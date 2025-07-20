# File: src/requirements_resolver/backend.py

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path

# Third-party libraries must be installed for certain algorithms
try:
    import requests
except ImportError:
    requests = None

try:
    import yaml
except ImportError:
    yaml = None

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, parse


class Algorithm(Enum):
    """Enum for selecting the resolution strategy."""

    GREEDY = "Greedy Latest-Compatible"
    BACKTRACKING = "Version Range with Backtracking"
    ISOLATED_ENVS = "Per-File Isolated Environments"
    PEX_BUNDLE = "Wheelhouse + PEX Bundle"
    CONDA = "Conda-First Hybrid Resolution"

    def __str__(self):
        return self.value


class Backend:
    """
    Handles the core logic for resolving dependency conflicts using various algorithms.
    """

    def __init__(self):
        """Initializes the backend, setting up a cache directory."""
        self.cache_dir = Path.home() / ".requirements_resolver_cache"
        self.cache_dir.mkdir(exist_ok=True)
        if requests:
            self.session = requests.Session()
        else:
            self.session = None

    # --- Core Helpers ---

    def _parse_requirements(self, file_path):
        """Parses a single requirements file into a dictionary of name -> SpecifierSet."""
        dependencies = {}
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                match = re.match(r"^([a-zA-Z0-9_.-]+)((?:[<>=!~].*)?)$", line)
                if match:
                    name, spec_str = match.group(1).lower(), match.group(2).strip()
                    try:
                        # Store as a set for intersection later
                        dependencies[name] = SpecifierSet(spec_str)
                    except InvalidSpecifier:
                        # This warning can be logged if needed
                        pass
        return dependencies

    def _collect_and_intersect_reqs(self, files, log_queue):
        """Parses all files and intersects specifiers for common packages."""
        all_reqs = {}
        for file_path in files:
            log_queue.put(f"Parsing {os.path.basename(file_path)}...")
            parsed = self._parse_requirements(file_path)
            for package, spec in parsed.items():
                if package in all_reqs:
                    all_reqs[package] &= spec  # Intersect the specifiers
                else:
                    all_reqs[package] = spec
        return all_reqs

    def get_package_info(self, package_name):
        """Fetches package version info from PyPI, using a cache."""
        if not self.session:
            return {}
        cache_file = self.cache_dir / f"{package_name}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass  # Cache is corrupt, refetch

        try:
            response = self.session.get(f"https://pypi.org/pypi/{package_name}/json")
            response.raise_for_status()
            data = response.json()
            # Extract python version requirement for each package version
            version_info = {
                v: dists[0].get("requires_python")
                for v, dists in data.get("releases", {}).items()
                if dists
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(version_info, f)
            return version_info
        except requests.RequestException:
            return {}

    def _get_compatible_versions(self, package, specifier_set, python_version):
        """Returns all non-prerelease versions satisfying the spec and python version."""
        info = self.get_package_info(package)
        compatible = []
        for v_str, req_py in info.items():
            try:
                version = parse(v_str)
                if version.is_prerelease or not specifier_set.contains(version):
                    continue
                if (
                    python_version
                    and req_py
                    and not SpecifierSet(req_py).contains(python_version)
                ):
                    continue
                compatible.append(version)
            except (InvalidSpecifier, TypeError, InvalidVersion):
                continue
        return sorted(compatible, reverse=True)

    def _test_and_write_file(
        self, requirements, log_queue, output_file, python_version, install_in_env
    ):
        """Creates a venv, optionally tests installation, and writes the final file."""
        if install_in_env:
            venv_dir = self.cache_dir / f"test_env_py{python_version or 'default'}"
            log_queue.put(f"STATUS: Creating test environment in {venv_dir}...")
            py_exe = f"python{python_version}" if python_version else sys.executable
            try:
                subprocess.run(
                    [py_exe, "-m", "venv", str(venv_dir), "--clear"],
                    check=True,
                    capture_output=True,
                )
                pip_exe = (
                    str(venv_dir / "Scripts" / "pip")
                    if sys.platform == "win32"
                    else str(venv_dir / "bin" / "pip")
                )
                for pkg, ver in requirements.items():
                    subprocess.run(
                        [pip_exe, "install", f"{pkg}=={ver}"],
                        check=True,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                    )
                log_queue.put(
                    "✅ All dependencies installed successfully in the test environment."
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                log_queue.put(
                    f"❌ Test environment installation failed: {getattr(e, 'stderr', e)}"
                )
                return False

        with open(output_file, "w", encoding="utf-8") as f:
            for package, version in sorted(requirements.items()):
                f.write(f"{package}=={version}\n")
        log_queue.put(f"\nSuccessfully created '{output_file}'")
        return True

    # --- Algorithm 1: Greedy Latest-Compatible ---
    def _resolve_greedy(self, files, log_queue, python_version, **kwargs):
        all_reqs = self._collect_and_intersect_reqs(files, log_queue)
        resolved, conflicts = {}, []
        for package, specifiers in sorted(all_reqs.items()):
            log_queue.put(f"Resolving {package} ({specifiers or 'any version'})...")
            compatible_versions = self._get_compatible_versions(
                package, specifiers, python_version
            )
            if compatible_versions:
                resolved[package] = str(compatible_versions[0])
                log_queue.put(f"  ✅ Picked latest: {resolved[package]}")
            else:
                conflicts.append(package)
                log_queue.put(f"  ❌ No compatible version found.")
        return resolved, conflicts

    # --- Algorithm 2: Backtracking ---
    def _resolve_backtracking(self, files, log_queue, python_version, **kwargs):
        all_reqs = self._collect_and_intersect_reqs(files, log_queue)
        candidates = {
            pkg: self._get_compatible_versions(pkg, specs, python_version)
            for pkg, specs in all_reqs.items()
        }

        # Filter out packages with no compatible versions from the start
        if any(not versions for versions in candidates.values()):
            conflicts = [pkg for pkg, versions in candidates.items() if not versions]
            return {}, conflicts

        packages_to_resolve = list(candidates.keys())
        solution = {}

        def dfs(index):
            if index == len(packages_to_resolve):
                return True  # Found a full valid solution

            package = packages_to_resolve[index]
            log_queue.put(f"Searching for {package}...")
            for version in candidates[package]:
                solution[package] = str(version)
                # NOTE: A true backtracking solver would check sub-dependencies here to see
                # if this choice is viable. This is a simplified version demonstrating the pattern.
                if dfs(index + 1):
                    log_queue.put(f"  ✅ Tentatively selected {package}=={version}")
                    return True

            solution.pop(package, None)
            log_queue.put(f"  ❌ Backtracking from {package}, no valid path found.")
            return False

        if dfs(0):
            return solution, []
        return {}, list(packages_to_resolve)

    # --- Algorithm 3: Isolated Environments ---
    def _resolve_isolated_envs(self, files, log_queue, python_version, **kwargs):
        failures = []
        for req_file in files:
            file_name = os.path.basename(req_file)
            log_queue.put(f"\n--- Creating isolated environment for {file_name} ---")
            venv_dir = self.cache_dir / f"iso_env_{Path(req_file).stem}"
            py_exe = f"python{python_version}" if python_version else sys.executable
            try:
                subprocess.run(
                    [py_exe, "-m", "venv", str(venv_dir), "--clear"],
                    check=True,
                    capture_output=True,
                )
                pip_exe = (
                    str(venv_dir / "Scripts" / "pip")
                    if sys.platform == "win32"
                    else str(venv_dir / "bin" / "pip")
                )
                subprocess.run(
                    [pip_exe, "install", "-r", req_file],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                log_queue.put(
                    f"✅ Success: Environment for {file_name} created and installed."
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                log_queue.put(
                    f"❌ Failed to create/install env for {file_name}: {getattr(e, 'stderr', e)}"
                )
                failures.append(file_name)
        return {}, failures

    # --- Algorithm 4: PEX Bundle ---
    def _resolve_pex(self, files, log_queue, python_version, **kwargs):
        if not shutil.which("pex"):
            log_queue.put(
                "ERROR: 'pex' executable not found in PATH. Please run `pip install pex`."
            )
            return {}, ["'pex' not installed"]

        wheelhouse = self.cache_dir / "pex_wheelhouse"
        shutil.rmtree(wheelhouse, ignore_errors=True)
        wheelhouse.mkdir()

        log_queue.put("Building wheels for all requirements files...")
        combined_reqs_path = self.cache_dir / "pex_combined_reqs.txt"
        with open(combined_reqs_path, "w") as outfile:
            for fname in files:
                with open(fname) as infile:
                    outfile.write(infile.read())

        try:
            # Create a wheelhouse from all requirements at once
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "-r",
                    str(combined_reqs_path),
                    "-w",
                    str(wheelhouse),
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except subprocess.CalledProcessError as e:
            log_queue.put(f"❌ Failed to build wheels: {e.stderr}")
            return {}, ["Wheel build failed"]

        pex_file = Path("agentic.pex")
        cmd = [
            "pex",
            "--resolver-version=pip-2020-resolver",
            f"--wheel-dir={wheelhouse}",
            "-r",
            str(combined_reqs_path),
            "-o",
            str(pex_file),
            "--no-build",
        ]
        if python_version:
            cmd.extend(["--python", f"python{python_version}"])

        log_queue.put(f"Creating PEX bundle at {pex_file}...")
        try:
            subprocess.run(
                cmd, check=True, capture_output=True, text=True, encoding="utf-8"
            )
            log_queue.put(f"✅ PEX bundle created successfully: {pex_file}")
            return {}, []
        except subprocess.CalledProcessError as e:
            log_queue.put(f"❌ PEX creation failed: {e.stderr}")
            return {}, ["PEX bundling failed"]

    # --- Algorithm 5: Conda ---
    def _resolve_conda(self, files, log_queue, python_version, **kwargs):
        if not shutil.which("conda"):
            log_queue.put("ERROR: 'conda' executable not found in PATH.")
            return {}, ["'conda' not installed"]
        if not yaml:
            log_queue.put(
                "ERROR: 'PyYAML' is required. Please run `pip install pyyaml`."
            )
            return {}, ["'PyYAML' not installed"]

        log_queue.put("Aggregating dependencies for Conda...")
        all_deps = []
        for req_file in files:
            with open(req_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.split("#", 1)[0].strip()
                    if line:
                        # Convert pip's == to conda's = for version pinning
                        all_deps.append(line.replace("==", "="))

        env_data = {
            "name": "resolver-conda-env",
            "dependencies": ["pip", *sorted(list(set(all_deps)))],
        }
        if python_version:
            env_data["dependencies"].insert(0, f"python={python_version}")

        with tempfile.NamedTemporaryFile(
            "w", delete=False, suffix=".yml", encoding="utf-8"
        ) as f:
            yaml.dump(env_data, f, default_flow_style=False)
            env_file_path = f.name

        log_queue.put(f"Attempting to resolve with Conda (dry-run)...")
        try:
            # Use --dry-run and --json to get solver output without creating the env
            result = subprocess.run(
                ["conda", "env", "create", "-f", env_file_path, "--dry-run", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            os.unlink(env_file_path)  # Clean up temp file

            data = json.loads(result.stdout)
            if data.get("success"):
                log_queue.put("✅ Conda SAT solver succeeded.")
                return {}, []
            else:
                conflicts = data.get("error", "Unknown Conda error.")
                log_queue.put(f"❌ Conda resolution failed: {conflicts}")
                return {}, [str(conflicts)]
        except (
            FileNotFoundError,
            json.JSONDecodeError,
            subprocess.CalledProcessError,
        ) as e:
            os.unlink(env_file_path)
            log_queue.put(f"❌ Conda failed with an error: {e}")
            return {}, ["Conda process failed"]

    # --- Main Dispatcher ---
    def resolve_dependencies(
        self,
        files,
        log_queue,
        algorithm: Algorithm,
        output_file="requirements.merged.txt",
        python_version=None,
        install_in_env=True,
    ):
        """Public method to dispatch to the chosen resolution strategy."""

        strategies = {
            Algorithm.GREEDY: self._resolve_greedy,
            Algorithm.BACKTRACKING: self._resolve_backtracking,
            Algorithm.ISOLATED_ENVS: self._resolve_isolated_envs,
            Algorithm.PEX_BUNDLE: self._resolve_pex,
            Algorithm.CONDA: self._resolve_conda,
        }

        log_queue.put(f"--- Starting resolution with algorithm: {algorithm} ---")

        try:
            resolver_func = strategies[algorithm]
            resolved, conflicts = resolver_func(
                files=files, log_queue=log_queue, python_version=python_version
            )
        except Exception as e:
            log_queue.put(
                f"An unexpected error occurred in '{algorithm}' resolver: {e}"
            )
            log_queue.put(
                ("RESOLUTION_COMPLETE", "Resolution failed with an unexpected error.")
            )
            return

        if conflicts:
            log_queue.put(f"\n❌ Conflicts found for: {', '.join(conflicts)}")
            log_queue.put(
                ("RESOLUTION_COMPLETE", "Resolution failed due to conflicts.")
            )
            return

        # Post-processing for algorithms that produce a single requirements file
        if algorithm in (Algorithm.GREEDY, Algorithm.BACKTRACKING):
            if not resolved:
                log_queue.put("\n❌ Algorithm failed to find a valid set of packages.")
                log_queue.put(
                    ("RESOLUTION_COMPLETE", "Resolution failed: No solution found.")
                )
                return

            if self._test_and_write_file(
                resolved, log_queue, output_file, python_version, install_in_env
            ):
                log_queue.put(("RESOLUTION_DATA", resolved))
                log_queue.put(("RESOLUTION_COMPLETE", "Resolution successful!"))
            else:
                log_queue.put(
                    (
                        "RESOLUTION_COMPLETE",
                        "Resolution succeeded, but test environment failed.",
                    )
                )
            return

        # Success message for other algorithms that don't produce a file
        log_queue.put(f"\n✅ Algorithm '{algorithm}' completed successfully.")
        log_queue.put(("RESOLUTION_COMPLETE", "Resolution successful!"))
