"""Start the backend locally for the manual browser check.

The application never calls load_dotenv, so POSTGRES_* is injected from
backend/.env here. Run with backend/ as the working directory so relative
state paths resolve exactly like the systemd unit in production.

Usage:
    python deploy/checks/serve_backend.py            # http://127.0.0.1:8000
    python deploy/checks/serve_backend.py --port 8001
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import add_backend_to_path, load_postgres_env  # noqa: E402

load_postgres_env()
add_backend_to_path()

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402  (module-level create_app())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    os.chdir(Path(__file__).resolve().parents[2] / "backend")
    print(f"starting backend on http://127.0.0.1:{args.port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
