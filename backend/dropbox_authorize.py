#!/usr/bin/env python3
"""One-time Dropbox authorisation: trade a browser code for a refresh token.

Dropbox stopped issuing long-lived access tokens; the ones from the App
Console "Generate" button expire after about four hours.  Running this once
yields a refresh token that does not expire, which the backend exchanges for
fresh access tokens on demand.

    python dropbox_authorize.py

Reads DROPBOX_APP_KEY / DROPBOX_APP_SECRET from the environment or backend
``.env``, and prints the DROPBOX_REFRESH_TOKEN line to add to that file.
"""
from __future__ import annotations

import sys
import urllib.parse

import httpx

from app.config import get_settings

AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"
TOKEN_URL = "https://api.dropbox.com/oauth2/token"


def main() -> int:
    settings = get_settings()
    app_key = settings.DROPBOX_APP_KEY
    app_secret = settings.DROPBOX_APP_SECRET

    if not app_key or not app_secret:
        print("DROPBOX_APP_KEY and DROPBOX_APP_SECRET must be set in backend/.env")
        return 1

    params = urllib.parse.urlencode(
        {
            "client_id": app_key,
            "response_type": "code",
            # The flag that makes Dropbox return a refresh token at all.
            "token_access_type": "offline",
        }
    )
    print("1. Open this URL, sign in, and click Allow:\n")
    print(f"   {AUTHORIZE_URL}?{params}\n")
    print("2. Dropbox shows an authorisation code. Paste it below.\n")

    code = input("   Code: ").strip()
    if not code:
        print("No code entered.")
        return 1

    response = httpx.post(
        TOKEN_URL,
        data={"grant_type": "authorization_code", "code": code},
        auth=(app_key, app_secret),
        timeout=30.0,
    )

    if response.status_code != 200:
        print(f"\nExchange failed ({response.status_code}): {response.text[:300]}")
        print("Codes are single-use and short-lived — re-run to get a fresh one.")
        return 1

    payload = response.json()
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        print("\nNo refresh_token returned. Confirm token_access_type=offline was used.")
        return 1

    print("\nSuccess. Put this in backend/.env and restart the backend:\n")
    print(f"DROPBOX_REFRESH_TOKEN={refresh_token}\n")
    print("DROPBOX_ACCESS_TOKEN is no longer needed and can be left blank.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
