"""
Start the Orion backend.

    python run.py

Listens on all network interfaces so the frontend works from
localhost, this machine's LAN address, or another device.
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
