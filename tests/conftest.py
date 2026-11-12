import os
import tempfile
from pathlib import Path

# Tests never touch the real warehouse: point everything at a throw-away fixture DB.
os.environ["CAMPUSPULSE_DB"] = str(Path(tempfile.mkdtemp()) / "test.duckdb")
