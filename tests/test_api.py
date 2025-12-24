import os
import tempfile
import pytest
from app import create_app, db
from app.models import User, Task

@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['WTF_CSRF_ENABLED'] = False

    with app.test_client() as client:
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()

            admin = User(username='admin', access_level=0)
            admin.set_password('admin')
            user1 = User(username='user1', access_level=1)
            user1.set_password('pass1')
            user2 = User(username='user2', access_level=2)
            user2.set_password('pass2')
            db.session.add_all([admin, user1, user2])
            db.session.commit()

            assert User.query.count() == 3

        yield client

        with app.app_context():
            db.session.remove()

    os.close(db_fd)
    os.unlink(db_path)

def login(client, username, password):
    return client.post('/login', data={
        'username': username,
        'password': password
    }, follow_redirects=True)

def test_get_tasks_success(client):
    login(client, 'user1', 'pass1')
    rv = client.get('/api/tasks')
    assert rv.status_code == 200
    assert isinstance(rv.json, list)

def test_get_tasks_unauthorized(client):
    rv = client.get('/api/tasks')
    assert rv.status_code == 302

def test_create_task_success(client):
    login(client, 'user1', 'pass1')
    rv = client.post('/api/tasks', json={
        'title': 'Test Task',
        'description': 'Test Description'
    })
    assert rv.status_code == 201
    assert rv.json['title'] == 'Test Task'
    assert rv.json['description'] == 'Test Description'

def test_create_task_missing_title(client):
    login(client, 'user1', 'pass1')
    rv = client.post('/api/tasks', json={'description': 'No title'})
    assert rv.status_code == 400
    assert 'error' in rv.json

def test_update_task_success(client):
    login(client, 'user1', 'pass1')
    rv = client.post('/api/tasks', json={'title': 'Original'})
    task_id = rv.json['id']
    rv = client.put(f'/api/tasks/{task_id}', json={
        'title': 'Updated Title',
        'description': 'Updated Description'
    })
    assert rv.status_code == 200
    assert rv.json['title'] == 'Updated Title'

def test_update_task_forbidden(client):
    login(client, 'user1', 'pass1')
    rv = client.post('/api/tasks', json={'title': 'User1 Task'})
    task_id = rv.json['id']
    client.get('/logout')
    login(client, 'user2', 'pass2')
    rv = client.put(f'/api/tasks/{task_id}', json={'title': 'Hacked'})
    assert rv.status_code == 403

def test_delete_task_success(client):
    login(client, 'user1', 'pass1')
    rv = client.post('/api/tasks', json={'title': 'To Delete'})
    task_id = rv.json['id']
    rv = client.delete(f'/api/tasks/{task_id}')
    assert rv.status_code == 200
    assert rv.json['message'] == 'Task deleted'
    rv = client.get(f'/api/tasks/{task_id}')
    assert rv.status_code == 404

def test_delete_task_not_found(client):
    login(client, 'user1', 'pass1')
    rv = client.delete('/api/tasks/999999')
    assert rv.status_code == 404

def test_admin_can_assign_to_anyone(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/tasks', json={
        'title': 'Admin Task',
        'assignee_ids': [2, 3]
    })
    assert rv.status_code == 201
    assert len(rv.json['assignee_ids']) == 2

def test_user_cannot_assign_to_higher_level(client):
    login(client, 'user2', 'pass2')
    rv = client.post('/api/tasks', json={
        'title': 'Restricted Task',
        'assignee_ids': [2]
    })
    assert rv.status_code == 201
    assert rv.json['assignee_ids'] == []