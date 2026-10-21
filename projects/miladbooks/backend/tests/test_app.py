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
        self.cursor.fetchone.return_value = (1, title, 'Author', 'to_read')
        response = self.client.post('/books', json={'title': title, 'author': 'Author'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['title'], title)
        sql, params = self.cursor.execute.call_args.args
        self.assertNotIn(title, sql)
        self.assertEqual(params, (title, 'Author', 'to_read'))
        self.cursor.fetchall.return_value = [(1, title, 'Author', 'to_read')]
        self.assertEqual(self.client.get('/books').json, [response.json])
        self.cursor.fetchone.return_value = (1, 'Updated', 'Writer', 'reading')
        response = self.client.put('/books/1', json={'title': 'Updated', 'author': 'Writer'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['title'], 'Updated')
        self.assertEqual(self.client.delete('/books/1').status_code, 204)

    def test_search_sort_and_pagination(self):
        self.cursor.fetchone.return_value = (23,)
        self.cursor.fetchall.return_value = [(12, 'Linux', 'Milad', 'finished')]
        response = self.client.get('/books?q=LINUX&sort=title&page=2&page_size=10')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            'books': [{'id': 12, 'title': 'Linux', 'author': 'Milad', 'status': 'finished'}],
            'total': 23, 'page': 2, 'page_size': 10,
        })
        sql, params = self.cursor.execute.call_args.args
        self.assertIn('ORDER BY lower(title) ASC, id ASC LIMIT %s OFFSET %s', sql)
        self.assertEqual(params, ('LINUX', 'LINUX', 10, 10))

    def test_search_is_literal_and_parameterized(self):
        self.cursor.fetchall.return_value = []
        query = "100%_';--"
        response = self.client.get('/books', query_string={'q': query, 'sort': 'newest'})
        self.assertEqual(response.status_code, 200)
        sql, params = self.cursor.execute.call_args.args
        self.assertNotIn(query, sql)
        self.assertEqual(params, (query, query))
        self.assertIn('strpos', sql)
        self.assertIn('ORDER BY id DESC', sql)

    def test_invalid_list_options_do_not_touch_database(self):
        for query in ['page=0', 'page=-1', 'page=abc', 'page=1000001',
                      'page_size=0', 'page_size=101', 'page_size=1.5',
                      'sort=title;DROP TABLE books', 'q=' + 'x' * 256]:
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/books?' + query).status_code, 400)
        self.cursor.execute.assert_not_called()

    def test_empty_page_retains_total(self):
        self.cursor.fetchone.return_value = (3,)
        self.cursor.fetchall.return_value = []
        response = self.client.get('/books?page=2&page_size=10')
        self.assertEqual(response.json['books'], [])
        self.assertEqual(response.json['total'], 3)

    def test_status_updates_and_validation(self):
        self.cursor.fetchone.return_value = (1, 'Linux', 'Milad', 'reading')
        response = self.client.patch('/books/1/status', json={'status': 'reading'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'reading')
        self.assertEqual(self.cursor.execute.call_args.args[1], ('reading', 1))
        self.cursor.fetchone.return_value = None
        self.assertEqual(self.client.patch('/books/99/status', json={'status': 'finished'}).status_code, 404)
        for payload in [{}, [], {'status': None}, {'status': []}, {'status': 'unknown'}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.patch('/books/1/status', json=payload).status_code, 400)
        self.assertEqual(self.client.post('/books', json={
            'title': 'Book', 'author': 'Author', 'status': 'unknown',
        }).status_code, 400)

    def test_create_with_status_and_edit_without_resetting_status(self):
        self.cursor.fetchone.return_value = (8, 'Book', 'Author', 'finished')
        response = self.client.post('/books', json={
            'title': 'Book', 'author': 'Author', 'status': 'finished',
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['status'], 'finished')
        self.assertEqual(self.cursor.execute.call_args.args[1], ('Book', 'Author', 'finished'))
        response = self.client.put('/books/8', json={'title': 'Edited', 'author': 'Writer'})
        self.assertEqual(response.status_code, 200)
        sql, params = self.cursor.execute.call_args.args
        self.assertNotIn('SET status', sql)
        self.assertEqual(params, ('Edited', 'Writer', 8))

    def test_status_filter_combines_with_title_or_author_search(self):
        self.cursor.fetchone.return_value = (0,)
        self.cursor.fetchall.return_value = []
        response = self.client.get('/books?q=Linux&status=finished&page=1')
        self.assertEqual(response.status_code, 200)
        sql, params = self.cursor.execute.call_args.args
        self.assertIn(') AND status = %s', sql)
        self.assertEqual(params, ('Linux', 'Linux', 'finished', 10, 0))
        self.assertEqual(self.client.get('/books?status=invalid').status_code, 400)

    def test_library_stats_including_empty_shelves(self):
        self.cursor.fetchall.return_value = [('to_read', 3), ('finished', 2)]
        self.assertEqual(self.client.get('/books/stats').json, {
            'total': 5, 'to_read': 3, 'reading': 0, 'finished': 2,
        })
        self.cursor.fetchall.return_value = []
        self.assertEqual(self.client.get('/books/stats').json['total'], 0)

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
