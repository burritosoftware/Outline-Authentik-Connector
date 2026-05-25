import os
import sys
from pathlib import Path

# Env vars must be set before importing src modules; module-level clients
# read them at construction time.
os.environ.setdefault('OUTLINE_TOKEN', 'test-outline-token')
os.environ.setdefault('OUTLINE_URL', 'https://outline.test')
os.environ.setdefault('OUTLINE_WEBHOOK_SECRET', 'test-webhook-secret')
os.environ.setdefault('AUTHENTIK_URL', 'https://authentik.test')
os.environ.setdefault('AUTHENTIK_TOKEN', 'test-authentik-token')
os.environ.setdefault('AUTO_CREATE_GROUPS', 'False')

SRC = Path(__file__).resolve().parents[1] / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
