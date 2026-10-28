"""Render frontend entrypoint; also usable locally."""
import os
import subprocess
import sys

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.address=0.0.0.0", "--server.port=" + os.getenv("PORT", "8501"),
        "--server.headless=true"]))
