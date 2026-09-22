import sys
from pathlib import Path

# Make repo-root modules (tools, main.py helpers) importable under pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
