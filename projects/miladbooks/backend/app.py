from flask import Flask, jsonify
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
    except Exception as e:
        logging.error("Database connection failed:")
        logging.error(traceback.format_exc())
        raise

@app.route('/books')
def get_books():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, author FROM books")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        books = [{"id": r[0], "title": r[1], "author": r[2]} for r in rows]
        logging.info("GET /books successful")
        return jsonify(books)

    except Exception as e:
        logging.error("GET /books failed:")
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
