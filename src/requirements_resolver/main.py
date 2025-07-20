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
    parser = argparse.ArgumentParser(
        description="Resolve requirements conflicts between multiple requirements files for a target Python version."
    )
    parser.add_argument(
        "-f",
        "--files",
        nargs="+",  # Accept one or more files
        metavar="FILE",
        help="One or more requirements files to merge.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="requirements.merged.txt",
        help="The name of the output file for the merged requirements. Defaults to requirements.merged.txt",
    )
    parser.add_argument(
        "-p",
        "--python",
        dest="python_version",
        help="Specify the target Python version for requirements resolution (e.g., 3.9).",
    )

    args = parser.parse_args()
    backend = Backend()

    if args.files:
        # --- CLI Mode ---
        run_cli_mode(backend, args)
    else:
        # --- GUI Mode ---
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
                        print(f"Status: {data}", file=sys.stderr)
                    elif msg_type == "RESOLUTION_COMPLETE":
                        print(data)
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

    backend.resolve_dependencies(
        files=args.files,
        log_queue=log_queue,
        output_file=args.output,
        python_version=args.python_version,
    )
    logger_thread.join(timeout=2)  # Wait for logger to finish


def run_gui_mode(backend):
    """
    Handles the application logic for GUI execution.
    Catches the ImportError if Tkinter is not installed and provides helpful instructions.
    """
    try:
        # This dynamic import will fail if tkinter is not available
        from .ui import RequirementsResolverUI

        app = RequirementsResolverUI(backend)
        app.mainloop()
    except ImportError:
        # If the import fails, provide detailed, OS-specific instructions.
        print("--- GUI Error: Tkinter is not installed ---", file=sys.stderr)
        print(
            "\nThe graphical user interface requires the Tkinter library, which was not found in your Python installation.",
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
            print("  - On Arch Linux:    sudo pacman -S tk", file=sys.stderr)
        elif os_name == "Darwin":  # macOS
            print(
                "\n  - If you use Homebrew (recommended): brew install python-tk",
                file=sys.stderr,
            )
            print(
                "  - Alternatively, reinstall Python from python.org, ensuring 'Tcl/Tk support' is selected during installation.",
                file=sys.stderr,
            )
        elif os_name == "Windows":
            print(
                "\n  - Re-run the Python installer, choose 'Modify', and ensure the 'tcl/tk and IDLE' option is checked.",
                file=sys.stderr,
            )

        print("\n-------------------------------------------------", file=sys.stderr)
        print(
            "\nIn the meantime, you can use the command-line interface.",
            file=sys.stderr,
        )
        print(
            "Example: requirements-resolver --files requirements1.txt requirements2.txt",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
