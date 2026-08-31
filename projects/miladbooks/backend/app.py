from flask import Flask, jsonify, request
import psycopg2
import os

app = Flask(__name__)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

@app.route('/books')
def get_books():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, author FROM books;")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    books = []
    for row in rows:
        books.append({
            "id": row[0],
            "title": row[1],
            "author": row[2]
        })

    return jsonify(books)

@app.route('/books/add', methods=['POST'])
def add_book():
    data = request.json
    title = data.get("title")
    author = data.get("author")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO books (title, author) VALUES (%s, %s) RETURNING id;",
        (title, author)
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Book added", "id": new_id})

if __name__ == '__main__':
    print("Starting Flask backend...")
    app.run(host='0.0.0.0', port=5000)
