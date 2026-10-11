"""Owned QA harness: no credentials/providers, all temp files remain owned."""
import os
import sys
import tempfile
from pathlib import Path

root = Path('/tmp/visionflow-live-review-1-f5aeae3')
tempfile.tempdir = str(root / 'tmp')
Path(tempfile.tempdir).mkdir(exist_ok=True)
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
