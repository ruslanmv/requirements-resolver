# File: src/requirements_resolver/main.py

import argparse
import queue
import sys

from .backend import Backend
from .ui import RequirementsResolverUI


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

    import threading

    main_thread = threading.current_thread()
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
    """Handles the application logic for GUI execution."""
    if not is_tkinter_installed():
        print(
            "Error: Tkinter is not installed, which is required for the GUI.",
            file=sys.stderr,
        )
        print(
            "Please install it for your system (e.g., 'sudo apt-get install python3-tk' on Debian/Ubuntu).",
            file=sys.stderr,
        )
        sys.exit(1)
    app = RequirementsResolverUI(backend)
    app.mainloop()


def is_tkinter_installed():
    """Checks if the tkinter module is available."""
    try:
        import tkinter  # <-- Correct
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    main()
