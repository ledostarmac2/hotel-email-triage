from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn

from outlook_dashboard.config import get_settings
from outlook_dashboard.main import app


def main() -> None:
    settings = get_settings()
    url = f"http://{settings.app_host}:{settings.app_port}"

    def open_browser() -> None:
        time.sleep(1.2)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
