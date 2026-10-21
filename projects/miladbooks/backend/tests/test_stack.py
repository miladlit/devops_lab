"""Run against the full stack with STACK_URL=http://127.0.0.1:8080."""
import json
import os
import unittest
import uuid
import urllib.parse
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

    def test_search_and_sort_across_pages(self):
        marker = uuid.uuid4().hex
        for title, author in [('Zulu', 'Alice'), ('alpha', 'Bob'), ('Beta', 'Carol')]:
            status, book = self.request('/api/books', 'POST', {
                'title': title, 'author': marker + author,
            })
            self.assertEqual(status, 201)
            self.addCleanup(self.request, f"/api/books/{book['id']}", 'DELETE')
        path = '/api/books?' + urllib.parse.urlencode({
            'q': marker.upper(), 'sort': 'title', 'page': 1, 'page_size': 2,
        })
        status, result = self.request(path)
        self.assertEqual(status, 200)
        self.assertEqual(result['total'], 3)
        self.assertEqual([book['title'] for book in result['books']], ['alpha', 'Beta'])
        status, result = self.request(path.replace('page=1', 'page=2'))
        self.assertEqual([book['title'] for book in result['books']], ['Zulu'])
        status, result = self.request(path.replace('page=1', 'page=3'))
        self.assertEqual(result['books'], [])
        self.assertEqual(result['total'], 3)
        self.assertEqual(self.request('/api/books?page_size=101')[0], 400)

    def test_reading_progress_persists_and_filters(self):
        marker = uuid.uuid4().hex
        status, book = self.request('/api/books', 'POST', {'title': marker, 'author': 'Reader'})
        self.assertEqual(status, 201)
        self.assertEqual(book['status'], 'to_read')
        book_id = book['id']
        self.addCleanup(self.request, f'/api/books/{book_id}', 'DELETE')
        status, changed = self.request(f'/api/books/{book_id}/status', 'PATCH', {'status': 'reading'})
        self.assertEqual(status, 200)
        self.assertEqual(changed['status'], 'reading')
        self.assertEqual(self.request(f'/api/books?q={marker}&status=to_read&page=1')[1]['total'], 0)
        result = self.request(f'/api/books?q={marker}&status=reading&page=1')[1]
        self.assertEqual(result['books'], [changed])
        status, edited = self.request(f'/api/books/{book_id}', 'PUT', {'title': marker, 'author': 'Edited'})
        self.assertEqual(edited['status'], 'reading')
        status, stats = self.request('/api/books/stats')
        self.assertEqual(status, 200)
        self.assertGreaterEqual(stats['reading'], 1)
        self.assertEqual(stats['total'], sum(stats[key] for key in ['to_read', 'reading', 'finished']))


if __name__ == '__main__':
    unittest.main()
