import os
import sys

# Make src/ importable as a top-level package root, mirroring container layout
# (Dockerfile copies src/ to /app and runs `uvicorn connect:app`).
SRC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# The Outline and Authentik clients construct themselves at import time and
# require these to be set. Tests do not make real API calls; placeholders are
# enough to satisfy the constructors.
os.environ.setdefault("OUTLINE_TOKEN", "test-token")
os.environ.setdefault("OUTLINE_URL", "https://example.invalid")
os.environ.setdefault("AUTHENTIK_TOKEN", "test-token")
os.environ.setdefault("AUTHENTIK_URL", "https://example.invalid")
