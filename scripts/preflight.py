import sys
import importlib
import os
from pathlib import Path

REQUIRED_PYTHON_MAJOR = 3
REQUIRED_PYTHON_MINOR = 11
REQUIRED_PACKAGES = ["streamlit", "pandas", "numpy"]
OPTIONAL_PACKAGES = ["faiss", "faiss-cpu", "sentence_transformers", "fpdf"]

# --- Data files from config ---
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "config.py")
DATA_FILES = {}
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if "CLEAN_DATA_PARQUET" in line or "EMBEDDINGS_PATH" in line or "FAISS_INDEX_PATH" in line:
                parts = line.split("=")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().replace("'","").replace('"',"").replace("Path(","").replace(")","")
                    DATA_FILES[key] = val
except Exception as e:
    print(f"[ERROR] Could not read config.py: {e}")
    sys.exit(1)

# --- Python version check ---
if sys.version_info.major != REQUIRED_PYTHON_MAJOR or sys.version_info.minor != REQUIRED_PYTHON_MINOR:
    print(f"[ERROR] Python 3.11 is required. Current version: {sys.version}")
    sys.exit(1)

# --- Required packages ---
missing = []
for pkg in REQUIRED_PACKAGES:
    try:
        importlib.import_module(pkg)
    except ImportError:
        missing.append(pkg)
if missing:
    print(f"[ERROR] Missing required packages: {', '.join(missing)}")
    sys.exit(1)

# --- Optional packages ---
fallback_modes = []
for pkg in OPTIONAL_PACKAGES:
    try:
        importlib.import_module(pkg)
    except ImportError:
        print(f"[WARNING] Optional package '{pkg}' not found. Fallback mode will be used.")
        fallback_modes.append(pkg)

# --- Data files check ---
for key, path in DATA_FILES.items():
    full_path = os.path.abspath(os.path.join(os.path.dirname(CONFIG_PATH), "..", path))
    if not os.path.exists(full_path):
        if key == "FAISS_INDEX_PATH":
            print(f"[WARNING] FAISS index file not found: {full_path}. Fallback will be used.")
            fallback_modes.append("faiss_index")
        else:
            print(f"[ERROR] Required data file not found: {full_path}")
            sys.exit(1)

print("[OK] Preflight check passed.")
if fallback_modes:
    print(f"[INFO] Fallback modes active: {', '.join(fallback_modes)}")
else:
    print("[INFO] All optional features available.")
