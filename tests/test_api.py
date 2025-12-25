import os
import tempfile
import pytest
from app import create_app, db
from app.models import User, Task, Project, Comment, Subtask
from datetime import timedelta

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

def test_create_project_success(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/projects', json={
        'name': 'Test Project',
        'description': 'Project Description',
        'color': '#ff0000'
    })
    assert rv.status_code == 201
    assert rv.json['name'] == 'Test Project'
    assert rv.json['color'] == '#ff0000'

def test_create_project_missing_name(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/projects', json={
        'description': 'No name'
    })
    assert rv.status_code == 400
    assert 'error' in rv.json

def test_get_projects_success(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/projects', json={'name': 'Project A'})
    rv = client.get('/api/projects')
    assert rv.status_code == 200
    assert len(rv.json) >= 1

def test_get_project_by_id(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/projects', json={'name': 'Project B'})
    project_id = rv.json['id']
    rv = client.get(f'/api/projects/{project_id}')
    assert rv.status_code == 200
    assert rv.json['id'] == project_id

def test_update_project_success(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/projects', json={'name': 'Old Name'})
    project_id = rv.json['id']
    rv = client.put(f'/api/projects/{project_id}', json={
        'name': 'New Name',
        'description': 'Updated description'
    })
    assert rv.status_code == 200
    assert rv.json['name'] == 'New Name'

def test_delete_project_success(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/projects', json={'name': 'To Delete'})
    project_id = rv.json['id']
    rv = client.delete(f'/api/projects/{project_id}')
    assert rv.status_code == 200
    assert rv.json['message'] == 'Project deleted'
    rv = client.get(f'/api/projects/{project_id}')
    assert rv.status_code == 404

def test_create_task_with_project(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/projects', json={'name': 'Project X'})
    project_id = rv.json['id']
    rv = client.post('/api/tasks', json={
        'title': 'Task with Project',
        'project_id': project_id
    })
    assert rv.status_code == 201
    assert rv.json['project_id'] == project_id

def test_filter_tasks_by_status(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/tasks', json={'title': 'Todo Task', 'status': 'todo'})
    todo_id = rv.json['id']
    rv = client.post('/api/tasks', json={'title': 'Done Task', 'status': 'done'})
    done_id = rv.json['id']
    
    rv = client.get('/api/tasks?status=todo')
    assert rv.status_code == 200
    task_ids = [t['id'] for t in rv.json]
    assert todo_id in task_ids
    assert done_id not in task_ids

def test_filter_tasks_by_overdue(client):
    from datetime import date
    login(client, 'admin', 'admin')
    deadline = (date.today() - timedelta(days=1)).isoformat()
    rv = client.post('/api/tasks', json={
        'title': 'Overdue Task',
        'deadline': deadline
    })
    overdue_id = rv.json['id']
    rv = client.get('/api/tasks?overdue=true')
    assert rv.status_code == 200
    task_ids = [t['id'] for t in rv.json]
    assert overdue_id in task_ids

def test_add_comment_to_task(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/tasks', json={'title': 'Task for Comment'})
    task_id = rv.json['id']
    rv = client.post(f'/api/tasks/{task_id}/comments', json={
        'content': 'This is a comment'
    })
    assert rv.status_code == 201
    assert rv.json['content'] == 'This is a comment'
    assert rv.json['task_id'] == task_id

def test_delete_comment(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/tasks', json={'title': 'Task with Comment'})
    task_id = rv.json['id']
    rv = client.post(f'/api/tasks/{task_id}/comments', json={
        'content': 'Comment to delete'
    })
    comment_id = rv.json['id']
    rv = client.delete(f'/api/comments/{comment_id}')
    assert rv.status_code == 200
    assert rv.json['message'] == 'Comment deleted'

def test_add_subtask_to_task(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/tasks', json={'title': 'Task with Subtask'})
    task_id = rv.json['id']
    rv = client.post(f'/api/tasks/{task_id}/subtasks', json={
        'title': 'Subtask 1'
    })
    assert rv.status_code == 201
    assert rv.json['title'] == 'Subtask 1'
    assert rv.json['task_id'] == task_id

def test_toggle_subtask(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/tasks', json={'title': 'Task with Subtask'})
    task_id = rv.json['id']
    rv = client.post(f'/api/tasks/{task_id}/subtasks', json={
        'title': 'Subtask to toggle'
    })
    subtask_id = rv.json['id']
    rv = client.put(f'/api/subtasks/{subtask_id}', json={'completed': True})
    assert rv.status_code == 200
    assert rv.json['completed'] == True

def test_delete_subtask(client):
    login(client, 'admin', 'admin')
    rv = client.post('/api/tasks', json={'title': 'Task with Subtask'})
    task_id = rv.json['id']
    rv = client.post(f'/api/tasks/{task_id}/subtasks', json={
        'title': 'Subtask to delete'
    })
    subtask_id = rv.json['id']
    rv = client.delete(f'/api/subtasks/{subtask_id}')
    assert rv.status_code == 200
    assert rv.json['message'] == 'Subtask deleted'