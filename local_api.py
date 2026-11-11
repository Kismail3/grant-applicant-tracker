"""Session-isolated local API adapter for Streamlit Community Cloud.

Provides the same GET/PATCH interface the dashboard uses, but reads SQLite
read-only and keeps demo status changes in Streamlit session_state only.
No shared database writes or background FastAPI service are needed.
"""
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlparse
import streamlit as st

DB_PATH = Path(__file__).resolve().parent / "federal_grants.db"

class RequestException(Exception):
    pass

class Response:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.text = str(data)

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RequestException(f"HTTP {self.status_code}: {self.text}")


def _connection():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _overrides():
    return st.session_state.setdefault("demo_status_overrides", {})


def _history_overrides():
    return st.session_state.setdefault("demo_history_overrides", {})


def _apply_status(row):
    record = dict(row)
    record["status"] = _overrides().get(record["application_id"], record["status"])
    return record


def get(url, timeout=10):
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    with _connection() as conn:
        if path == "applications":
            rows = conn.execute("""
                SELECT a.application_id, ap.organization_name, g.grant_program_name,
                       r.reviewer_name, a.submission_date, a.requested_amount,
                       a.status, a.priority
                FROM applications a
                JOIN applicants ap ON a.applicant_id=ap.applicant_id
                JOIN grants g ON a.grant_number=g.grant_number
                LEFT JOIN reviewers r ON a.reviewer_id=r.reviewer_id
                ORDER BY a.application_id
            """).fetchall()
            return Response([_apply_status(row) for row in rows])

        if len(parts) in (2, 3) and parts[0] == "applications" and parts[1].isdigit():
            app_id = int(parts[1])
            if len(parts) == 3 and parts[2] == "history":
                exists = conn.execute("SELECT 1 FROM applications WHERE application_id=?", (app_id,)).fetchone()
                if not exists:
                    return Response({"detail": "Application not found"}, 404)
                rows = conn.execute("""
                    SELECT application_id, old_status, new_status, changed_by, notes
                    FROM status_history WHERE application_id=? ORDER BY history_id
                """, (app_id,)).fetchall()
                history = [dict(row) for row in rows] + _history_overrides().get(app_id, [])
                return Response({"application_id": app_id, "history": history})
            if len(parts) == 2:
                row = conn.execute("""
                    SELECT a.application_id, ap.organization_name, a.grant_number,
                           g.grant_program_name, a.reviewer_id, r.reviewer_name,
                           a.submission_date, a.requested_amount, a.status, a.priority
                    FROM applications a
                    JOIN applicants ap ON a.applicant_id=ap.applicant_id
                    JOIN grants g ON a.grant_number=g.grant_number
                    LEFT JOIN reviewers r ON a.reviewer_id=r.reviewer_id
                    WHERE a.application_id=?
                """, (app_id,)).fetchone()
                return Response(_apply_status(row)) if row else Response({"detail": "Application not found"}, 404)
    return Response({"detail": "Not found"}, 404)


def patch(url, json=None, timeout=10):
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) != 3 or parts[0] != "applications" or not parts[1].isdigit() or parts[2] != "status":
        return Response({"detail": "Not found"}, 404)
    app_id = int(parts[1])
    payload = json or {}
    with _connection() as conn:
        row = conn.execute("SELECT status, reviewer_id FROM applications WHERE application_id=?", (app_id,)).fetchone()
    if row is None:
        return Response({"detail": "Application not found"}, 404)
    if row["reviewer_id"] != payload.get("reviewer_id"):
        return Response({"detail": "Reviewer is not assigned to this application"}, 403)
    old_status = _overrides().get(app_id, row["status"])
    new_status = payload.get("new_status")
    allowed = {"Submitted": {"Under Review"}, "Under Review": {"Approved", "Rejected"}, "Approved": set(), "Rejected": set()}
    if new_status not in allowed.get(old_status, set()):
        return Response({"detail": "Invalid status transition"}, 409)
    _overrides()[app_id] = new_status
    _history_overrides().setdefault(app_id, []).append({
        "application_id": app_id,
        "old_status": old_status,
        "new_status": new_status,
        "changed_by": payload["reviewer_id"],
        "notes": payload.get("notes", ""),
    })
    return Response({"application_id": app_id, "old_status": old_status,
                     "new_status": new_status, "message": "Demo status updated for this browser session"})
