from pathlib import Path
import subprocess, sys
root=Path(__file__).resolve().parents[0]
subprocess.check_call([sys.executable, str(root/'code'/'main_rework.py')])
