import os
import time
import logging
import psycopg2
from flask import Flask, request, jsonify
from pythonjsonlogger import jsonlogger

# ---------------------------------------------------
# Logging Configuration (JSON Structured Logging)
# ---------------------------------------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(message)s %(pathname)s %(lineno)d"
)
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)

# ---------------------------------------------------
# Flask App
# ---------------------------------------------------
app = Flask(__name__)

# ---------------------------------------------------
# Database Connection
# ---------------------------------------------------
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

# ---------------------------------------------------
# Request Logging Middleware
# ---------------------------------------------------
@app.before_request
def log_request():
    request.start_time = time.time()
    logging.info({
        "event": "request",
        "method": request.method,
        "path": request.path,
        "remote_addr": request.remote_addr
    })

@app.after_request
def log_response(response):
    duration = round(time.time() - request.start_time, 4)
    logging.info({
        "event": "response",
        "status": response.status_code,
        "path": request.path,
        "duration": duration
    })
    return response

# ---------------------------------------------------
# Error Logging
# ---------------------------------------------------
@app.errorhandler(Exception)
def handle_exception(e):
    logging.error({
        "event": "error",
        "error": str(e),
        "path": request.path
    })
    return jsonify({"error": "Internal server error"}), 500

# ---------------------------------------------------
# Health Endpoints
# ---------------------------------------------------
@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/health/db")
def health_db():
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        return jsonify({"status": "ok", "db": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "error", "db": str(e)}), 500

# ---------------------------------------------------
# Books Endpoint
# ---------------------------------------------------
@app.route("/books")
def get_books():
    cur = conn.cursor()
    cur.execute("SELECT id, title, author FROM books;")
    rows = cur.fetchall()

    books = [{"id": r[0], "title": r[1], "author": r[2]} for r in rows]
    return jsonify(books)

# ---------------------------------------------------
# Start App
# ---------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
