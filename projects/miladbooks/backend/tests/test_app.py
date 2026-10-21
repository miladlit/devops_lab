import unittest
from datetime import date, datetime, timezone
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
        self.cursor.fetchone.return_value = (1, title, 'Author', 'to_read', None, '', None)
        response = self.client.post('/books', json={'title': title, 'author': 'Author'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['title'], title)
        sql, params = self.cursor.execute.call_args.args
        self.assertNotIn(title, sql)
        self.assertEqual(params, (title, 'Author', 'to_read', None))
        self.cursor.fetchall.return_value = [(1, title, 'Author', 'to_read', None, '', None)]
        self.assertEqual(self.client.get('/books').json, [response.json])
        self.cursor.fetchone.return_value = (1, 'Updated', 'Writer', 'reading', None, '', None)
        response = self.client.put('/books/1', json={'title': 'Updated', 'author': 'Writer'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['title'], 'Updated')
        self.assertEqual(self.client.delete('/books/1').status_code, 204)

    def test_search_sort_and_pagination(self):
        self.cursor.fetchone.return_value = (23,)
        self.cursor.fetchall.return_value = [(12, 'Linux', 'Milad', 'finished', None, '', None)]
        response = self.client.get('/books?q=LINUX&sort=title&page=2&page_size=10')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            'books': [{'id': 12, 'title': 'Linux', 'author': 'Milad', 'status': 'finished', 'rating': None, 'notes': '', 'finished_on': None}],
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
        self.cursor.fetchone.return_value = (1, 'Linux', 'Milad', 'reading', None, '', None)
        response = self.client.patch('/books/1/status', json={'status': 'reading'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'reading')
        self.assertEqual(self.cursor.execute.call_args.args[1], ('reading', 'reading', None, 1))
        self.cursor.fetchone.return_value = None
        self.assertEqual(self.client.patch('/books/99/status', json={'status': 'finished'}).status_code, 404)
        for payload in [{}, [], {'status': None}, {'status': []}, {'status': 'unknown'}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.patch('/books/1/status', json=payload).status_code, 400)
        self.assertEqual(self.client.post('/books', json={
            'title': 'Book', 'author': 'Author', 'status': 'unknown',
        }).status_code, 400)

    def test_create_with_status_and_edit_without_resetting_status(self):
        self.cursor.fetchone.return_value = (8, 'Book', 'Author', 'finished', None, '', None)
        response = self.client.post('/books', json={
            'title': 'Book', 'author': 'Author', 'status': 'finished',
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['status'], 'finished')
        self.assertEqual(self.cursor.execute.call_args.args[1], ('Book', 'Author', 'finished', datetime.now(timezone.utc).date()))
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

    def test_review_update_clear_and_partial_update(self):
        self.cursor.fetchone.return_value = (5, 'Book', 'Author', 'finished', 4, "Reader's notes")
        response = self.client.patch('/books/5/review', json={'rating': 4, 'notes': "Reader's notes"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['rating'], 4)
        sql, params = self.cursor.execute.call_args.args
        self.assertEqual(params, (4, "Reader's notes", 5))
        self.assertNotIn("Reader's notes", sql)
        self.client.patch('/books/5/review', json={'rating': None})
        sql, params = self.cursor.execute.call_args.args
        self.assertEqual(params, (None, 5))
        self.assertNotIn('notes =', sql)
        self.client.patch('/books/5/review', json={'notes': ''})
        sql, params = self.cursor.execute.call_args.args
        self.assertEqual(params, ('', 5))
        self.assertNotIn('rating =', sql)
        self.cursor.fetchone.return_value = None
        self.assertEqual(self.client.patch('/books/99/review', json={'rating': 5}).status_code, 404)

    def test_review_rejects_invalid_values_without_database_access(self):
        for data in [[], {}, {'rating': True}, {'rating': 0}, {'rating': 6},
                     {'rating': '4'}, {'rating': 2.5}, {'notes': None},
                     {'notes': 'x' * 2001}, {'notes': 'a\x00b'}, {'status': 'finished'}]:
            with self.subTest(data=data):
                self.assertEqual(self.client.patch('/books/5/review', json=data).status_code, 400)
        self.cursor.execute.assert_not_called()

    def test_rating_sort_keeps_unrated_books_last(self):
        self.cursor.fetchall.return_value = []
        self.assertEqual(self.client.get('/books?sort=rating').status_code, 200)
        self.assertIn('rating DESC NULLS LAST, id ASC', self.cursor.execute.call_args.args[0])

    def test_yearly_progress_and_overachievement(self):
        self.cursor.fetchone.return_value = (12, 5, 2)
        response = self.client.get('/reading-progress/2026')
        self.assertEqual(response.json, {
            'year': 2026, 'target': 12, 'finished': 5, 'remaining': 7,
            'percent': 41.7, 'undated_finished': 2,
        })
        self.assertEqual(self.cursor.execute.call_args.args[1], (2026, date(2026, 1, 1), date(2027, 1, 1)))
        self.cursor.fetchone.return_value = (2, 3, 0)
        response = self.client.get('/reading-progress/2026')
        self.assertEqual(response.json['remaining'], 0)
        self.assertEqual(response.json['percent'], 150.0)
        self.cursor.fetchone.return_value = (None, 0, 1)
        self.assertIsNone(self.client.get('/reading-progress/2025').json['percent'])

    def test_goal_validation_and_upsert(self):
        response = self.client.put('/reading-goals/2026', json={'target': 24})
        self.assertEqual(response.json, {'year': 2026, 'target': 24})
        self.assertEqual(self.cursor.execute.call_args.args[1], (2026, 24))
        self.assertIn('ON CONFLICT', self.cursor.execute.call_args.args[0])
        self.cursor.reset_mock()
        for data in [{}, [], {'target': True}, {'target': 0}, {'target': 10001},
                     {'target': '5'}, {'target': 2.5}, {'target': 5, 'extra': 1}]:
            with self.subTest(data=data):
                self.assertEqual(self.client.put('/reading-goals/2026', json=data).status_code, 400)
        self.assertEqual(self.client.get('/reading-progress/9999').status_code, 400)
        self.assertEqual(self.client.put('/reading-goals/1899', json={'target': 12}).status_code, 400)
        self.cursor.execute.assert_not_called()

    def test_clearing_goal_preserves_books(self):
        response = self.client.delete('/reading-goals/2026')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.cursor.execute.call_args.args, ('DELETE FROM reading_goals WHERE year = %s', (2026,)))
        self.assertEqual(self.client.delete('/reading-goals/9999').status_code, 400)

    def test_completion_dates_and_reading_transitions(self):
        self.cursor.fetchone.return_value = (1, 'Book', 'Author', 'finished', None, '', date(2025, 12, 31))
        response = self.client.patch('/books/1/status', json={'status': 'finished', 'finished_on': '2025-12-31'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['finished_on'], '2025-12-31')
        self.assertEqual(self.cursor.execute.call_args.args[1], ('finished', 'finished', date(2025, 12, 31), 1))
        self.client.patch('/books/1/status', json={'status': 'reading'})
        sql, params = self.cursor.execute.call_args.args
        self.assertIn('ELSE NULL END', sql)
        self.assertIn('COALESCE', sql)
        self.assertEqual(params, ('reading', 'reading', None, 1))
        self.cursor.reset_mock()
        for value in ['not-a-date', '2026-02-30', '9999-12-31', '20250101', None, 5]:
            with self.subTest(value=value):
                self.assertEqual(self.client.patch('/books/1/status', json={
                    'status': 'finished', 'finished_on': value,
                }).status_code, 400)
        self.assertEqual(self.client.patch('/books/1/status', json={
            'status': 'reading', 'finished_on': '2025-01-01',
        }).status_code, 400)
        self.cursor.execute.assert_not_called()

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
