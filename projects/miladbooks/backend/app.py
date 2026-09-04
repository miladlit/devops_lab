from flask import Flask, jsonify, request
import psycopg2
import logging
import os
import traceback

app = Flask(__name__)

# Logging configuration
logging.basicConfig(
    filename='/app/logs/backend.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s'
)

logging.info("Backend started")


def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        return conn
    except Exception:
        logging.error("Database connection failed:")
        logging.error(traceback.format_exc())
        raise


# -----------------------------
# GET ALL BOOKS
# -----------------------------
@app.route('/books', methods=['GET'])
def get_books():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, author FROM books")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        books = [{"id": r[0], "title": r[1], "author": r[2]} for r in rows]
        return jsonify(books)

    except Exception:
        logging.error("GET /books failed:")
        logging.error(traceback.format_exc())
        return jsonify({"error": "Failed to fetch books"}), 500


# -----------------------------
# ADD NEW BOOK
# -----------------------------
@app.route('/books', methods=['POST'])
def add_book():
    try:
        data = request.get_json()
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

        return jsonify({"id": new_id, "title": title, "author": author}), 201

    except Exception:
        logging.error("POST /books failed:")
        logging.error(traceback.format_exc())
        return jsonify({"error": "Failed to add book"}), 500


# -----------------------------
# GET SINGLE BOOK
# -----------------------------
@app.route('/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, author FROM books WHERE id = %s", (book_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            return jsonify({"id": row[0], "title": row[1], "author": row[2]})
        else:
            return jsonify({"error": "Book not found"}), 404

    except Exception:
        logging.error("GET /books/<id> failed:")
        logging.error(traceback.format_exc())
        return jsonify({"error": "Failed to fetch book"}), 500


# -----------------------------
# UPDATE BOOK
# -----------------------------
@app.route('/books/<int:book_id>', methods=['PUT'])
def update_book(book_id):
    try:
        data = request.get_json()
        title = data.get("title")
        author = data.get("author")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE books SET title = %s, author = %s WHERE id = %s RETURNING id",
            (title, author, book_id)
        )
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        if updated:
            return jsonify({"id": book_id, "title": title, "author": author})
        else:
            return jsonify({"error": "Book not found"}), 404

    except Exception:
        logging.error("PUT /books/<id> failed:")
        logging.error(traceback.format_exc())
        return jsonify({"error": "Failed to update book"}), 500


# -----------------------------
# DELETE BOOK
# -----------------------------
@app.route('/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM books WHERE id = %s RETURNING id", (book_id,))
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        if deleted:
            return jsonify({"message": "Book deleted"})
        else:
            return jsonify({"error": "Book not found"}), 404

    except Exception:
        logging.error("DELETE /books/<id> failed:")
        logging.error(traceback.format_exc())
        return jsonify({"error": "Failed to delete book"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
