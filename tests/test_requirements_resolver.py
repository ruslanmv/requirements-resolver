# File: tests/test_requirements_resolver.py
import os
import queue
import tempfile
import unittest
from pathlib import Path

# To make this test runnable, we need to add the src directory to the path
# This is a common pattern for testing local packages without installation.
import sys

# Add the 'src' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from requirements_resolver.backend import Backend


class TestRequirementsResolver(unittest.TestCase):
    """
    Test suite for the requirements resolver backend.
    """

    def setUp(self):
        """
        Set up a temporary directory and files for testing.
        This method is called before each test.
        """
        # Create a temporary directory to work in
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_dir_path = Path(self.test_dir.name)

        # Create a dummy requirements file
        self.reqs1_path = self.test_dir_path / "requirements1.txt"
        with open(self.reqs1_path, "w") as f:
            f.write("requests>2.20\n")
            f.write("packaging<24\n")

        # The path for the output file
        self.output_path = self.test_dir_path / "resolved.txt"

    def tearDown(self):
        """
        Clean up the temporary directory after each test.
        """
        self.test_dir.cleanup()

    def test_cli_resolution_smoke_test(self):
        """
        A simple smoke test to ensure the core dependency resolution logic works.
        """
        # --- 1. Setup ---
        backend = Backend()
        # A queue to capture logs/messages from the backend
        log_queue = queue.Queue()
        # Get the current python version dynamically (e.g., "3.11", "3.12")
        current_python_version = f"{sys.version_info.major}.{sys.version_info.minor}"


        # --- 2. Execution ---
        # Run the main function from the backend
        backend.resolve_dependencies(
            files=[str(self.reqs1_path)],
            log_queue=log_queue,
            output_file=str(self.output_path),
            python_version=current_python_version,  # Use the current Python version
        )

        # --- 3. Verification ---
        # Check that the output file was created
        self.assertTrue(
            self.output_path.exists(), "The output file was not created."
        )

        # Read the content of the output file
        with open(self.output_path, "r") as f:
            content = f.read()

        # Check that the resolved packages are in the output
        self.assertIn(
            "requests==", content, "Resolved version of 'requests' not found in output."
        )
        self.assertIn(
            "packaging==",
            content,
            "Resolved version of 'packaging' not found in output.",
        )

        print(f"\n--- Test Output (Python {current_python_version}) ---")
        print(content)
        print("---------------------------------")


if __name__ == "__main__":
    unittest.main()