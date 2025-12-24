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
            db.create_all()
            admin = User(username='admin', access_level=0)
            admin.set_password('admin')
            user1 = User(username='user1', access_level=1)
            user1.set_password('pass')
            user2 = User(username='user2', access_level=2)
            user2.set_password('pass')
            db.session.add_all([admin, user1, user2])
            db.session.commit()
        yield client

    os.close(db_fd)
    os.unlink(db_path)

def login(client, username, password):
    return client.post('/login', data={
        'username': username,
        'password': password
    }, follow_redirects=True)

def test_admin_can_create_task_for_anyone(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/tasks', json={
        'title': 'Test',
        'assignee_ids': [2, 3]
    })
    assert rv.status_code == 201
    assert len(rv.json['assignee_ids']) == 2

def test_user1_cannot_assign_to_user2(client):
    login(client, 'user1', 'pass')
    rv = client.post('/api/tasks', json={
        'title': 'Test',
        'assignee_ids': [3]
    })
    assert rv.status_code == 201
    assert rv.json['assignee_ids'] == []

def test_complete_task(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/tasks', json={'title': 'Test'})
    task_id = rv.json['id']
    rv = client.put(f'/api/tasks/{task_id}/complete')
    assert rv.status_code == 200
    assert rv.json['completed_at'] is not None