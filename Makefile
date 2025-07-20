# Makefile for the requirements Resolver Project

# Use python3 as the default interpreter, default to python3 if not set
PYTHON ?= python3
VENV_DIR := venv
VENV_PYTHON := $(VENV_DIR)/bin/python
SRC_DIR := src/requirements_resolver

# Phony targets are not associated with files.
.PHONY: all help setup reinstall run lint clean _ensure_venv

# Default target executed when you just run `make`
all: help

# Target to display help
help:
	@echo "Makefile for the Requirements Resolver for Python"
	@echo ""
	@echo "Usage:"
	@echo "  make setup        - Creates or updates the virtual environment. Asks to reinstall if it exists."
	@echo "  make reinstall    - Forces a clean re-installation of the environment."
	@echo "  make run          - Runs the application (will prompt to run 'make setup' if not installed)."
	@echo "  make lint         - Runs the linter (will prompt to run 'make setup' if not installed)."
	@echo "  make clean        - Removes the virtual environment and other generated files."
	@echo "  make help         - Shows this help message."

# Target to set up the virtual environment and install dependencies.
# If the environment exists, it will ask the user before reinstalling.
setup:
	@if [ -d "$(VENV_DIR)" ]; then \
		echo "--- Virtual environment already exists. ---"; \
		read -p "Do you want to remove it and reinstall? (y/N) " choice; \
		case "$$choice" in \
			y|Y ) \
				$(MAKE) reinstall; \
				;; \
			* ) \
				echo "--- Updating existing environment. ---"; \
				$(MAKE) _install; \
				;; \
		esac; \
	else \
		$(MAKE) _install; \
	fi

# New target to explicitly and non-interactively reinstall
reinstall: clean _install
	@echo "\n--- Re-installation complete. ---"

# This is an internal target to perform the installation steps
_install: pyproject.toml
	@echo "--- Creating virtual environment in $(VENV_DIR) ---"
	test -d "$(VENV_DIR)" || $(PYTHON) -m venv $(VENV_DIR)
	@echo "--- Installing dependencies and project from pyproject.toml ---"
	. $(VENV_DIR)/bin/activate; \
	$(VENV_PYTHON) -m pip install --upgrade pip; \
	$(VENV_PYTHON) -m pip install -e ".[dev]";
	@echo "\n--- Checking for Tkinter ---"
	@if ! $(VENV_PYTHON) -c 'import tkinter' 2>/dev/null; then \
		echo "\n[ERROR] Tkinter not found in the Python environment."; \
		echo "This is a system-level requirements that must be installed before running 'make setup'."; \
		echo "For Debian/Ubuntu, run: sudo apt-get install python3-tk"; \
		echo "For Fedora, run: sudo dnf install python3-tkinter"; \
		echo "After installing it, you MUST run 'make reinstall'."; \
		exit 1; \
	else \
		echo "Tkinter is available."; \
	fi

# This is a non-interactive check to ensure the venv exists before running
_ensure_venv:
	@if [ ! -f "$(VENV_DIR)/bin/activate" ]; then \
		echo "[ERROR] Virtual environment not found. Please run 'make setup' first."; \
		exit 1; \
	fi

# Target to run the application using the installed entry point
run: _ensure_venv
	@echo "--- Starting requirements Resolver ---"
	. $(VENV_DIR)/bin/activate; requirements-resolver

# Target to run the linter
lint: _ensure_venv
	@echo "--- Running linter (flake8) ---"
	. $(VENV_DIR)/bin/activate; flake8 $(SRC_DIR)

# Target to clean up the project directory
clean:
	@echo "--- Cleaning up ---"
	rm -rf $(VENV_DIR)
	rm -f requirements.merged.txt
	rm -rf src/requirements_resolver.egg-info
	rm -rf build dist
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	@echo "Cleanup complete."

.PHONY: _install