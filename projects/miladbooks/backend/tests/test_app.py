import unittest
from unittest.mock import MagicMock, patch

import psycopg2
import app as api


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = api.app.test_client()
        self.database = patch('app.database')
        self.cursor = self.database.start().return_value.__enter__.return_value
        self.addCleanup(self.database.stop)

    def test_crud_and_parameterized_values(self):
        title = "Robert'); DROP TABLE books;--"
        self.cursor.fetchone.return_value = (1, title, 'Author')
        response = self.client.post('/books', json={'title': title, 'author': 'Author'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['title'], title)
        sql, params = self.cursor.execute.call_args.args
        self.assertNotIn(title, sql)
        self.assertEqual(params, (title, 'Author'))
        self.cursor.fetchall.return_value = [(1, title, 'Author')]
        self.assertEqual(self.client.get('/books').json, [response.json])
        self.cursor.fetchone.return_value = (1, 'Updated', 'Writer')
        response = self.client.put('/books/1', json={'title': 'Updated', 'author': 'Writer'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['title'], 'Updated')
        self.assertEqual(self.client.delete('/books/1').status_code, 204)

    def test_invalid_payloads_do_not_touch_database(self):
        for data in [None, [], {}, {'title': 4, 'author': 'A'},
                     {'title': ' ', 'author': 'A'}, {'title': 'x' * 256, 'author': 'A'}]:
            with self.subTest(data=data):
                response = self.client.post('/books', json=data, content_type='application/json')
                self.assertEqual(response.status_code, 400)
        self.cursor.execute.assert_not_called()
        self.assertEqual(self.client.post('/books', data='bad', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/books', data='plain').status_code, 415)

    def test_missing_books_and_http_errors(self):
        self.cursor.fetchone.return_value = None
        self.assertEqual(self.client.delete('/books/99').status_code, 404)
        self.assertEqual(self.client.put('/books/99', json={'title': 'T', 'author': 'A'}).status_code, 404)
        self.assertEqual(self.client.get('/missing').status_code, 404)
        response = self.client.patch('/books')
        self.assertEqual(response.status_code, 405)
        self.assertIn('GET', response.headers['Allow'])

    def test_database_failure_is_sanitized(self):
        self.cursor.execute.side_effect = psycopg2.OperationalError('private connection details')
        response = self.client.get('/books')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {'error': 'Database unavailable'})
        self.assertEqual(self.client.get('/health').status_code, 200)


class ConnectionTests(unittest.TestCase):
    @patch.dict('os.environ', {'DB_HOST': 'db', 'DB_NAME': 'books', 'DB_USER': 'user', 'DB_PASSWORD': 'secret'})
    @patch('app.psycopg2.connect')
    def test_failed_operation_exits_transaction_and_closes_connection(self, connect):
        connection = connect.return_value
        with self.assertRaises(ValueError):
            with api.database():
                raise ValueError('failed operation')
        self.assertEqual(connection.__exit__.call_args.args[0], ValueError)
        connection.close.assert_called_once()
        with api.database():
            pass
        self.assertEqual(connection.close.call_count, 2)

    @patch('wait_for_db.psycopg2.connect')
    @patch('wait_for_db.time.sleep')
    @patch.dict('os.environ', {'DB_HOST': 'db', 'DB_NAME': 'books', 'DB_USER': 'user', 'DB_PASSWORD': 'secret'})
    def test_startup_retries(self, sleep, connect):
        from wait_for_db import wait_for_db
        connection = MagicMock()
        connect.side_effect = [psycopg2.OperationalError('starting'), connection]
        wait_for_db()
        sleep.assert_called_once_with(2)
        connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
