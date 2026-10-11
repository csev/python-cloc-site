#!/usr/bin/env python3
"""Python for Everybody with AI — CLOC mini-site.

One process, two jobs for UTM tracking:
  - a visit to the home page records utm_* query parameters
  - /utm-live shows the counts

Storage is the SQLite file utm.sqlite beside this script.

Optional password for viewing results (tracking itself is never passworded):
  Create a sibling file named utm-password.txt containing only the password.
  While that file exists and is non-empty, /utm-live asks before showing
  the table. Delete the file to leave viewing open. Do not commit it.

Run locally:
  python3 app.py

The WSGI callable is `application`. When this file is executed as a CGI
script (GATEWAY_INTERFACE is set), it serves the request and exits.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import html
import mimetypes
import os
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parent
DB_FILE = ROOT / "utm.sqlite"
PASSWORD_FILE = ROOT / "utm-password.txt"
MAX_CODES = 250
UTM_NONE = "(none)"
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
COOKIE_NAME = "utm_live_ok"

PAGES = {
    "/": ROOT / "index.html",
    "/index.html": ROOT / "index.html",
    "/about.html": ROOT / "about.html",
}
STATIC_FILES = {
    "/styles.css": ROOT / "styles.css",
    "/script.js": ROOT / "script.js",
    "/favicon.ico": ROOT / "favicon.ico",
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=3, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS utm (
            utm_string TEXT PRIMARY KEY NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            first_use TEXT NOT NULL,
            last_use TEXT NOT NULL
        )
        """
    )
    return conn


def query_params(environ) -> dict[str, str]:
    parsed = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def form_params(environ) -> dict[str, str]:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    length = max(0, min(length, 4096))
    if length == 0:
        return {}
    raw = environ["wsgi.input"].read(length).decode("utf-8", "replace")
    parsed = parse_qs(raw, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def normalize_utm(params: dict[str, str]) -> str:
    """Fold keys and values to lowercase so UTM_SOURCE=Email matches utm_source=email.

    A bare utm parameter is an alias for utm_source.
    """
    lower = {str(key).lower(): value for key, value in params.items()}
    if "utm" in lower and "utm_source" not in lower:
        lower["utm_source"] = lower["utm"]

    parts = []
    for key in UTM_KEYS:
        if key not in lower:
            continue
        value = str(lower[key]).strip().lower()
        if value == "":
            continue
        # Keep values short so the table cannot be stuffed with huge strings.
        if len(value) > 200:
            value = value[:200]
        parts.append(f"{key}={value}")
    return "&".join(parts)


def prune(conn: sqlite3.Connection) -> None:
    """Cap real UTM codes. The (none) counter is never pruned."""
    count = conn.execute(
        "SELECT COUNT(*) FROM utm WHERE utm_string != ?",
        (UTM_NONE,),
    ).fetchone()[0]
    if count <= MAX_CODES:
        return
    extra = count - MAX_CODES
    conn.execute(
        """
        DELETE FROM utm WHERE utm_string IN (
            SELECT utm_string FROM utm
            WHERE utm_string != ?
            ORDER BY last_use ASC, utm_string ASC
            LIMIT ?
        )
        """,
        (UTM_NONE, extra),
    )


def track(params: dict[str, str]) -> None:
    utm = normalize_utm(params) or UTM_NONE
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT count FROM utm WHERE utm_string = ?",
            (utm,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE utm SET count = count + 1, last_use = ? WHERE utm_string = ?",
                (now, utm),
            )
        else:
            conn.execute(
                """
                INSERT INTO utm (utm_string, count, first_use, last_use)
                VALUES (?, 1, ?, ?)
                """,
                (utm, now, now),
            )
            if utm != UTM_NONE:
                prune(conn)
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
    finally:
        conn.close()


def expected_password() -> str | None:
    if not PASSWORD_FILE.is_file():
        return None
    try:
        password = PASSWORD_FILE.read_text(encoding="utf-8")
    except OSError:
        return None
    password = password.strip()
    return password or None


def password_token(password: str) -> str:
    return hmac.new(password.encode("utf-8"), b"utm-live", hashlib.sha256).hexdigest()


def cookie_value(environ, name: str) -> str:
    raw = environ.get("HTTP_COOKIE", "")
    for part in raw.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return ""


def authorized(environ, password: str | None) -> bool:
    if password is None:
        return True
    expected = password_token(password)
    got = cookie_value(environ, COOKIE_NAME)
    if len(got) != len(expected):
        return False
    return hmac.compare_digest(got, expected)


def cookie_header(environ, password: str) -> str:
    secure = "; Secure" if environ.get("wsgi.url_scheme") == "https" else ""
    return (
        f"{COOKIE_NAME}={password_token(password)}; HttpOnly; SameSite=Lax; Path=/{secure}"
    )


def h(value) -> str:
    return html.escape(str(value), quote=True)


def respond(start_response, status, body: bytes, content_type: str, extra=None):
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
    ]
    if extra:
        headers.extend(extra)
    start_response(status, headers)
    return [body]


def file_response(start_response, path: Path, environ):
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if content_type.startswith("text/") or path.suffix in {".js", ".css"}:
        content_type += "; charset=utf-8"
    body = path.read_bytes()
    if environ.get("REQUEST_METHOD", "GET").upper() == "HEAD":
        start_response(
            "200 OK",
            [
                ("Content-Type", content_type),
                ("Content-Length", str(len(body))),
            ],
        )
        return [b""]
    return respond(start_response, "200 OK", body, content_type)


def asset_file(url_path: str) -> Path | None:
    if not url_path.startswith("/assets/"):
        return None
    candidate = (ROOT / url_path.lstrip("/")).resolve()
    try:
        candidate.relative_to((ROOT / "assets").resolve())
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


def html_page(start_response, title: str, body: str, extra_headers=None):
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>{h(title)}</title>
</head>
<body>
{body}
</body>
</html>
"""
    headers = [("Cache-Control", "no-store")]
    if extra_headers:
        headers.extend(extra_headers)
    return respond(
        start_response,
        "200 OK",
        document.encode("utf-8"),
        "text/html; charset=utf-8",
        headers,
    )


def login_page(start_response, error: str):
    message = f"<p>{h(error)}</p>" if error else ""
    body = f"""  <p><a href="/">Home</a></p>
  <h1>UTM Live</h1>
  {message}
  <form method="post" action="">
    <label>Password <input type="password" name="password" autofocus></label>
    <button type="submit">View</button>
  </form>
"""
    return html_page(start_response, "UTM Live", body)


def dashboard(start_response):
    conn = connect()
    try:
        total_codes = conn.execute(
            "SELECT COUNT(*) FROM utm WHERE utm_string != ?",
            (UTM_NONE,),
        ).fetchone()[0]
        total_hits = conn.execute(
            "SELECT COALESCE(SUM(count), 0) FROM utm"
        ).fetchone()[0]
        none_row = conn.execute(
            "SELECT count FROM utm WHERE utm_string = ?",
            (UTM_NONE,),
        ).fetchone()
        none_hits = int(none_row["count"]) if none_row else 0
        rows = conn.execute(
            """
            SELECT utm_string, count, first_use, last_use
            FROM utm
            ORDER BY CASE WHEN utm_string = ? THEN 0 ELSE 1 END,
                     last_use DESC, count DESC
            """,
            (UTM_NONE,),
        ).fetchall()
    finally:
        conn.close()

    summary = (
        f"<p>{int(total_codes)} / {int(MAX_CODES)} codes, "
        f"{int(total_hits)} hits ({int(none_hits)} with no UTM). "
        "Times UTC. Cap drops oldest last_use; (none) is never pruned.</p>"
    )
    if not rows:
        table = "<p>No visits yet.</p>"
    else:
        rendered = []
        for row in rows:
            rendered.append(
                "<tr>"
                f"<td><code>{h(row['utm_string'])}</code></td>"
                f"<td>{int(row['count'])}</td>"
                f"<td>{h(row['first_use'])}</td>"
                f"<td>{h(row['last_use'])}</td>"
                "</tr>"
            )
        table = (
            '<table border="1" cellpadding="4" cellspacing="0">'
            "<tr><th>utm_string</th><th>count</th><th>first_use</th><th>last_use</th></tr>"
            + "".join(rendered)
            + "</table>"
        )
    body = f"  <p><a href=\"/\">Home</a></p>\n  <h1>UTM Live</h1>\n  {summary}\n  {table}\n"
    return html_page(start_response, "UTM Live", body)


def utm_live(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    password = expected_password()
    if authorized(environ, password):
        if method not in ("GET", "HEAD"):
            return respond(start_response, "405 Method Not Allowed", b"", "text/plain", [("Allow", "GET, HEAD")])
        return dashboard(start_response)

    error = ""
    if method == "POST":
        got = form_params(environ).get("password", "")
        if hmac.compare_digest(password, got):
            location = environ.get("PATH_INFO") or "/utm-live"
            start_response(
                "303 See Other",
                [
                    ("Location", location),
                    ("Set-Cookie", cookie_header(environ, password)),
                    ("Content-Length", "0"),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [b""]
        error = "Wrong password."
    elif method not in ("GET", "HEAD"):
        return respond(start_response, "405 Method Not Allowed", b"", "text/plain", [("Allow", "GET, HEAD, POST")])
    return login_page(start_response, error)


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO") or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1] or "/"

    if path in ("/", "/index.html"):
        if method not in ("GET", "HEAD"):
            return respond(
                start_response,
                "405 Method Not Allowed",
                b"",
                "text/plain",
                [("Allow", "GET, HEAD")],
            )
        track(query_params(environ))
        return file_response(start_response, PAGES["/"], environ)

    if path in ("/utm-live", "/utm-live.py"):
        return utm_live(environ, start_response)

    page = PAGES.get(path)
    if page is not None and page.is_file():
        if method not in ("GET", "HEAD"):
            return respond(
                start_response,
                "405 Method Not Allowed",
                b"",
                "text/plain",
                [("Allow", "GET, HEAD")],
            )
        return file_response(start_response, page, environ)

    static = STATIC_FILES.get(path)
    if static is not None and static.is_file():
        if method not in ("GET", "HEAD"):
            return respond(
                start_response,
                "405 Method Not Allowed",
                b"",
                "text/plain",
                [("Allow", "GET, HEAD")],
            )
        return file_response(start_response, static, environ)

    asset = asset_file(path if path.startswith("/") else f"/{path}")
    if asset is not None:
        if method not in ("GET", "HEAD"):
            return respond(
                start_response,
                "405 Method Not Allowed",
                b"",
                "text/plain",
                [("Allow", "GET, HEAD")],
            )
        return file_response(start_response, asset, environ)

    body = b"Not found\n"
    return respond(start_response, "404 Not Found", body, "text/plain; charset=utf-8")


def main() -> None:
    if os.environ.get("GATEWAY_INTERFACE"):
        from wsgiref.handlers import CGIHandler

        CGIHandler().run(application)
        return

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    with make_server(host, port, application) as httpd:
        print(f"Serving http://{host}:{port}/", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
