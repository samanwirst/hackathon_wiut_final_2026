"""Run the public LIVE Camera + Judges app.

    cd services/api
    VISIONFLOW_DEMO_PIN=... .venv/bin/python -m app.live --port 8001

This serves ONLY the authenticated live endpoints (never the legacy upload/control
API). Put the public HTTPS tunnel in front of this port.
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="VisionFlow Live app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    # proxy-headers lets uvicorn honor X-Forwarded-* from the cloudflared tunnel.
    uvicorn.run(
        "app.live.app:app",
        host=args.host,
        port=args.port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        workers=1,
    )


if __name__ == "__main__":
    main()
