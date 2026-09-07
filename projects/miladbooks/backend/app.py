import os
import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load environment variables
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
FLASK_SECRET = os.getenv("FLASK_SECRET")

app.config["SECRET_KEY"] = FLASK_SECRET

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

@app.route("/books", methods=["GET"])
def get_books():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, author FROM books ORDER BY id ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    books = [{"id": r[0], "title": r[1], "author": r[2]} for r in rows]
    return jsonify(books)

@app.route("/books", methods=["POST"])
def add_book():
    data = request.json
    title = data.get("title")
    author = data.get("author")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO books (title, author) VALUES (%s, %s) RETURNING id",
        (title, author)
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"id": new_id, "title": title, "author": author})

@app.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, author FROM books WHERE id = %s", (book_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        return jsonify({"id": row[0], "title": row[1], "author": row[2]})
    return jsonify({"message": "Book not found"}), 404

@app.route("/books/<int:book_id>", methods=["PUT"])
def update_book(book_id):
    data = request.json
    title = data.get("title")
    author = data.get("author")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE books SET title = %s, author = %s WHERE id = %s",
        (title, author, book_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"id": book_id, "title": title, "author": author})

@app.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM books WHERE id = %s", (book_id,))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Book deleted"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
