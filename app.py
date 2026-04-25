from __future__ import annotations

import datetime as dt
import re
import sqlite3
from html import escape
from pathlib import Path
from typing import Any

from flask import Flask, abort, flash, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "wiki.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "local-dev-secret"


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with db_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE
            );
            """
        )


def slugify(title: str) -> str:
    return title.strip().replace(" ", "_")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _render_inline(text: str) -> str:
    rendered = escape(text)
    rendered = re.sub(r"\[br\]", "<br>", rendered)
    rendered = re.sub(r"'''(.*?)'''", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"''(.*?)''", r"<em>\1</em>", rendered)
    rendered = re.sub(r"~~(.*?)~~", r"<del>\1</del>", rendered)
    rendered = re.sub(r"__(.*?)__", r"<u>\1</u>", rendered)

    def _wikilink(match: re.Match[str]) -> str:
        target, text = match.group(1), match.group(2)
        label = text if text else target
        if target.startswith(("http://", "https://")):
            return f'<a href="{target}" target="_blank" rel="noopener">{label}</a>'
        return f'<a href="/w/{slugify(target)}">{label}</a>'

    rendered = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", _wikilink, rendered)
    rendered = re.sub(
        r"\[\[([^\]|]+)\]\]",
        lambda m: f'<a href="/w/{slugify(m.group(1))}">{m.group(1)}</a>' if not m.group(1).startswith(("http://", "https://")) else f'<a href="{m.group(1)}" target="_blank" rel="noopener">{m.group(1)}</a>',
        rendered,
    )

    rendered = re.sub(
        r"\[math\((.*?)\)\]",
        lambda m: f'<span class="nm-math" data-expr="{escape(m.group(1))}"></span>',
        rendered,
    )
    return rendered


def render_namumark(text: str) -> str:
    lines = text.splitlines()
    html: list[str] = []
    in_ul = False
    in_ol = False
    in_code = False
    code_buffer: list[str] = []

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            html.append("</ul>")
            in_ul = False
        if in_ol:
            html.append("</ol>")
            in_ol = False

    for raw in lines:
        line = raw.rstrip("\n")

        if line.startswith("{{{"):
            close_lists()
            in_code = True
            code_buffer = []
            continue

        if in_code:
            if line.endswith("}}}"):
                in_code = False
                html.append(f"<pre><code>{escape(chr(10).join(code_buffer))}</code></pre>")
            else:
                code_buffer.append(line)
            continue

        if not line.strip():
            close_lists()
            html.append("<p></p>")
            continue

        heading = re.match(r"^(={1,6})\s*(.*?)\s*\1$", line)
        if heading:
            close_lists()
            level = len(heading.group(1))
            html.append(f"<h{level}>{_render_inline(heading.group(2))}</h{level}>")
            continue

        if line.lstrip().startswith("* "):
            if in_ol:
                html.append("</ol>")
                in_ol = False
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            html.append(f"<li>{_render_inline(line.lstrip()[2:])}</li>")
            continue

        ordered = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if ordered:
            if in_ul:
                html.append("</ul>")
                in_ul = False
            if not in_ol:
                html.append("<ol>")
                in_ol = True
            html.append(f"<li>{_render_inline(ordered.group(2))}</li>")
            continue

        if line.startswith(">"):
            close_lists()
            html.append(f"<blockquote>{_render_inline(line[1:].strip())}</blockquote>")
            continue

        close_lists()
        html.append(f"<p>{_render_inline(line)}</p>")

    close_lists()
    if in_code:
        html.append(f"<pre><code>{escape(chr(10).join(code_buffer))}</code></pre>")
    return "\n".join(html)


@app.route("/")
def home() -> str:
    with db_conn() as conn:
        pages = conn.execute(
            "SELECT title, slug, updated_at FROM pages ORDER BY updated_at DESC"
        ).fetchall()
    return render_template("home.html", pages=pages)


@app.route("/w/<path:slug>", methods=["GET", "POST"])
def wiki_page(slug: str) -> str:
    with db_conn() as conn:
        page = conn.execute(
            "SELECT id, title, slug, content, updated_at FROM pages WHERE slug = ?", (slug,)
        ).fetchone()

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            if not title:
                flash("제목은 필수입니다.")
                return redirect(url_for("wiki_page", slug=slug))

            if page is None:
                created = now_iso()
                cur = conn.execute(
                    "INSERT INTO pages(slug, title, content, created_at, updated_at) VALUES(?,?,?,?,?)",
                    (slugify(title), title, content, created, created),
                )
                page_id = cur.lastrowid
            else:
                conn.execute(
                    "UPDATE pages SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                    (title, content, now_iso(), page["id"]),
                )
                page_id = page["id"]

            conn.execute(
                "INSERT INTO revisions(page_id, content, created_at) VALUES(?,?,?)",
                (page_id, content, now_iso()),
            )
            conn.commit()
            flash("저장되었습니다.")
            return redirect(url_for("wiki_page", slug=slugify(title)))

    if page is None:
        return render_template("edit.html", slug=slug, page=None)

    with db_conn() as conn:
        revisions = conn.execute(
            "SELECT id, created_at FROM revisions WHERE page_id = ? ORDER BY id DESC LIMIT 20",
            (page["id"],),
        ).fetchall()
    rendered = render_namumark(page["content"])
    return render_template("page.html", page=page, rendered=rendered, revisions=revisions)


@app.route("/w/<path:slug>/edit", methods=["GET"])
def edit_page(slug: str) -> str:
    with db_conn() as conn:
        page = conn.execute(
            "SELECT id, title, slug, content FROM pages WHERE slug = ?", (slug,)
        ).fetchone()
    return render_template("edit.html", slug=slug, page=page)


@app.route("/revisions/<int:revision_id>")
def revision_detail(revision_id: int) -> str:
    with db_conn() as conn:
        rev = conn.execute(
            """
            SELECT r.id, r.created_at, r.content, p.slug, p.title
            FROM revisions r
            JOIN pages p ON p.id = r.page_id
            WHERE r.id = ?
            """,
            (revision_id,),
        ).fetchone()
    if rev is None:
        abort(404)
    rendered = render_namumark(rev["content"])
    return render_template("revision.html", rev=rev, rendered=rendered)


@app.route("/import", methods=["POST"])
def import_data() -> Any:
    payload = request.get_json(silent=True)
    if not payload or "pages" not in payload:
        return {"error": "Invalid payload"}, 400

    count = 0
    with db_conn() as conn:
        for page in payload["pages"]:
            title = str(page.get("title", "")).strip()
            content = str(page.get("content", "")).strip()
            if not title:
                continue

            slug = slugify(str(page.get("slug") or title))
            existing = conn.execute("SELECT id FROM pages WHERE slug = ?", (slug,)).fetchone()
            timestamp = now_iso()

            if existing:
                page_id = existing["id"]
                conn.execute(
                    "UPDATE pages SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                    (title, content, timestamp, page_id),
                )
            else:
                cur = conn.execute(
                    "INSERT INTO pages(slug, title, content, created_at, updated_at) VALUES(?,?,?,?,?)",
                    (slug, title, content, timestamp, timestamp),
                )
                page_id = cur.lastrowid

            conn.execute(
                "INSERT INTO revisions(page_id, content, created_at) VALUES(?,?,?)",
                (page_id, content, timestamp),
            )
            count += 1

        conn.commit()
    return {"imported": count}


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
