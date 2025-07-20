# 🔧 Requirements Resolver

> Effortlessly merge and resolve Python dependencies from two `requirements.txt` files via a sleek GUI or CLI tool.


<p align="left">
  <a href="https://pypi.org/project/requirements-resolver/">
    <img alt="PyPI Version" src="https://img.shields.io/pypi/v/requirements-resolver.svg">
  </a>
  <a href="https://www.python.org/downloads/release/python-380/">
    <img alt="Python 3.8+" src="https://img.shields.io/badge/python-3.8%2B-blue.svg">
  </a>
  <a href="https://github.com/ruslanmv/requirements-resolver/blob/master/LICENSE">
    <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  </a>
  <a href="https://github.com/ruslanmv/requirements-resolver/actions/workflows/ci.yml">
    <img alt="Build Status" src="https://github.com/ruslanmv/requirements-resolver/actions/workflows/ci.yml/badge.svg">
  </a>
  <a href="https://coveralls.io/github/ruslanmv/requirements-resolver?branch=master">
    <img alt="Coverage Status" src="https://coveralls.io/repos/github/ruslanmv/requirements-resolver/badge.svg?branch=master">
  </a>
  <a href="https://pepy.tech/project/requirements-resolver">
    <img alt="PyPI Downloads" src="https://pepy.tech/badge/requirements-resolver">
  </a>
  <a href="https://requirements-resolver.readthedocs.io/en/latest/">
    <img alt="Read the Docs" src="https://readthedocs.org/projects/requirements-resolver/badge/?version=latest">
  </a>
</p>

## 🔍 Overview

Requirements Resolver is a production‑ready Python package that:

- **Parses** two separate `requirements.txt` files  
- **Fetches** all available versions from PyPI  
- **Computes** the latest set of compatible versions satisfying both files  
- **Caches** results locally for lightning‑fast subsequent runs  
- **Validates** the merged set in an ephemeral virtual environment  
- **Delivers** both a polished GUI (Tkinter) and a powerful CLI  

Ideal for open‑source projects, CI/CD pipelines, and large‑scale Python deployments.

---

## 🚀 Installation

Ensure you have **Python 3.8+** installed. On Debian/Ubuntu, install Tkinter for GUI support:

```bash
sudo apt-get update
sudo apt-get install python3-tk
````

Then install via `pip`:

```bash
pip install requirements-resolver
```

Or grab the latest source:

```bash
git clone https://github.com/ruslanmv/requirements-resolver.git
cd requirements-resolver
pip install .
```

---

## 🎬 Quickstart

### GUI Mode

```bash
requirements-resolver
```

1. **Browse…** to select your two `requirements.txt` files.
2. Click **Resolve Dependencies**.
3. Watch progress logs and find your `requirements.merged.txt` upon success.

### CLI Mode

```bash
requirements-resolver -f reqs/prod.txt reqs/dev.txt
```

* **Specify output**:

  ```bash
  requirements-resolver -f reqs/prod.txt reqs/dev.txt -o requirements.final.txt
  ```

---

## 🛠 Features

* **Dual Interfaces**: Tkinter‐based GUI + rich CLI
* **PyPI Integration**: Real‑time version lookup
* **Local Caching**: Minimizes API calls for repeat runs
* **Automated Testing**: Leverages `venv` to verify installability
* **Configurable**: Override cache directory, HTTP timeouts, log levels

---

## 🧑‍💻 Development

```bash
git clone https://github.com/ruslanmv.com/requirements-resolver.git
cd requirements-resolver
make setup      # Installs dev dependencies
make run        # Launches GUI in development mode
make lint       # Checks code style (flake8)
make test       # Runs unit tests
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

---

## 📄 Documentation

Full user guide, API reference, and examples are on Read the Docs:
[https://requirements-resolver.readthedocs.io](https://requirements-resolver.readthedocs.io)

---

## ❤️ Contributing & Support

Please ⭐ the repo, file issues, and submit PRs!
For questions or feature requests, open an issue or join our Slack channel.

---

## 📜 License

Distributed under the [MIT License](./LICENSE).
© 2025 ruslanmv.com

