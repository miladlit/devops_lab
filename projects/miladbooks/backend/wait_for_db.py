"""Bounded connection retries before running migrations."""
import os
import time
import psycopg2


def wait_for_db():
    for attempt in range(30):
        try:
            conn = psycopg2.connect(
                host=os.environ["DB_HOST"], dbname=os.environ["DB_NAME"],
                user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                connect_timeout=3,
            )
            conn.close()
            return
        except psycopg2.OperationalError:
            if attempt == 29:
                raise
            time.sleep(2)


if __name__ == "__main__":
    wait_for_db()
