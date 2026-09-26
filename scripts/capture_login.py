"""Open a browser on the running app, wait for a manual login, and save the session.

The saved Playwright storage state (.auth/state.json) lets scripted browser checks
reuse the session. It contains the ChurchTools login token: keep it local and
delete it when done (mise run login-clear).

Usage: mise run login   (app must be running, e.g. mise run run)
"""

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP_URL = os.environ.get("APP_URL", "http://localhost:5005")
STATE_PATH = Path(os.environ.get("AUTH_STATE", ".auth/state.json"))
COOKIE_NAME = "login_token"
TIMEOUT_SECONDS = 300


def main() -> int:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(APP_URL)
        print(f"Bitte im Browserfenster einloggen ({APP_URL}) ...")

        deadline = time.monotonic() + TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if any(c["name"] == COOKIE_NAME for c in context.cookies()):
                page.wait_for_load_state()
                context.storage_state(path=str(STATE_PATH))
                STATE_PATH.chmod(0o600)
                browser.close()
                print(f"Session gespeichert: {STATE_PATH}")
                return 0
            time.sleep(0.5)

        browser.close()
        print("Kein Login innerhalb von 5 Minuten.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
