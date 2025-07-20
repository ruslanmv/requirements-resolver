# File: src/requirements_resolver/ui.py

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk

# Import the Algorithm enum from the backend
from .backend import Algorithm


class RequirementsResolverUI(tk.Tk):
    """
    A graphical user interface for the Requirements Resolver application.
    """

    def __init__(self, backend_logic):
        """
        Initializes the user interface.
        """
        super().__init__()
        self.title("Requirements Resolver")
        self.geometry("800x650")

        self.backend = backend_logic
        self.log_queue = queue.Queue()
        self.file_list = []
        self.resolved_reqs = {}

        # --- UI Variables ---
        self.python_version_var = tk.StringVar(value="3.9")
        self.install_var = tk.BooleanVar(value=True)
        self.algorithm_var = tk.StringVar()

        # --- UI Components ---
        self.create_widgets()
        self.check_log_queue()

    def create_widgets(self):
        """
        Creates and arranges the widgets in the main window.
        """
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_controls = ttk.Frame(main_frame)
        top_controls.pack(fill=tk.X, pady=5)

        file_frame = ttk.LabelFrame(top_controls, text="Requirements Files", padding="10")
        file_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.file_listbox = tk.Listbox(file_frame, height=5)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        file_buttons_frame = ttk.Frame(file_frame)
        file_buttons_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(file_buttons_frame, text="Add File(s)...", command=self.add_file).pack(pady=2, fill=tk.X)
        ttk.Button(file_buttons_frame, text="Remove Selected", command=self.remove_file).pack(pady=2, fill=tk.X)

        options_frame = ttk.LabelFrame(top_controls, text="Options", padding="10")
        options_frame.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(options_frame, text="Algorithm:").pack(anchor="w")
        # Use the string representation from the Enum for user-friendly names
        algo_names = [str(algo) for algo in Algorithm]
        algo_select = ttk.Combobox(options_frame, textvariable=self.algorithm_var, values=algo_names, state="readonly", width=30)
        algo_select.pack(anchor="w", pady=(0, 5))
        algo_select.set(str(Algorithm.GREEDY))  # Default value

        ttk.Label(options_frame, text="Python Version:").pack(anchor="w")
        py_versions = ["3.8", "3.9", "3.10", "3.11", "3.12", "3.13"]
        python_select = ttk.Combobox(options_frame, textvariable=self.python_version_var, values=py_versions, width=30)
        python_select.pack(anchor="w", pady=(0, 5))
        python_select.set("3.9")

        install_check = ttk.Checkbutton(options_frame, text="Create and test environment", variable=self.install_var)
        install_check.pack(anchor="w")
        
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(10, 5))

        self.resolve_button = ttk.Button(action_frame, text="Resolve Dependencies", command=self.start_resolution)
        self.resolve_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.view_reqs_button = ttk.Button(action_frame, text="View Resolved File", command=self.view_resolved_requirements, state="disabled")
        self.view_reqs_button.pack(side=tk.LEFT, padx=5)
        
        self.clean_cache_button = ttk.Button(action_frame, text="Clean Environment Cache", command=self.clean_cache)
        self.clean_cache_button.pack(side=tk.LEFT, padx=5)

        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        self.status_label = ttk.Label(status_frame, text="Status: Idle", font=("TkDefaultFont", 10, "italic"))
        self.status_label.pack(side=tk.LEFT)

        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        log_header_frame = ttk.Frame(log_frame)
        log_header_frame.pack(fill=tk.X)

        self.save_log_button = ttk.Button(log_header_frame, text="Save Log...", command=self.save_log_file)
        self.save_log_button.pack(side=tk.RIGHT)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state="disabled", height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(5,0))

    def add_file(self):
        filenames = filedialog.askopenfilenames(title="Select requirements files", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
        for filename in filenames:
            if filename and filename not in self.file_list:
                self.file_list.append(filename)
                self.file_listbox.insert(tk.END, os.path.basename(filename))

    def remove_file(self):
        selected_indices = self.file_listbox.curselection()
        for i in sorted(selected_indices, reverse=True):
            self.file_listbox.delete(i)
            del self.file_list[i]

    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, str(message) + "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see(tk.END)

    def check_log_queue(self):
        while not self.log_queue.empty():
            try:
                message = self.log_queue.get_nowait()
                if isinstance(message, tuple):
                    msg_type, data = message
                    if msg_type == "STATUS":
                        self.status_label.config(text=f"Status: {data}")
                    elif msg_type == "RESOLUTION_DATA":
                        self.resolved_reqs = data
                        self.view_reqs_button.config(state="normal")
                    elif msg_type == "RESOLUTION_COMPLETE":
                        self.log(f"\n--- {data} ---")
                        self.status_label.config(text=f"Status: {data}")
                        self.resolve_button.config(state="normal")
                        self.clean_cache_button.config(state="normal")
                else:
                    self.log(message)
            except queue.Empty:
                pass
        self.after(100, self.check_log_queue)
    
    def save_log_file(self):
        log_content = self.log_text.get("1.0", tk.END)
        if not log_content.strip():
            self.log("Log is empty. Nothing to save.")
            return
        filename = filedialog.asksaveasfilename(title="Save Log File", defaultextension=".log", filetypes=(("Log files", "*.log"), ("Text files", "*.txt")), initialfile="resolver-log.log")
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(log_content)
                self.log(f"✅ Log saved to {filename}")
            except Exception as e:
                self.log(f"❌ Failed to save log: {e}")

    def view_resolved_requirements(self):
        if not self.resolved_reqs:
            return

        view_window = tk.Toplevel(self)
        view_window.title("Resolved Requirements")
        view_window.geometry("400x500")

        req_text = scrolledtext.ScrolledText(view_window, wrap=tk.WORD, height=15)
        req_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        req_content = ""
        for package, version in self.resolved_reqs.items():
            line = f"{package}=={version}\n"
            req_content += line
            req_text.insert(tk.END, line)
        req_text.configure(state="disabled")

        def save_reqs_from_view():
            filename = filedialog.asksaveasfilename(title="Save Resolved Requirements", defaultextension=".txt", filetypes=(("Requirements files", "*.txt"), ("All files", "*.*")), initialfile="requirements.resolved.txt")
            if filename:
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(req_content)
                    self.log(f"✅ Resolved file saved to {filename}")
                except Exception as e:
                    self.log(f"❌ Failed to save file: {e}")
                finally:
                    view_window.destroy()

        save_button = ttk.Button(view_window, text="Save to File...", command=save_reqs_from_view)
        save_button.pack(pady=10)

    def clean_cache(self):
        self.log("\n--- Cleaning Test Environment Cache ---")
        self.resolve_button.config(state="disabled")
        self.clean_cache_button.config(state="disabled")
        self.view_reqs_button.config(state="disabled")
        
        # The clean function in the backend doesn't exist, so this is illustrative
        self.log("Cache cleaning functionality would run here.")
        
        self.after(2000, lambda: self.resolve_button.config(state="normal"))
        self.after(2000, lambda: self.clean_cache_button.config(state="normal"))

    def start_resolution(self):
        if not self.file_list:
            self.log("❌ Please add at least one requirements file.")
            return

        self.resolve_button.config(state="disabled")
        self.clean_cache_button.config(state="disabled")
        self.view_reqs_button.config(state="disabled")
        self.resolved_reqs = {}
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")
        self.log("--- Starting Requirements Resolution ---")

        # Find the enum member that matches the selected string value
        selected_algo_str = self.algorithm_var.get()
        selected_algorithm = next((algo for algo in Algorithm if str(algo) == selected_algo_str), Algorithm.GREEDY)

        threading.Thread(
            target=self.backend.resolve_dependencies,
            kwargs={
                "files": self.file_list,
                "log_queue": self.log_queue,
                "algorithm": selected_algorithm,
                "python_version": self.python_version_var.get(),
                "install_in_env": self.install_var.get(),
            },
            daemon=True,
        ).start()