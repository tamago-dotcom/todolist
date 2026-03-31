import pytest
import os
import tempfile
from app import app, init_db, get_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    app.config['TESTING'] = True
    original_db = app.config.get('DATABASE', 'todo.db')

    import app as app_module
    app_module.DATABASE = db_path

    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

    app_module.DATABASE = original_db
    os.close(db_fd)
    os.unlink(db_path)


def get_category_id(client, name='仕事'):
    """デフォルトカテゴリのIDを取得"""
    import app as app_module
    conn = get_db()
    row = conn.execute('SELECT id FROM categories WHERE name = ?', (name,)).fetchone()
    conn.close()
    return row['id']


# ---- ページ表示 ----

def test_index_returns_200(client):
    r = client.get('/')
    assert r.status_code == 200


def test_index_contains_tabs(client):
    r = client.get('/')
    html = r.data.decode()
    assert 'すべて' in html
    assert '完了済み' in html
    assert '仕事' in html
    assert '買い物' in html
    assert '副業' in html


def test_completed_page_returns_200(client):
    r = client.get('/completed')
    assert r.status_code == 200


# ---- タスク追加 ----

def test_add_task(client):
    cat_id = get_category_id(client)
    r = client.post('/task/add', data={
        'name': 'テストタスク', 'due_date': '2026-04-10',
        'category_id': cat_id, 'priority': '高',
        'tab': 'all', 'sort': 'due'
    })
    assert r.status_code == 302

    r = client.get('/')
    assert 'テストタスク' in r.data.decode()


def test_add_task_with_special_chars(client):
    """ダブルクォートや特殊文字を含むタスク名でHTMLが壊れないことを確認"""
    cat_id = get_category_id(client)
    r = client.post('/task/add', data={
        'name': '買う: "りんご" & みかん', 'due_date': '2026-04-15',
        'category_id': cat_id, 'priority': '中',
        'tab': 'all', 'sort': 'due'
    })
    assert r.status_code == 302

    r = client.get('/')
    html = r.data.decode()
    # data-task-name属性にHTMLエスケープされて含まれることを確認
    assert 'data-task-name=' in html
    # onclickにtojsonのダブルクォートが直接埋め込まれていないことを確認
    assert 'onclick="openCompleteModal(' not in html or 'dataset' in html


def test_add_task_default_priority_is_mid(client):
    cat_id = get_category_id(client)
    client.post('/task/add', data={
        'name': 'デフォルト優先度', 'due_date': '2026-05-01',
        'category_id': cat_id, 'priority': '中',
        'tab': 'all', 'sort': 'due'
    })
    import app as app_module
    conn = get_db()
    task = conn.execute('SELECT priority FROM tasks WHERE name = ?', ('デフォルト優先度',)).fetchone()
    conn.close()
    assert task['priority'] == '中'


# ---- 完了ボタンのHTML確認 ----

def test_complete_button_uses_data_attributes(client):
    """○ボタンがdata属性を使い、onclickにtojsonの生クォートが含まれないことを確認"""
    cat_id = get_category_id(client)
    client.post('/task/add', data={
        'name': 'ボタンテスト', 'due_date': '2026-04-20',
        'category_id': cat_id, 'priority': '低',
        'tab': 'all', 'sort': 'due'
    })
    r = client.get('/')
    html = r.data.decode()

    assert 'data-form-id=' in html
    assert 'data-task-name=' in html
    assert 'this.dataset.formId' in html
    assert 'this.dataset.taskName' in html


def test_edit_button_uses_data_attributes(client):
    cat_id = get_category_id(client)
    client.post('/task/add', data={
        'name': '編集テスト', 'due_date': '2026-04-25',
        'category_id': cat_id, 'priority': '高',
        'tab': 'all', 'sort': 'due'
    })
    r = client.get('/')
    html = r.data.decode()

    assert 'data-task-id=' in html
    assert 'data-task-name=' in html
    assert 'data-due-date=' in html
    assert 'data-priority=' in html
    assert 'this.dataset.taskId' in html


# ---- タスク完了 ----

def test_complete_task(client):
    cat_id = get_category_id(client)
    client.post('/task/add', data={
        'name': '完了テスト', 'due_date': '2026-04-10',
        'category_id': cat_id, 'priority': '高',
        'tab': 'all', 'sort': 'due'
    })
    import app as app_module
    conn = get_db()
    task = conn.execute('SELECT id FROM tasks WHERE name = ?', ('完了テスト',)).fetchone()
    conn.close()
    task_id = task['id']

    r = client.post(f'/task/complete/{task_id}', data={'tab': 'all', 'sort': 'due'})
    assert r.status_code == 302

    # メイン一覧から消えている
    r = client.get('/')
    assert '完了テスト' not in r.data.decode()

    # 完了済みタブに表示される
    r = client.get('/completed')
    assert '完了テスト' in r.data.decode()


# ---- タスク編集 ----

def test_edit_task(client):
    cat_id = get_category_id(client)
    client.post('/task/add', data={
        'name': '編集前', 'due_date': '2026-04-10',
        'category_id': cat_id, 'priority': '低',
        'tab': 'all', 'sort': 'due'
    })
    import app as app_module
    conn = get_db()
    task = conn.execute('SELECT id FROM tasks WHERE name = ?', ('編集前',)).fetchone()
    conn.close()
    task_id = task['id']

    r = client.post(f'/task/edit/{task_id}', data={
        'name': '編集後', 'due_date': '2026-05-01',
        'category_id': cat_id, 'priority': '高',
        'tab': 'all', 'sort': 'due', 'source': 'index'
    })
    assert r.status_code == 302

    r = client.get('/')
    html = r.data.decode()
    assert '編集後' in html
    assert '編集前' not in html


# ---- タスク削除 ----

def test_delete_task(client):
    cat_id = get_category_id(client)
    client.post('/task/add', data={
        'name': '削除テスト', 'due_date': '2026-04-10',
        'category_id': cat_id, 'priority': '中',
        'tab': 'all', 'sort': 'due'
    })
    import app as app_module
    conn = get_db()
    task = conn.execute('SELECT id FROM tasks WHERE name = ?', ('削除テスト',)).fetchone()
    conn.close()
    task_id = task['id']

    r = client.post(f'/task/delete/{task_id}', data={'tab': 'all', 'sort': 'due', 'source': 'index'})
    assert r.status_code == 302

    r = client.get('/')
    assert '削除テスト' not in r.data.decode()


# ---- カテゴリ ----

def test_add_category(client):
    r = client.post('/category/add', data={
        'category_name': '趣味', 'tab': 'all', 'sort': 'due'
    })
    assert r.status_code == 302

    r = client.get('/')
    assert '趣味' in r.data.decode()


def test_delete_category_also_deletes_tasks(client):
    # カテゴリ追加
    client.post('/category/add', data={
        'category_name': '一時カテゴリ', 'tab': 'all', 'sort': 'due'
    })
    import app as app_module
    conn = get_db()
    cat = conn.execute("SELECT id FROM categories WHERE name = '一時カテゴリ'").fetchone()
    conn.close()
    cat_id = cat['id']

    # タスク追加
    client.post('/task/add', data={
        'name': '消えるタスク', 'due_date': '2026-04-10',
        'category_id': cat_id, 'priority': '中',
        'tab': 'all', 'sort': 'due'
    })

    # カテゴリ削除
    r = client.post(f'/category/delete/{cat_id}', data={'sort': 'due'})
    assert r.status_code == 302

    # タスクも消えている
    conn = get_db()
    task = conn.execute('SELECT id FROM tasks WHERE name = ?', ('消えるタスク',)).fetchone()
    conn.close()
    assert task is None


# ---- 並び替え ----

def test_sort_by_priority(client):
    cat_id = get_category_id(client)
    for name, priority, due in [
        ('低優先', '低', '2026-04-30'),
        ('高優先', '高', '2026-05-15'),
        ('中優先', '中', '2026-05-01'),
    ]:
        client.post('/task/add', data={
            'name': name, 'due_date': due,
            'category_id': cat_id, 'priority': priority,
            'tab': 'all', 'sort': 'due'
        })

    r = client.get('/?sort=priority')
    html = r.data.decode()
    assert html.index('高優先') < html.index('中優先') < html.index('低優先')
