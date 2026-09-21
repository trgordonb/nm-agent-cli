import sys
from pathlib import Path

# Make repo-root modules (tools, alt-main helpers) importable under pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
