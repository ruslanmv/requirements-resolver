# File: src/requirements_resolver/main.py

import argparse
import platform
import queue
import sys
import threading

from .backend import Backend


def main():
    """
    The main entry point for the application.
    Parses command-line arguments to either run in CLI mode or launch the GUI.
    """
    # --- MODIFIED: Use RawTextHelpFormatter for better formatting and add a detailed epilog for examples ---
    parser = argparse.ArgumentParser(
        description="A tool to merge multiple requirements.txt files, resolve version conflicts, and create a single, unified file.\n\n"
        "It intelligently combines specifiers (e.g., package>=1.0 and package<2.0 become package>=1.0,<2.0)\n"
        "and finds the latest compatible version for each package from PyPI.",
        epilog="""
Examples:
--------------------------------------------------------------------------------
1. Merge two files into the default 'requirements.merged.txt':
   requirements-resolver -f project_reqs.txt dev_reqs.txt

2. Merge and specify a different output file name:
   requirements-resolver -f reqs1.txt reqs2.txt -o final.txt

3. Merge and check for compatibility with Python 3.11:
   requirements-resolver -f reqs.txt -p 3.11

4. Merge without creating a test environment (faster):
   requirements-resolver -f reqs.txt --no-test

5. Combine all options:
   requirements-resolver -f app.txt test.txt -p 3.10 -o final_reqs.txt --no-test
""",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    # --- MODIFIED: Make the --files argument required in CLI mode and improve help text ---
    parser.add_argument(
        "-f",
        "--files",
        nargs="+",
        metavar="FILE",
        help="Path to one or more requirements files to process (e.g., reqs1.txt reqs2.txt).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="requirements.merged.txt",
        help="Name for the generated file. (Default: requirements.merged.txt).",
    )
    parser.add_argument(
        "-p",
        "--python",
        dest="python_version",
        help="Target Python version (e.g., 3.10) to check for compatibility.",
    )
    # --- NEW: Add --no-test flag to skip environment installation ---
    parser.add_argument(
        "--no-test",
        dest="install_in_env",
        action="store_false",
        help="Skip creating a test environment and installing packages. This is faster but\ndoes not verify if the packages can be installed together.",
    )

    args = parser.parse_args()
    backend = Backend()

    if args.files:
        # --- CLI Mode ---
        run_cli_mode(backend, args)
    else:
        # --- GUI Mode ---
        # If no files are provided via CLI, launch the GUI.
        run_gui_mode(backend)


def run_cli_mode(backend, args):
    """Handles the application logic for command-line execution."""
    log_queue = queue.Queue()
    main_thread = threading.current_thread()

    # Simple console logger
    def console_logger(q):
        while True:
            try:
                message = q.get_nowait()
                if isinstance(message, tuple):
                    msg_type, data = message
                    if msg_type == "STATUS":
                        # Status messages are more for GUI, print to stderr in CLI
                        print(f"Status: {data}", file=sys.stderr)
                    elif msg_type == "RESOLUTION_DATA":
                        # In CLI mode, the data is written to the file, so we can ignore this.
                        pass
                    elif msg_type == "RESOLUTION_COMPLETE":
                        print(f"\n--- {data} ---")
                        # Check for failure to set exit code
                        if (
                            "fail" in data.lower()
                            or "error" in data.lower()
                            or "conflict" in data.lower()
                        ):
                            sys.exit(1)
                        break  # End the logger thread
                else:
                    print(message)
            except queue.Empty:
                if not main_thread.is_alive():
                    break
            except Exception:
                break

    logger_thread = threading.Thread(
        target=console_logger, args=(log_queue,), daemon=True
    )
    logger_thread.start()

    # --- MODIFIED: Pass the 'install_in_env' argument to the backend ---
    backend.resolve_dependencies(
        files=args.files,
        log_queue=log_queue,
        output_file=args.output,
        python_version=args.python_version,
        install_in_env=args.install_in_env,
    )
    logger_thread.join(timeout=5)  # Wait for logger to finish


def run_gui_mode(backend):
    """
    Handles the application logic for GUI execution.
    """
    try:
        from .ui import RequirementsResolverUI

        app = RequirementsResolverUI(backend)
        app.mainloop()
    except ImportError:
        print("--- GUI Error: Tkinter is not installed ---", file=sys.stderr)
        print(
            "\nThe graphical user interface requires the Tkinter library, which was not found.",
            file=sys.stderr,
        )

        os_name = platform.system()
        print(
            "\nTo fix this, please install Tkinter for your operating system:",
            file=sys.stderr,
        )

        if os_name == "Linux":
            print(
                "\n  - On Debian/Ubuntu: sudo apt-get install python3-tk",
                file=sys.stderr,
            )
            print(
                "  - On Fedora/CentOS: sudo dnf install python3-tkinter",
                file=sys.stderr,
            )
        elif os_name == "Darwin":  # macOS
            print("\n  - If you use Homebrew: brew install python-tk", file=sys.stderr)
        elif os_name == "Windows":
            print(
                "\n  - Re-run the Python installer, choose 'Modify', and ensure 'tcl/tk and IDLE' is checked.",
                file=sys.stderr,
            )

        print("\n-------------------------------------------------", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
