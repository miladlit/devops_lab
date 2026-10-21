import logging
import os
import time
from contextlib import contextmanager
from datetime import date, datetime, timezone

import psycopg2
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from logging_config import configure_logging

configure_logging()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
READING_STATUSES = ("to_read", "reading", "finished")


@contextmanager
def database():
    # One connection and transaction per operation; always release both.
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"], dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        connect_timeout=5, options="-c statement_timeout=5000",
    )
    try:
        with conn:
            with conn.cursor() as cursor:
                yield cursor
    finally:
        conn.close()


@app.before_request
def log_request():
    g.start_time = time.monotonic()


@app.after_request
def log_response(response):
    logging.info("request", extra={
        "method": request.method, "path": request.path,
        "status": response.status_code,
        "duration": round(time.monotonic() - g.start_time, 4),
    })
    return response


@app.errorhandler(HTTPException)
def handle_http_error(error):
    response = error.get_response()
    response.data = app.json.dumps({"error": error.description})
    response.content_type = "application/json"
    return response


@app.errorhandler(psycopg2.Error)
def handle_database_error(error):
    logging.exception("Database operation failed")
    return jsonify(error="Database unavailable"), 503


@app.errorhandler(Exception)
def handle_exception(error):
    logging.exception("Unhandled request error")
    return jsonify(error="Internal server error"), 500


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/health/db")
def health_db():
    with database() as cursor:
        cursor.execute("SELECT 1 FROM books LIMIT 1")
    return jsonify(status="ok", db="connected")


def book_values():
    data = request.get_json()
    if not isinstance(data, dict):
        return None
    values = [data.get("title"), data.get("author")]
    if any(not isinstance(value, str) or not value.strip() or len(value.strip()) > 255
           for value in values):
        return None
    return tuple(value.strip() for value in values)


def serialize_book(row):
    book = dict(zip(("id", "title", "author", "status", "rating", "notes", "finished_on"), row))
    if book.get("finished_on") is not None:
        book["finished_on"] = book["finished_on"].isoformat()
    return book


@app.get("/books")
def get_books():
    query = request.args.get("q", "").strip()
    sort = request.args.get("sort", "oldest")
    status = request.args.get("status", "")
    orders = {
        "oldest": "id ASC", "newest": "id DESC",
        "rating": "rating DESC NULLS LAST, id ASC",
        "title": "lower(title) ASC, id ASC", "author": "lower(author) ASC, id ASC",
    }
    if len(query) > 255 or sort not in orders or (status and status not in READING_STATUSES):
        return jsonify(error="Invalid search or sort option"), 400
    paginated = "page" in request.args or "page_size" in request.args
    try:
        page = int(request.args.get("page", "1"))
        page_size = int(request.args.get("page_size", "10"))
        if not 1 <= page <= 1000000 or not 1 <= page_size <= 100:
            raise ValueError
    except ValueError:
        return jsonify(error="Page must be 1–1000000 and page_size must be 1–100"), 400
    where = " WHERE (strpos(lower(title), lower(%s)) > 0 OR strpos(lower(author), lower(%s)) > 0)"
    params = (query, query)
    if status:
        where += " AND status = %s"
        params += (status,)
    with database() as cursor:
        if paginated:
            cursor.execute("SELECT count(*) FROM books" + where, params)
            total = cursor.fetchone()[0]
        sql = "SELECT id, title, author, status, rating, notes, finished_on FROM books" + where + " ORDER BY " + orders[sort]
        if paginated:
            sql += " LIMIT %s OFFSET %s"
            params += (page_size, (page - 1) * page_size)
        cursor.execute(sql, params)
        books = [serialize_book(row) for row in cursor.fetchall()]
    if paginated:
        return jsonify(books=books, total=total, page=page, page_size=page_size)
    return jsonify(books)


@app.post("/books")
def add_book():
    values = book_values()
    if values is None:
        return jsonify(error="Title and author must contain 1–255 characters"), 400
    status = request.get_json().get("status", "to_read")
    if status not in READING_STATUSES:
        return jsonify(error="Invalid reading status"), 400
    with database() as cursor:
        cursor.execute(
            "INSERT INTO books (title, author, status, finished_on) VALUES (%s, %s, %s, %s) RETURNING id, title, author, status, rating, notes, finished_on",
            (*values, status, datetime.now(timezone.utc).date() if status == "finished" else None),
        )
        book = serialize_book(cursor.fetchone())
    return jsonify(book), 201


@app.put("/books/<int:book_id>")
def update_book(book_id):
    values = book_values()
    if values is None:
        return jsonify(error="Title and author must contain 1–255 characters"), 400
    with database() as cursor:
        cursor.execute(
            "UPDATE books SET title = %s, author = %s WHERE id = %s RETURNING id, title, author, status, rating, notes, finished_on",
            (*values, book_id),
        )
        row = cursor.fetchone()
    if row is None:
        return jsonify(error="Book not found"), 404
    return jsonify(serialize_book(row))


@app.delete("/books/<int:book_id>")
def delete_book(book_id):
    with database() as cursor:
        cursor.execute("DELETE FROM books WHERE id = %s RETURNING id", (book_id,))
        row = cursor.fetchone()
    if row is None:
        return jsonify(error="Book not found"), 404
    return "", 204


@app.patch("/books/<int:book_id>/status")
def update_status(book_id):
    data = request.get_json()
    if not isinstance(data, dict) or data.get("status") not in READING_STATUSES:
        return jsonify(error="Status must be to_read, reading, or finished"), 400
    finished_on = None
    if "finished_on" in data:
        try:
            finished_on = date.fromisoformat(data["finished_on"])
            if (data["status"] != "finished" or finished_on.isoformat() != data["finished_on"]
                    or finished_on > datetime.now(timezone.utc).date()):
                raise ValueError
        except (ValueError, TypeError):
            return jsonify(error="Completion date must be YYYY-MM-DD, not in the future, and status must be finished"), 400
    with database() as cursor:
        cursor.execute(
            "UPDATE books SET status = %s, finished_on = CASE WHEN %s = 'finished' "
            "THEN COALESCE(%s::date, finished_on, (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date) "
            "ELSE NULL END WHERE id = %s RETURNING id, title, author, status, rating, notes, finished_on",
            (data["status"], data["status"], finished_on, book_id),
        )
        row = cursor.fetchone()
    if row is None:
        return jsonify(error="Book not found"), 404
    return jsonify(serialize_book(row))


@app.get("/books/stats")
def book_stats():
    with database() as cursor:
        cursor.execute("SELECT status, count(*) FROM books GROUP BY status")
        counts = {status: 0 for status in READING_STATUSES}
        counts.update(dict(cursor.fetchall()))
    return jsonify(total=sum(counts.values()), **counts)


@app.patch("/books/<int:book_id>/review")
def update_review(book_id):
    data = request.get_json()
    if not isinstance(data, dict) or not data or set(data) - {"rating", "notes"}:
        return jsonify(error="Provide rating, notes, or both"), 400
    if "rating" in data and data["rating"] is not None:
        if type(data["rating"]) is not int or not 1 <= data["rating"] <= 5:
            return jsonify(error="Rating must be an integer from 1 to 5 or null"), 400
    if "notes" in data and (not isinstance(data["notes"], str) or len(data["notes"]) > 2000 or "\x00" in data["notes"]):
        return jsonify(error="Notes must be text of at most 2000 characters without null bytes"), 400
    # Assignments use fixed field names; values always remain parameters.
    fields = [field for field in ("rating", "notes") if field in data]
    assignments = ", ".join(field + " = %s" for field in fields)
    with database() as cursor:
        cursor.execute(
            "UPDATE books SET " + assignments + " WHERE id = %s RETURNING id, title, author, status, rating, notes, finished_on",
            tuple(data[field] for field in fields) + (book_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return jsonify(error="Book not found"), 404
    return jsonify(serialize_book(row))


@app.get("/reading-progress/<int:year>")
def reading_progress(year):
    if not 1900 <= year <= 9998:
        return jsonify(error="Year must be between 1900 and 9998"), 400
    with database() as cursor:
        cursor.execute(
            "SELECT (SELECT target FROM reading_goals WHERE year = %s), "
            "count(*) FILTER (WHERE status = 'finished' AND finished_on >= %s AND finished_on < %s), "
            "count(*) FILTER (WHERE status = 'finished' AND finished_on IS NULL) FROM books",
            (year, date(year, 1, 1), date(year + 1, 1, 1)),
        )
        target, finished, undated = cursor.fetchone()
    return jsonify(
        year=year, target=target, finished=finished, undated_finished=undated,
        remaining=max(target - finished, 0) if target else None,
        percent=round(finished / target * 100, 1) if target else None,
    )


@app.put("/reading-goals/<int:year>")
def save_reading_goal(year):
    data = request.get_json()
    if not 1900 <= year <= 9998:
        return jsonify(error="Year must be between 1900 and 9998"), 400
    if (not isinstance(data, dict) or set(data) != {"target"}
            or type(data.get("target")) is not int or not 1 <= data["target"] <= 10000):
        return jsonify(error="Target must be an integer between 1 and 10000"), 400
    with database() as cursor:
        cursor.execute(
            "INSERT INTO reading_goals (year, target) VALUES (%s, %s) "
            "ON CONFLICT (year) DO UPDATE SET target = EXCLUDED.target",
            (year, data["target"]),
        )
    return jsonify(year=year, target=data["target"])


@app.delete("/reading-goals/<int:year>")
def clear_reading_goal(year):
    if not 1900 <= year <= 9998:
        return jsonify(error="Year must be between 1900 and 9998"), 400
    with database() as cursor:
        cursor.execute("DELETE FROM reading_goals WHERE year = %s", (year,))
    return "", 204
