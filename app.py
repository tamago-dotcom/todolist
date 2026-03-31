from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)
DATABASE = 'todo.db'


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            due_date TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')
    # 既存DBへのマイグレーション
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT '中'")
    except Exception:
        pass  # 列が既に存在する場合はスキップ
    cur.execute('SELECT COUNT(*) as cnt FROM categories')
    if cur.fetchone()['cnt'] == 0:
        for name in ['仕事', '買い物', '副業']:
            cur.execute('INSERT INTO categories (name) VALUES (?)', (name,))
    conn.commit()
    conn.close()


def priority_order(priority):
    return {'高': 0, '中': 1, '低': 2}.get(priority, 3)


def enrich_and_sort(tasks_raw, sort):
    result = []
    for t in tasks_raw:
        result.append({
            'id': t['id'],
            'name': t['name'],
            'due_date': t['due_date'],
            'category_id': t['category_id'],
            'category_name': t['category_name'],
            'created_at': t['created_at'],
            'priority': t['priority'],
        })
    if sort == 'priority':
        result.sort(key=lambda x: priority_order(x['priority']))
    elif sort == 'created':
        result.sort(key=lambda x: x['created_at'])
    else:
        result.sort(key=lambda x: x['due_date'])
    return result


TASK_QUERY = '''
    SELECT t.id, t.name, t.due_date, t.category_id, t.priority, t.created_at, c.name as category_name
    FROM tasks t
    JOIN categories c ON t.category_id = c.id
    WHERE t.completed = {completed}
'''


@app.route('/')
def index():
    tab = request.args.get('tab', 'all')
    sort = request.args.get('sort', 'due')

    conn = get_db()
    categories = conn.execute('SELECT * FROM categories ORDER BY id').fetchall()

    query = TASK_QUERY.format(completed=0)
    if tab != 'all':
        tasks_raw = conn.execute(query + ' AND t.category_id = ?', (tab,)).fetchall()
    else:
        tasks_raw = conn.execute(query).fetchall()
    conn.close()

    tasks = enrich_and_sort(tasks_raw, sort)
    return render_template('index.html', tasks=tasks, categories=categories, tab=tab, sort=sort)


@app.route('/completed')
def completed():
    sort = request.args.get('sort', 'due')

    conn = get_db()
    categories = conn.execute('SELECT * FROM categories ORDER BY id').fetchall()
    tasks_raw = conn.execute(TASK_QUERY.format(completed=1)).fetchall()
    conn.close()

    tasks = enrich_and_sort(tasks_raw, sort)
    return render_template('completed.html', tasks=tasks, categories=categories, sort=sort, tab='')


@app.route('/task/add', methods=['POST'])
def add_task():
    name = request.form['name'].strip()
    due_date = request.form['due_date']
    category_id = request.form['category_id']
    priority = request.form.get('priority', '中')
    tab = request.form.get('tab', 'all')
    sort = request.form.get('sort', 'due')

    if name and due_date and category_id:
        conn = get_db()
        conn.execute('INSERT INTO tasks (name, due_date, category_id, priority) VALUES (?, ?, ?, ?)',
                     (name, due_date, category_id, priority))
        conn.commit()
        conn.close()

    return redirect(url_for('index', tab=tab, sort=sort))


@app.route('/task/complete/<int:task_id>', methods=['POST'])
def complete_task(task_id):
    tab = request.form.get('tab', 'all')
    sort = request.form.get('sort', 'due')

    conn = get_db()
    conn.execute('UPDATE tasks SET completed = 1 WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('index', tab=tab, sort=sort))


@app.route('/task/edit/<int:task_id>', methods=['POST'])
def edit_task(task_id):
    name = request.form['name'].strip()
    due_date = request.form['due_date']
    category_id = request.form['category_id']
    priority = request.form.get('priority', '中')
    tab = request.form.get('tab', 'all')
    sort = request.form.get('sort', 'due')
    source = request.form.get('source', 'index')

    if name and due_date and category_id:
        conn = get_db()
        conn.execute('UPDATE tasks SET name = ?, due_date = ?, category_id = ?, priority = ? WHERE id = ?',
                     (name, due_date, category_id, priority, task_id))
        conn.commit()
        conn.close()

    if source == 'completed':
        return redirect(url_for('completed', sort=sort))
    return redirect(url_for('index', tab=tab, sort=sort))


@app.route('/task/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    tab = request.form.get('tab', 'all')
    sort = request.form.get('sort', 'due')
    source = request.form.get('source', 'index')

    conn = get_db()
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

    if source == 'completed':
        return redirect(url_for('completed', sort=sort))
    return redirect(url_for('index', tab=tab, sort=sort))


@app.route('/category/add', methods=['POST'])
def add_category():
    name = request.form['category_name'].strip()
    tab = request.form.get('tab', 'all')
    sort = request.form.get('sort', 'due')

    if name:
        conn = get_db()
        conn.execute('INSERT INTO categories (name) VALUES (?)', (name,))
        conn.commit()
        conn.close()

    return redirect(url_for('index', tab=tab, sort=sort))


@app.route('/category/delete/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    sort = request.form.get('sort', 'due')

    conn = get_db()
    conn.execute('DELETE FROM tasks WHERE category_id = ?', (category_id,))
    conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('index', tab='all', sort=sort))


init_db()

if __name__ == '__main__':
    app.run(debug=True)
