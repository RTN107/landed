"""Google Sheets: OAuth desktop flow, read the Quote DB tab, append rows.

The tab is addressed by name, never by index. The app only ever appends.
"""

from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import CREDENTIALS_FILE, SCOPES, SHEET_COLUMNS, SHEET_ID, TAB_NAME, TOKEN_FILE

_RANGE = f"'{TAB_NAME}'!A:H"


def _credentials() -> Credentials:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(f"Google OAuth client file not found at {CREDENTIALS_FILE}")
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    return creds


def _service():
    if not SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID is empty. Set it in the .env file at the project root.")
    return build("sheets", "v4", credentials=_credentials(), cache_discovery=False)


def read_all() -> list[dict[str, str]]:
    """Every data row of Quote DB as a dict keyed by the verbatim column headers."""
    resp = (
        _service()
        .spreadsheets()
        .values()
        .get(spreadsheetId=SHEET_ID, range=_RANGE)
        .execute()
    )
    values = resp.get("values", [])
    if not values:
        raise RuntimeError(f"The '{TAB_NAME}' tab is empty; expected a header row.")
    header = [h.strip() for h in values[0]]
    if header[: len(SHEET_COLUMNS)] != SHEET_COLUMNS:
        raise RuntimeError(
            f"Unexpected header row in '{TAB_NAME}'.\nExpected: {SHEET_COLUMNS}\nFound:    {header}"
        )
    rows = []
    for raw in values[1:]:
        if not any(cell.strip() for cell in raw):
            continue
        padded = list(raw) + [""] * (len(SHEET_COLUMNS) - len(raw))
        rows.append(dict(zip(SHEET_COLUMNS, padded[: len(SHEET_COLUMNS)])))
    return rows


def append_rows(rows: list[list]) -> dict:
    """Append rows below the existing data. RAW input keeps every string verbatim."""
    resp = (
        _service()
        .spreadsheets()
        .values()
        .append(
            spreadsheetId=SHEET_ID,
            range=_RANGE,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        )
        .execute()
    )
    return resp.get("updates", {})
