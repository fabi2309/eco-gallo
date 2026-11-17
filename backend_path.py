"""Import the backend consistently from launchers."""
import sys
from pathlib import Path


def setup_backend():
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'backend'))
