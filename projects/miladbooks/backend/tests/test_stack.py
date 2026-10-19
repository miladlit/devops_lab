"""Run against the full stack with STACK_URL=http://127.0.0.1:8080."""
import json
import os
import unittest
import urllib.error
import urllib.request


@unittest.skipUnless(os.getenv('STACK_URL'), 'Set STACK_URL for full-stack tests')
class StackTests(unittest.TestCase):
    def request(self, path, method='GET', data=None):
        payload = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(
            os.environ['STACK_URL'] + path, data=payload, method=method,
            headers={'Content-Type': 'application/json'},
        )
        try:
            response = urllib.request.urlopen(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            return response.status, json.loads(body) if body else None

    def test_crud_through_nginx(self):
        status, health = self.request('/api/health/db')
        self.assertEqual(status, 200)
        status, book = self.request('/api/books', 'POST', {'title': '<img src=x onerror=alert(1)>', 'author': 'Writer'})
        self.assertEqual(status, 201)
        book_id = book['id']
        self.addCleanup(self.request, f'/api/books/{book_id}', 'DELETE')
        self.assertIn(book, self.request('/api/books')[1])
        status, updated = self.request(f'/api/books/{book_id}', 'PUT', {'title': 'Updated', 'author': 'Writer'})
        self.assertEqual(status, 200)
        self.assertEqual(updated['title'], 'Updated')
        self.assertEqual(self.request(f'/api/books/{book_id}', 'DELETE')[0], 204)
        self.assertEqual(self.request(f'/api/books/{book_id}', 'DELETE')[0], 404)
        self.assertEqual(self.request('/api/books', 'POST', {'title': '', 'author': 'A'})[0], 400)
        self.assertEqual(self.request('/api/missing')[0], 404)
        self.assertEqual(self.request('/api/books', 'PATCH')[0], 405)


if __name__ == '__main__':
    unittest.main()
