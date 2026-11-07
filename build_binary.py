'''
Courtney Lin, Nicholas Marden
Task-4: build the executable.

Creates one standalone executable of main.py with PyInstaller. The result runs
on a machine with no Python and no pip install -r requirements.txt.

    python3 build_binary.py            # folder build   -> dist/SecureSoftwareProcess/
    python3 build_binary.py --onefile  # single file    -> dist/SecureSoftwareProcess(.exe)
    python3 build_binary.py --dry-run  # print the PyInstaller command, build nothing

Windows note: use `pyinstaller` from the same venv as torch/transformers, and run
the build on Windows to get a .exe. PyInstaller cannot cross-compile.
'''

import argparse
import os
import subprocess
import sys

APP_NAME = "SecureSoftwareProcess"
ENTRY_POINT = "main.py"


def _check(module_name, pip_name=None):
    # PyInstaller and the project's own dependencies must be installed first.
    try:
        __import__(module_name)
    except ImportError:
        sys.exit(f"Missing '{module_name}'. Run: pip install {pip_name or module_name}")


def build_command(onefile=False):
    # --collect-all grabs the data files, metadata and dynamic submodules that
    # transformers and torch load at runtime; without them the binary starts but
    # fails the first time it touches the model.
    cmd = [
        sys.executable, "-m", "PyInstaller",
        # The three task packages are imported from the project root, so
        # PyInstaller needs the root on its search path to find them.
        "--paths", os.path.abspath("."),
        "--noconfirm",            # overwrite an existing dist/ without asking
        "--clean",                # ignore the PyInstaller cache
        "--name", APP_NAME,
        "--onefile" if onefile else "--onedir",
        # Nothing to collect for pypdf, but its submodules are imported lazily.
        "--collect-submodules", "pypdf",
        "--collect-submodules", "yaml",
        # torch / transformers / accelerate / tokenizers / safetensors need both
        # their Python modules and their data + metadata files.
        "--collect-all", "torch",
        "--collect-all", "transformers",
        "--collect-all", "accelerate",
        "--collect-all", "tokenizers",
        "--collect-all", "safetensors",
        "--collect-all", "huggingface_hub",
        "--collect-all", "pandas",
        # Parsed at runtime by transformers' model loader.
        "--copy-metadata", "torch",
        "--copy-metadata", "transformers",
        "--copy-metadata", "tokenizers",
        "--copy-metadata", "huggingface_hub",
        # Imported by name only (string lookups inside torch/transformers).
        "--hidden-import", "torch",
        "--hidden-import", "transformers",
        "--hidden-import", "sentencepiece",
        "--hidden-import", "protobuf",
        "--hidden-import", "google.protobuf",
        "--hidden-import", "pandas._libs.tslibs.base",
        # Console app: keep stdout/stderr so the progress lines are visible.
        "--console",
        ENTRY_POINT,
    ]
    return cmd


def main():
    parser = argparse.ArgumentParser(description="Build the Task-4 executable.")
    parser.add_argument("--onefile", action="store_true",
                        help="single self-extracting file (slower start-up)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the PyInstaller command and exit")
    args = parser.parse_args()

    if not os.path.isfile(ENTRY_POINT):
        sys.exit(f"Run this from the project root; {ENTRY_POINT} not found.")

    cmd = build_command(onefile=args.onefile)

    if args.dry_run:
        print(" ".join(cmd))
        return 0

    # Checked only for a real build so --dry-run works anywhere.
    _check("PyInstaller", "pyinstaller")
    _check("torch")
    _check("transformers")
    _check("pypdf")
    _check("yaml", "PyYAML")
    _check("pandas")

    print(f"Building {APP_NAME} with PyInstaller ...")
    print(" ".join(cmd[:6]), "...")
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        sys.exit(f"PyInstaller failed with exit code {completed.returncode}")

    target = os.path.join("dist",
                          APP_NAME + (".exe" if os.name == "nt" else ""))
    if os.path.isdir(os.path.join("dist", APP_NAME)):
        target = os.path.join("dist", APP_NAME, APP_NAME)
    print(f"\nBuilt: {target}")
    print("Run it with the three PDFs, exactly like main.py:")
    print(f"    {target} docker-cis-v0.pdf docker-cis-v1.pdf docker-cis-v2.pdf")
    print("The Gemma-3-1B weights are NOT bundled: the first run still downloads")
    print("them from Hugging Face (~2 GB) using HF_TOKEN or `huggingface-cli login`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
