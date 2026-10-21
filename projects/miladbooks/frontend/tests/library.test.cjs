const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const settle = async () => { await new Promise(setImmediate); };

function element() {
    return {
        value: '', textContent: '', style: {}, children: [], events: {}, disabled: false,
        addEventListener(name, callback) { this.events[name] = callback; },
        setAttribute(name, value) { this[name] = value; },
        replaceChildren() { this.children = []; this.textContent = ''; },
        appendChild(child) { this.children.push(child); },
        append(...children) { this.children.push(...children); },
        set innerHTML(value) { throw new Error('Unsafe HTML rendering'); },
    };
}
function start(handler) {
    const nodes = {};
    for (const id of ['status-filter', 'library-stats', 'sort', 'page-size', 'book-list', 'book-count', 'page-info',
        'previous-page', 'next-page', 'message', 'search-form', 'search', 'title', 'author', 'add-button']) {
        nodes[id] = element();
    }
    nodes.sort.value = 'oldest';
    nodes['page-size'].value = '10';
    const calls = [];
    const context = {
        URLSearchParams,
        document: {getElementById: id => nodes[id], createElement: element},
        fetch: async (url, options) => {
            if (url.endsWith('/stats')) return response({total: 4, to_read: 2, reading: 1, finished: 1});
            calls.push({url, options});
            return handler(url, options);
        },
        prompt: () => null,
    };
    vm.runInNewContext(script, context);
    return {nodes, calls, context};
}
const response = (body, status = 200) => ({ok: status < 400, status, json: async () => body});
const page = (books = [], total = books.length, size = 10) => ({books, total, page_size: size});

test('renders book text safely and sends search/sort/page controls', async () => {
    const book = {id: 1, title: '<img onerror=alert(1)>', author: 'Author'};
    const {nodes, calls} = start(() => response(page([book], 30)));
    await settle();
    assert.equal(nodes['book-list'].children[0].children[0].textContent, '1. <img onerror=alert(1)> — Author');
    assert.equal(nodes['book-count'].textContent, '30 books');
    nodes['next-page'].events.click();
    await settle();
    assert.equal(new URLSearchParams(calls.at(-1).url.split('?')[1]).get('page'), '2');
    nodes.search.value = ' Linux & Docker ';
    nodes['search-form'].events.submit({preventDefault() {}});
    await settle();
    const params = new URLSearchParams(calls.at(-1).url.split('?')[1]);
    assert.equal(params.get('q'), 'Linux & Docker');
    assert.equal(params.get('page'), '1');
    nodes.sort.value = 'author';
    nodes.sort.events.change();
    await settle();
    assert.equal(new URLSearchParams(calls.at(-1).url.split('?')[1]).get('sort'), 'author');
});

test('a late search response cannot replace newer results', async () => {
    let firstResolve;
    let requests = 0;
    const {context, nodes} = start(() => {
        if (++requests === 1) return new Promise(resolve => { firstResolve = resolve; });
        return response(page([{id: 2, title: 'Current', author: 'A'}]));
    });
    await context.loadBooks();
    firstResolve(response(page([{id: 1, title: 'Old', author: 'A'}])));
    await settle();
    assert.equal(nodes['book-list'].children[0].children[0].textContent, '2. Current — A');
    assert.equal(nodes['book-list']['aria-busy'], 'false');
});

test('editing prefills the current values and failed creation preserves inputs', async () => {
    const {context, nodes, calls} = start((url, options) => {
        if (options?.method === 'POST') return response({error: 'Database unavailable'}, 503);
        if (options?.method === 'PUT') return response({id: 7, title: 'Edited', author: 'Writer'});
        return response(page());
    });
    await settle();
    const prompts = [];
    context.prompt = (label, value) => { prompts.push(value); return 'Edited'; };
    await context.updateBook({id: 7, title: 'Original', author: 'Writer'});
    assert.deepEqual(prompts, ['Original', 'Writer']);
    assert.equal(calls.find(call => call.options?.method === 'PUT').url, '/api/books/7');
    nodes.title.value = 'Keep title';
    nodes.author.value = 'Keep author';
    await context.addBook();
    assert.equal(nodes.title.value, 'Keep title');
    assert.equal(nodes.author.value, 'Keep author');
    assert.equal(nodes.message.textContent, 'Database unavailable');
    assert.equal(nodes['add-button'].disabled, false);
});

test('deleting the last book on a page returns to an available page', async () => {
    let deleted = false;
    const {context, nodes, calls} = start((url, options) => {
        if (options?.method === 'DELETE') { deleted = true; return response(null, 204); }
        const number = Number(new URLSearchParams(url.split('?')[1]).get('page'));
        const books = number === 2 && deleted ? [] : [{id: 11, title: 'Book', author: 'A'}];
        return response(page(books, deleted ? 10 : 11));
    });
    await settle();
    nodes['next-page'].events.click();
    await settle();
    assert.equal(nodes['page-info'].textContent, 'Page 2 of 2');
    await context.deleteBook(11);
    assert.equal(nodes['page-info'].textContent, 'Page 1 of 1');
    assert.equal(new URLSearchParams(calls.at(-1).url.split('?')[1]).get('page'), '1');
    assert.equal(nodes['next-page'].disabled, true);
});


test('reading status filters reset pagination and updates refresh library counts', async () => {
    const book = {id: 4, title: 'Linux', author: 'Author', status: 'to_read'};
    const {nodes, calls} = start((url, options) => {
        if (options?.method === 'PATCH') return response({...book, status: 'reading'});
        return response(page([book], 20));
    });
    await settle();
    assert.match(nodes['library-stats'].textContent, /2 to read · 1 reading · 1 finished/);
    const select = nodes['book-list'].children[0].children[1].children[0];
    assert.equal(select.value, 'to_read');
    select.value = 'reading';
    await select.events.change();
    const update = calls.find(call => call.options?.method === 'PATCH');
    assert.equal(update.url, '/api/books/4/status');
    assert.deepEqual(JSON.parse(update.options.body), {status: 'reading'});
    nodes['next-page'].events.click();
    await settle();
    nodes['status-filter'].value = 'finished';
    nodes['status-filter'].events.change();
    await settle();
    const params = new URLSearchParams(calls.at(-1).url.split('?')[1]);
    assert.equal(params.get('page'), '1');
    assert.equal(params.get('status'), 'finished');
});

test('a failed reading status update restores the saved selection', async () => {
    const book = {id: 4, title: 'Linux', author: 'Author', status: 'to_read'};
    const {nodes} = start((url, options) => options?.method === 'PATCH'
        ? response({error: 'Database unavailable'}, 503) : response(page([book])));
    await settle();
    const select = nodes['book-list'].children[0].children[1].children[0];
    select.value = 'finished';
    await select.events.change();
    assert.equal(select.value, 'to_read');
    assert.equal(select.disabled, false);
    assert.equal(nodes.message.textContent, 'Database unavailable');
});
