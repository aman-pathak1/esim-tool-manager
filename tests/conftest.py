import sys
from pathlib import Path

# Make sure the repo root (parent of tool_manager/) is on sys.path so
# `import tool_manager` works no matter which directory pytest is
# invoked from.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))