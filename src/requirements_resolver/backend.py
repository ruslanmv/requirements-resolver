# File: src/requirements_resolver/backend.py

import os
import re
import sys
import json
import subprocess
from pathlib import Path
import requests
from packaging.version import parse
from packaging.specifiers import SpecifierSet, InvalidSpecifier

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

    def parse_requirements(self, file_path):
        """
        Parses a requirements.txt file into a dictionary of package names and specifiers,
        correctly handling inline comments.
        """
        dependencies = {}
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                # Remove inline comments and strip whitespace before processing
                line_without_comments = line.split('#', 1)[0].strip()
                
                if line_without_comments:
                    # A more robust regex to handle various package name formats
                    match = re.match(r'([a-zA-Z0-9_.-]+)(.*)', line_without_comments)
                    if match:
                        name = match.group(1)
                        specifier = match.group(2).strip()
                        try:
                            dependencies[name.lower()] = SpecifierSet(specifier)
                        except InvalidSpecifier:
                            print(
                                f"Warning: Skipping malformed requirement in '{os.path.basename(file_path)}' "
                                f"on line {line_num}: '{line_without_comments}'"
                            )
        return dependencies

    def get_package_info(self, package_name):
        """
        Fetches all available versions of a package from PyPI and their Python requirements.
        Caches the result to avoid repeated network requests.
        Returns a dictionary mapping version string to its 'requires_python' specifier.
        """
        cache_file = self.cache_dir / f"{package_name}.json"
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                return json.load(f)

        try:
            response = self.session.get(f"https://pypi.org/pypi/{package_name}/json")
            response.raise_for_status()
            data = response.json()
            version_info = {}
            for version, dists in data["releases"].items():
                # Find the 'requires_python' for the version. Prioritize wheels.
                requires_python_spec = None
                if dists:
                    # Find a wheel distribution if possible
                    wheel_dists = [d for d in dists if d.get('packagetype') == 'bdist_wheel']
                    if wheel_dists:
                        requires_python_spec = wheel_dists[0].get('requires_python')
                    else: # Fallback to source distribution
                        requires_python_spec = dists[0].get('requires_python')
                version_info[version] = requires_python_spec

            with open(cache_file, 'w') as f:
                json.dump(version_info, f)
            return version_info
        except requests.RequestException:
            return {}

    def find_compatible_version(self, package_name, specifiers, python_version=None):
        """
        Finds the latest version of a package that satisfies a set of specifiers and a Python version.
        """
        package_info = self.get_package_info(package_name)
        compatible_versions = []
        
        # Combine all specifiers for the package
        combined_spec = SpecifierSet("")
        for spec in specifiers:
            combined_spec &= spec

        for v_str, requires_python_spec in package_info.items():
            try:
                version = parse(v_str)
                if version.is_prerelease or not combined_spec.contains(version):
                    continue

                # Check Python version compatibility if specified
                if python_version and requires_python_spec:
                    if not SpecifierSet(requires_python_spec).contains(python_version):
                        continue
                
                compatible_versions.append(version)
            except Exception:
                continue  # Ignore invalid version strings

        return max(compatible_versions) if compatible_versions else None

    def test_environment(self, requirements, log_queue, python_version=None):
        """
        Creates a virtual environment with a specific Python version and installs dependencies.
        """
        venv_dir = self.cache_dir / f"test_env_py{python_version or 'default'}"
        log_queue.put(f"STATUS: Creating test environment in {venv_dir}...")
        
        # Determine the python executable to use
        python_executable = f"python{python_version}" if python_version else sys.executable
        
        try:
            # Ensure the python version exists
            subprocess.run([python_executable, "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            log_queue.put(f"ERROR: Python interpreter '{python_executable}' not found in PATH.")
            return False

        # Create the virtual environment using the specified python
        subprocess.run([python_executable, "-m", "venv", venv_dir, "--clear"], check=True, capture_output=True)

        pip_executable = str(venv_dir / "bin" / "pip")
        
        log_queue.put("STATUS: Installing resolved dependencies...")
        for package, version in requirements.items():
            install_command = [pip_executable, "install", f"{package}=={version}"]
            try:
                subprocess.run(install_command, check=True, capture_output=True, text=True)
                log_queue.put(f"Successfully installed {package}=={version}")
            except subprocess.CalledProcessError as e:
                log_queue.put(f"ERROR: Failed to install {package}=={version}")
                log_queue.put(e.stderr)
                return False
        
        log_queue.put("All dependencies installed successfully in the test environment.")
        return True

    def resolve_dependencies(self, files, log_queue, output_file="requirements.merged.txt", python_version=None):
        """
        The main function to resolve dependencies between multiple files for a specific Python version.
        """
        try:
            all_reqs = {}
            for file_path in files:
                log_queue.put(f"Parsing {os.path.basename(file_path)}...")
                parsed = self.parse_requirements(file_path)
                for package, spec in parsed.items():
                    if package not in all_reqs:
                        all_reqs[package] = []
                    all_reqs[package].append(spec)

            resolved_reqs = {}
            conflicts = []

            log_queue.put(f"STATUS: Resolving conflicts for Python {python_version or 'system default'}...")
            for package, specifiers in sorted(all_reqs.items()):
                log_queue.put(f"Resolving {package} ({', '.join(map(str, specifiers))})...")
                
                compatible_version = self.find_compatible_version(package, specifiers, python_version)

                if compatible_version:
                    resolved_reqs[package] = compatible_version
                    log_queue.put(f"  ✅ Found compatible version for {package}: {compatible_version}")
                else:
                    conflicts.append(package)
                    log_queue.put(f"  ❌ No compatible version found for {package}")
            
            if conflicts:
                log_queue.put(f"\nCould not resolve the following conflicts: {', '.join(conflicts)}")
                log_queue.put(("RESOLUTION_COMPLETE", "Resolution failed due to conflicts."))
                return

            if self.test_environment(resolved_reqs, log_queue, python_version):
                with open(output_file, 'w') as f:
                    for package, version in resolved_reqs.items():
                        f.write(f"{package}=={version}\n")
                log_queue.put(f"\nSuccessfully created '{output_file}'")
                log_queue.put(("RESOLUTION_COMPLETE", "Resolution successful!"))
            else:
                log_queue.put("\nrequirements installation failed in the test environment.")
                log_queue.put(("RESOLUTION_COMPLETE", "Resolution failed during testing."))

        except FileNotFoundError as e:
            log_queue.put(f"ERROR: File not found - {e.filename}")
            log_queue.put(("RESOLUTION_COMPLETE", "An error occurred."))
        except Exception as e:
            log_queue.put(f"An unexpected error occurred: {e}")
            log_queue.put(("RESOLUTION_COMPLETE", "An error occurred."))