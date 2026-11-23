"""Start the packaged dashboard on this computer and open its browser page."""

import os
from pathlib import Path
import sys
from threading import Thread
from time import monotonic, sleep
from urllib.request import urlopen
import webbrowser

from streamlit.web import bootstrap


def open_when_ready(url):
    deadline = monotonic() + 30
    while monotonic() < deadline:
        try:
            with urlopen(f"{url}/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            sleep(.25)


def main():
    bundled_app = Path(__file__).resolve().with_name("app.py")
    install_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else bundled_app.parent
    os.environ.setdefault("MES_DB_PATH", str(install_dir / "data" / "mes.sqlite3"))
    flags = {
        "global.developmentMode": False,
        "server.address": "127.0.0.1",
        "server.port": 8501,
        "server.headless": True,
        "server.fileWatcherType": "none",
        "browser.gatherUsageStats": False,
    }
    bootstrap.load_config_options(flags)
    if "--no-browser" not in sys.argv[1:]:
        Thread(target=open_when_ready, args=("http://127.0.0.1:8501",), daemon=True).start()
    bootstrap.run(str(bundled_app), False, [], flags)


if __name__ == "__main__":
    main()
