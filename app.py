from __future__ import annotations

import datetime as dt
import sqlite3
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
    return render_template("page.html", page=page, revisions=revisions)


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
    return render_template("revision.html", rev=rev)


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
