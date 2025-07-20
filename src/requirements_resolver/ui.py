# File: src/requirements_resolver/ui.py

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import queue
import threading
import os

class RequirementsResolverUI(tk.Tk):
    """
    A graphical user interface for the requirements Resolver application.
    """
    def __init__(self, backend_logic):
        """
        Initializes the user interface.
        """
        super().__init__()
        self.title("requirements Resolver")
        self.geometry("800x600")

        self.backend = backend_logic
        self.log_queue = queue.Queue()
        self.file_list = []

        # --- UI Variables ---
        self.python_version_var = tk.StringVar(value="3.9")

        # --- UI Components ---
        self.create_widgets()
        self.check_log_queue()

    def create_widgets(self):
        """
        Creates and arranges the widgets in the main window.
        """
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Top Control Frame ---
        top_controls = ttk.Frame(main_frame)
        top_controls.pack(fill=tk.X, pady=5)

        # --- File Management Frame ---
        file_frame = ttk.LabelFrame(top_controls, text="Requirements Files", padding="10")
        file_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.file_listbox = tk.Listbox(file_frame, height=4)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        file_buttons_frame = ttk.Frame(file_frame)
        file_buttons_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(file_buttons_frame, text="Add File...", command=self.add_file).pack(pady=2, fill=tk.X)
        ttk.Button(file_buttons_frame, text="Remove Selected", command=self.remove_file).pack(pady=2, fill=tk.X)

        # --- Options Frame ---
        options_frame = ttk.LabelFrame(top_controls, text="Options", padding="10")
        options_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        ttk.Label(options_frame, text="Python Version:").pack(anchor="w")
        # Common Python versions
        py_versions = ["3.8", "3.9", "3.10", "3.11", "3.12"]
        python_select = ttk.Combobox(options_frame, textvariable=self.python_version_var, values=py_versions, width=10)
        python_select.pack(anchor="w")
        python_select.set("3.9") # Default value

        # --- Main Action Frame ---
        action_frame = ttk.Frame(main_frame, padding="10")
        action_frame.pack(fill=tk.X, pady=10)

        self.resolve_button = ttk.Button(action_frame, text="Resolve Dependencies", command=self.start_resolution)
        self.resolve_button.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(action_frame, text="Status: Idle")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # --- Log Frame ---
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state="disabled", height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def add_file(self):
        """Opens a file dialog to add a requirements file to the list."""
        filenames = filedialog.askopenfilenames(
            title="Select requirements files",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        for filename in filenames:
            if filename and filename not in self.file_list:
                self.file_list.append(filename)
                self.file_listbox.insert(tk.END, os.path.basename(filename))

    def remove_file(self):
        """Removes the selected file from the list."""
        selected_indices = self.file_listbox.curselection()
        # Iterate backwards to avoid index shifting issues
        for i in sorted(selected_indices, reverse=True):
            self.file_listbox.delete(i)
            del self.file_list[i]

    def log(self, message):
        """Logs a message to the text area in a thread-safe way."""
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, str(message) + "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see(tk.END)

    def check_log_queue(self):
        """Periodically checks the log queue for new messages to display from the backend."""
        while not self.log_queue.empty():
            try:
                message = self.log_queue.get_nowait()
                if isinstance(message, tuple):
                    msg_type, data = message
                    if msg_type == "STATUS":
                        self.status_label.config(text=f"Status: {data}")
                    elif msg_type == "RESOLUTION_COMPLETE":
                        self.log(data)
                        self.status_label.config(text=f"Status: {data}")
                        self.resolve_button.config(state="normal")
                else:
                    self.log(message)
            except queue.Empty:
                pass
        self.after(100, self.check_log_queue)

    def start_resolution(self):
        """Starts the requirements resolution process in a new thread to keep the UI responsive."""
        if not self.file_list:
            self.log("Please add at least one requirements file.")
            return

        self.resolve_button.config(state="disabled")
        self.log("--- Starting requirements Resolution ---")

        python_version = self.python_version_var.get()

        threading.Thread(
            target=self.backend.resolve_dependencies,
            kwargs={
                'files': self.file_list,
                'log_queue': self.log_queue,
                'python_version': python_version
            },
            daemon=True
        ).start()
