# File: src/requirements_resolver/backend.py

import json
import os
import re
import shutil  # --- ADDED: For deleting directories ---
import subprocess
import sys
from pathlib import Path

import requests
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, parse


class Backend:
    """
    Handles the core logic for resolving requirements conflicts.
    """

    def __init__(self):
        """
        Initializes the backend, setting up a cache directory.
        """
        self.cache_dir = Path.home() / ".requirements_resolver_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.session = requests.Session()

    # --- NEW: Method to clean the test environment ---
    def clean_test_environment(self, log_queue, python_version=None):
        """Removes the temporary virtual environment directory."""
        venv_dir = self.cache_dir / f"test_env_py{python_version or 'default'}"
        log_queue.put(f"Attempting to clean environment: {venv_dir}")
        if venv_dir.exists():
            try:
                shutil.rmtree(venv_dir)
                log_queue.put(f"✅ Successfully removed {venv_dir}")
            except OSError as e:
                log_queue.put(f"❌ Error removing environment: {e}")
        else:
            log_queue.put("No test environment found to clean.")

    def parse_requirements(self, file_path):
        """
        Parses a requirements.txt file.
        """
        dependencies = {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line_without_comments = line.split("#", 1)[0].strip()
                    if not line_without_comments:
                        continue

                    match = re.match(
                        r"^([a-zA-Z0-9_.-]+)((?:[<>=!~].*)?)$", line_without_comments
                    )

                    if match:
                        name = match.group(1).lower()
                        specifier_str = match.group(2).strip()
                        try:
                            new_spec = SpecifierSet(specifier_str)
                            if name in dependencies:
                                dependencies[name] &= new_spec
                            else:
                                dependencies[name] = new_spec
                        except InvalidSpecifier:
                            print(
                                f"Warning: Skipping malformed requirement in '{os.path.basename(file_path)}' "
                                f"on line {line_num}: '{line_without_comments}'"
                            )
        except FileNotFoundError:
            print(f"ERROR: File not found: '{file_path}'")
            raise
        except Exception as e:
            print(
                f"ERROR: An unexpected error occurred while parsing '{file_path}': {e}"
            )
            raise

        return dependencies

    def get_package_info(self, package_name):
        """
        Fetches all available versions of a package from PyPI. Caches the result.
        """
        cache_file = self.cache_dir / f"{package_name}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        try:
            response = self.session.get(f"https://pypi.org/pypi/{package_name}/json")
            response.raise_for_status()
            data = response.json()
            version_info = {}
            for version, dists in data.get("releases", {}).items():
                if not dists:
                    continue
                wheel_dist = next(
                    (d for d in dists if d.get("packagetype") == "bdist_wheel"), None
                )
                if wheel_dist and wheel_dist.get("requires_python"):
                    version_info[version] = wheel_dist.get("requires_python")
                else:
                    version_info[version] = dists[0].get("requires_python")

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(version_info, f)
            return version_info
        except requests.RequestException:
            return {}

    def find_compatible_version(
        self, package_name, combined_specifiers, python_version=None
    ):
        """
        Finds the latest version of a package that satisfies a combined SpecifierSet.
        """
        package_info = self.get_package_info(package_name)
        compatible_versions = []

        for v_str, requires_python_spec_str in package_info.items():
            try:
                version = parse(v_str)
                if version.is_prerelease:
                    continue
                if not combined_specifiers.contains(version):
                    continue
                if python_version and requires_python_spec_str:
                    if not SpecifierSet(requires_python_spec_str).contains(
                        python_version
                    ):
                        continue
                compatible_versions.append(version)
            except (InvalidSpecifier, TypeError, InvalidVersion):
                continue

        return max(compatible_versions) if compatible_versions else None

    def test_environment(self, requirements, log_queue, python_version=None):
        """
        Creates a virtual environment and installs dependencies to verify them.
        """
        if not requirements:
            log_queue.put(
                "STATUS: No requirements to test, skipping environment creation."
            )
            return True

        venv_dir = self.cache_dir / f"test_env_py{python_version or 'default'}"
        log_queue.put(f"STATUS: Creating test environment in {venv_dir}...")

        python_executable = (
            f"python{python_version}" if python_version else sys.executable
        )

        try:
            subprocess.run(
                [python_executable, "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            log_queue.put(f"ERROR: Python interpreter '{python_executable}' not found.")
            return False

        # The --clear flag ensures the environment is clean for each run.
        subprocess.run(
            [python_executable, "-m", "venv", str(venv_dir), "--clear"],
            check=True,
            capture_output=True,
        )

        if sys.platform == "win32":
            pip_executable = str(venv_dir / "Scripts" / "pip.exe")
        else:
            pip_executable = str(venv_dir / "bin" / "pip")

        log_queue.put(
            "STATUS: Installing resolved dependencies into test environment..."
        )
        for package, version in requirements.items():
            install_command = [pip_executable, "install", f"{package}=={version}"]
            try:
                subprocess.run(
                    install_command,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                log_queue.put(f"  ✅ Successfully installed {package}=={version}")
            except subprocess.CalledProcessError as e:
                log_queue.put(f"❌ ERROR: Failed to install {package}=={version}")
                log_queue.put(f"  DETAILS: {e.stderr}")
                return False

        log_queue.put(
            "✅ All dependencies installed successfully in the test environment."
        )
        return True

    def resolve_dependencies(
        self,
        files,
        log_queue,
        output_file="requirements.merged.txt",
        python_version=None,
        install_in_env=True,  # --- ADDED: Flag for optional installation ---
    ):
        """
        The main function to resolve dependencies between multiple files.
        """
        try:
            all_reqs = {}
            for file_path in files:
                log_queue.put(f"Parsing {os.path.basename(file_path)}...")
                parsed_from_file = self.parse_requirements(file_path)
                for package, spec in parsed_from_file.items():
                    if package in all_reqs:
                        all_reqs[package] &= spec
                    else:
                        all_reqs[package] = spec

            resolved_reqs = {}
            conflicts = []

            log_queue.put(
                f"STATUS: Resolving conflicts for Python {python_version or 'system default'}..."
            )

            if not all_reqs:
                log_queue.put(
                    "ERROR: No requirements were parsed from the provided files."
                )
                log_queue.put(
                    ("RESOLUTION_COMPLETE", "Resolution failed: No requirements found.")
                )
                return

            for package, specifiers in sorted(all_reqs.items()):
                log_queue.put(f"Resolving {package} ({specifiers or 'any version'})...")
                compatible_version = self.find_compatible_version(
                    package, specifiers, python_version
                )
                if compatible_version:
                    resolved_reqs[package] = str(compatible_version)
                    log_queue.put(
                        f"  ✅ Found compatible version for {package}: {compatible_version}"
                    )
                else:
                    conflicts.append(package)
                    log_queue.put(f"  ❌ No compatible version found for {package}")

            if conflicts:
                log_queue.put(
                    f"\nCould not resolve the following conflicts: {', '.join(conflicts)}"
                )
                log_queue.put(
                    ("RESOLUTION_COMPLETE", "Resolution failed due to conflicts.")
                )
                return

            # --- MODIFIED: Logic to handle optional installation ---
            if install_in_env:
                log_queue.put("\n--- Starting Environment Test ---")
                if self.test_environment(resolved_reqs, log_queue, python_version):
                    is_success = True
                    final_message = (
                        "Resolution successful and validated in test environment!"
                    )
                else:
                    is_success = False
                    final_message = "Resolution failed during environment test."
            else:
                log_queue.put("\nSkipping environment test as requested.")
                is_success = True
                final_message = "Resolution successful!"

            if is_success:
                with open(output_file, "w", encoding="utf-8") as f:
                    for package, version in resolved_reqs.items():
                        f.write(f"{package}=={version}\n")
                log_queue.put(f"\nSuccessfully created '{output_file}'")
                # --- ADD THIS LINE to send data to the UI ---
                log_queue.put(("RESOLUTION_DATA", resolved_reqs))

            log_queue.put(("RESOLUTION_COMPLETE", final_message))

        except FileNotFoundError as e:
            log_queue.put(f"ERROR: File not found - {e.filename}")
            log_queue.put(("RESOLUTION_COMPLETE", "An error occurred."))
        except Exception as e:
            log_queue.put(f"An unexpected error occurred: {e}")
            log_queue.put(("RESOLUTION_COMPLETE", "An error occurred."))
