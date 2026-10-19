import logging
import os
import time
from contextlib import contextmanager

import psycopg2
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from logging_config import configure_logging

configure_logging()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


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
    return dict(zip(("id", "title", "author"), row))


@app.get("/books")
def get_books():
    with database() as cursor:
        cursor.execute("SELECT id, title, author FROM books ORDER BY id")
        books = [serialize_book(row) for row in cursor.fetchall()]
    return jsonify(books)


@app.post("/books")
def add_book():
    values = book_values()
    if values is None:
        return jsonify(error="Title and author must contain 1–255 characters"), 400
    with database() as cursor:
        cursor.execute(
            "INSERT INTO books (title, author) VALUES (%s, %s) RETURNING id, title, author",
            values,
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
            "UPDATE books SET title = %s, author = %s WHERE id = %s RETURNING id, title, author",
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
