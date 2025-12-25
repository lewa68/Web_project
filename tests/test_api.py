import os
import tempfile
from datetime import date, timedelta

import pytest

from app import create_app, db
from app.models import User, Task, Project, Comment, Subtask


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()

            admin = User(username="admin", access_level=0)
            admin.set_password("admin")
            user1 = User(username="user1", access_level=1)
            user1.set_password("pass1")
            user2 = User(username="user2", access_level=2)
            user2.set_password("pass2")

            db.session.add_all([admin, user1, user2])
            db.session.commit()

        yield client

    with app.app_context():
        db.session.remove()
    os.close(db_fd)
    os.unlink(db_path)


def login(client, username, password):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def logout(client):
    return client.get("/logout", follow_redirects=True)


def test_get_tasks_requires_auth(client):
    rv = client.get("/api/tasks")
    assert rv.status_code in (302, 401)


def test_get_tasks_basic(client):
    login(client, "user1", "pass1")
    rv = client.get("/api/tasks")
    assert rv.status_code == 200
    assert isinstance(rv.get_json(), list)


def test_create_task_success_minimal(client):
    login(client, "user1", "pass1")
    rv = client.post("/api/tasks", json={"title": "Test Task"})
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["title"] == "Test Task"
    assert data["status"] == "todo"


def test_create_task_validation_title_required(client):
    login(client, "user1", "pass1")
    rv = client.post("/api/tasks", json={"description": "no title"})
    assert rv.status_code == 400
    assert "error" in rv.get_json()


def test_create_task_validation_title_too_long(client):
    login(client, "user1", "pass1")
    long_title = "a" * 201
    rv = client.post("/api/tasks", json={"title": long_title})
    assert rv.status_code == 400
    assert "Title too long" in rv.get_json()["error"]


def test_create_task_validation_description_too_long(client):
    login(client, "user1", "pass1")
    long_desc = "a" * 2001
    rv = client.post("/api/tasks", json={"title": "t", "description": long_desc})
    assert rv.status_code == 400
    assert "Description too long" in rv.get_json()["error"]


def test_create_task_invalid_project_id(client):
    login(client, "user1", "pass1")
    rv = client.post(
        "/api/tasks", json={"title": "Task", "project_id": 999999}
    )
    assert rv.status_code == 400
    assert "Invalid project_id" in rv.get_json()["error"]


def test_create_task_deadline_and_priority(client):
    login(client, "user1", "pass1")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    rv = client.post(
        "/api/tasks",
        json={"title": "With deadline", "deadline": tomorrow, "priority": 4},
    )
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["deadline"] == tomorrow
    assert data["priority"] == 4


def test_create_task_invalid_deadline_format(client):
    login(client, "user1", "pass1")
    rv = client.post(
        "/api/tasks",
        json={"title": "Bad deadline", "deadline": "31-12-2025"},
    )
    assert rv.status_code == 400
    assert "Invalid deadline format" in rv.get_json()["error"]


def test_create_task_priority_out_of_range_defaults_to_2(client):
    login(client, "user1", "pass1")
    rv = client.post(
        "/api/tasks",
        json={"title": "Bad priority", "priority": 999},
    )
    assert rv.status_code == 201
    assert rv.get_json()["priority"] == 2


def test_admin_can_assign_to_anyone(client):
    login(client, "admin", "admin")
    rv = client.post(
        "/api/tasks",
        json={"title": "Admin Task", "assignee_ids": [2, 3]},
    )
    assert rv.status_code == 201
    assert len(rv.get_json()["assignee_ids"]) == 2


def test_user_cannot_assign_to_higher_level(client):
    login(client, "user2", "pass2")
    rv = client.post(
        "/api/tasks",
        json={"title": "Restricted Task", "assignee_ids": [1]},
    )
    assert rv.status_code == 201
    assert rv.get_json()["assignee_ids"] == []


def test_create_task_with_subtasks(client):
    login(client, "user1", "pass1")
    rv = client.post(
        "/api/tasks",
        json={
            "title": "With subtasks",
            "subtasks": [
                {"title": "sub1"},
                {"title": "sub2", "completed": True},
                {"title": "   "},
            ],
        },
    )
    assert rv.status_code == 201
    data = rv.get_json()
    assert len(data["subtasks"]) == 2


def test_get_task_visibility_and_404(client):
    login(client, "user1", "pass1")
    rv = client.post("/api/tasks", json={"title": "User1 Task"})
    task_id = rv.get_json()["id"]
    rv = client.get(f"/api/tasks/{task_id}")
    assert rv.status_code == 200
    logout(client)
    login(client, "user2", "pass2")
    rv = client.get(f"/api/tasks/{task_id}")
    assert rv.status_code == 403
    rv = client.get("/api/tasks/999999")
    assert rv.status_code == 404


def test_filter_tasks_by_status(client):
    login(client, "admin", "admin")
    rv = client.post("/api/tasks", json={"title": "Todo Task", "status": "todo"})
    assert rv.status_code == 201
    rv = client.post("/api/tasks", json={"title": "Done Task", "status": "done"})
    assert rv.status_code == 201

    rv = client.get("/api/tasks?status=todo")
    assert rv.status_code == 200
    tasks = rv.get_json() or []
    assert all(t["status"] == "todo" for t in tasks)




def test_filter_tasks_by_overdue(client):
    login(client, "admin", "admin")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    rv = client.post("/api/tasks", json={"title": "Overdue", "deadline": yesterday})
    assert rv.status_code == 201

    rv = client.get("/api/tasks?overdue=true")
    assert rv.status_code == 200
    tasks = rv.get_json() or []
    assert all(
        t["deadline"] < date.today().isoformat() and t["completed_at"] is None
        for t in tasks
    )




def test_filter_tasks_by_due_today(client):
    login(client, "admin", "admin")
    today = date.today().isoformat()
    rv = client.post("/api/tasks", json={"title": "Due", "deadline": today})
    assert rv.status_code == 201

    rv = client.get("/api/tasks?due_today=true")
    assert rv.status_code == 200
    tasks = rv.get_json() or []
    assert all(
        t["deadline"] == today and t["completed_at"] is None
        for t in tasks
    )




def test_update_task_success_and_fields(client):
    login(client, "user1", "pass1")
    rv = client.post("/api/tasks", json={"title": "Original"})
    task_id = rv.get_json()["id"]
    today = date.today().isoformat()
    rv = client.put(
        f"/api/tasks/{task_id}",
        json={
            "title": "Updated",
            "description": "Desc",
            "status": "in_progress",
            "priority": 3,
            "deadline": today,
        },
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["title"] == "Updated"
    assert data["description"] == "Desc"
    assert data["status"] == "in_progress"
    assert data["priority"] == 3
    assert data["deadline"] == today


def test_update_task_forbidden_for_non_author(client):
    login(client, "user1", "pass1")
    rv = client.post("/api/tasks", json={"title": "User1 Task"})
    task_id = rv.get_json()["id"]
    logout(client)
    login(client, "user2", "pass2")
    rv = client.put(f"/api/tasks/{task_id}", json={"title": "Hacked"})
    assert rv.status_code == 403


def test_update_task_validation_and_project_reset(client):
    login(client, "admin", "admin")

    rv = client.post("/api/projects", json={"name": "P1"})
    assert rv.status_code == 201
    project_id = rv.get_json()["id"]

    rv = client.post(
        "/api/tasks", json={"title": "With project", "project_id": project_id}
    )
    assert rv.status_code == 201
    task_id = rv.get_json()["id"]

    rv = client.put(f"/api/tasks/{task_id}", json={"title": ""})
    assert rv.status_code == 400
    assert "error" in (rv.get_json() or {})

    rv = client.put(
        f"/api/tasks/{task_id}",
        json={"title": "New title", "project_id": 0},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["project_id"] is None

    rv = client.put(
        f"/api/tasks/{task_id}",
        json={"title": "New title", "project_id": 999999},
    )
    assert rv.status_code == 400
    assert "Invalid project_id" in rv.get_json()["error"]



def test_update_task_assignees_replace_and_permissions(client):
    login(client, "admin", "admin")
    rv = client.post("/api/tasks", json={"title": "With assignees"})
    task_id = rv.get_json()["id"]
    rv = client.put(
        f"/api/tasks/{task_id}",
        json={"title": "With assignees", "assignee_ids": [2]},
    )
    assert rv.status_code == 200
    assert rv.get_json()["assignee_ids"] == [2]
    logout(client)
    login(client, "user2", "pass2")
    rv = client.put(
        f"/api/tasks/{task_id}",
        json={"title": "With assignees 2", "assignee_ids": [1]},
    )
    assert rv.status_code == 403


def test_delete_task_success_and_404(client):
    login(client, "user1", "pass1")
    rv = client.post("/api/tasks", json={"title": "To Delete"})
    task_id = rv.get_json()["id"]
    rv = client.delete(f"/api/tasks/{task_id}")
    assert rv.status_code == 200
    assert rv.get_json()["message"] == "Task deleted"
    rv = client.get(f"/api/tasks/{task_id}")
    assert rv.status_code == 404


def test_delete_task_forbidden_for_not_author(client):
    login(client, "user1", "pass1")
    rv = client.post("/api/tasks", json={"title": "User1 task"})
    task_id = rv.get_json()["id"]
    logout(client)
    login(client, "user2", "pass2")
    rv = client.delete(f"/api/tasks/{task_id}")
    assert rv.status_code == 403


def test_delete_task_not_found(client):
    login(client, "user1", "pass1")
    rv = client.delete("/api/tasks/999999")
    assert rv.status_code == 404


def test_complete_task_visibility_and_state(client):
    login(client, "user1", "pass1")
    rv = client.post("/api/tasks", json={"title": "To complete"})
    task_id = rv.get_json()["id"]
    rv = client.put(f"/api/tasks/{task_id}/complete")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["completed_at"] is not None
    logout(client)
    login(client, "user2", "pass2")
    rv = client.put(f"/api/tasks/{task_id}/complete")
    assert rv.status_code == 403


def test_add_comment_validation_and_visibility(client):
    login(client, "admin", "admin")
    rv = client.post("/api/tasks", json={"title": "For comments"})
    task_id = rv.get_json()["id"]
    rv = client.post(f"/api/tasks/{task_id}/comments", json={"content": ""})
    assert rv.status_code == 400
    long_content = "a" * 1001
    rv = client.post(
        f"/api/tasks/{task_id}/comments", json={"content": long_content}
    )
    assert rv.status_code == 400
    rv = client.post(
        f"/api/tasks/{task_id}/comments", json={"content": "ok"}
    )
    assert rv.status_code == 201
    comment_id = rv.get_json()["id"]
    logout(client)
    login(client, "user2", "pass2")
    rv = client.post(
        f"/api/tasks/{task_id}/comments", json={"content": "denied"}
    )
    assert rv.status_code == 403
    logout(client)
    login(client, "admin", "admin")
    rv = client.delete(f"/api/comments/{comment_id}")
    assert rv.status_code == 200


def test_delete_comment_permissions(client):
    login(client, "admin", "admin")
    rv = client.post("/api/tasks", json={"title": "Task"})
    task_id = rv.get_json()["id"]
    rv = client.post(
        f"/api/tasks/{task_id}/comments", json={"content": "by admin"}
    )
    comment_id = rv.get_json()["id"]
    logout(client)
    login(client, "user1", "pass1")
    rv = client.delete(f"/api/comments/{comment_id}")
    assert rv.status_code == 403
    logout(client)
    login(client, "admin", "admin")
    rv = client.delete(f"/api/comments/{comment_id}")
    assert rv.status_code == 200


def test_add_subtask_validation_and_permissions(client):
    login(client, "admin", "admin")
    rv = client.post("/api/tasks", json={"title": "Task with sub"})
    task_id = rv.get_json()["id"]
    rv = client.post(f"/api/tasks/{task_id}/subtasks", json={"title": ""})
    assert rv.status_code == 400
    long_title = "a" * 101
    rv = client.post(
        f"/api/tasks/{task_id}/subtasks", json={"title": long_title}
    )
    assert rv.status_code == 400
    rv = client.post(
        f"/api/tasks/{task_id}/subtasks", json={"title": "Subtask 1"}
    )
    assert rv.status_code == 201
    subtask_id = rv.get_json()["id"]
    logout(client)
    login(client, "user1", "pass1")
    rv = client.post(
        f"/api/tasks/{task_id}/subtasks", json={"title": "no access"}
    )
    assert rv.status_code == 403
    logout(client)
    login(client, "admin", "admin")
    rv = client.put(
        f"/api/subtasks/{subtask_id}", json={"completed": True}
    )
    assert rv.status_code == 200
    assert rv.get_json()["completed"] is True
    rv = client.delete(f"/api/subtasks/{subtask_id}")
    assert rv.status_code == 200


def test_update_subtask_permissions(client):
    login(client, "admin", "admin")
    rv = client.post("/api/tasks", json={"title": "Task"})
    task_id = rv.get_json()["id"]
    rv = client.post(
        f"/api/tasks/{task_id}/subtasks", json={"title": "s"}
    )
    subtask_id = rv.get_json()["id"]
    logout(client)
    login(client, "user1", "pass1")
    rv = client.put(
        f"/api/subtasks/{subtask_id}", json={"completed": True}
    )
    assert rv.status_code == 403
    rv = client.delete(f"/api/subtasks/{subtask_id}")
    assert rv.status_code == 403


def test_projects_crud_and_validation(client):
    login(client, "admin", "admin")

    rv = client.post(
        "/api/projects",
        json={"name": "Test Project", "description": "Desc", "color": "#ff0000"},
    )
    assert rv.status_code == 201
    data = rv.get_json()
    project_id = data["id"]
    assert data["name"] == "Test Project"

    rv = client.post("/api/projects", json={"description": "No name"})
    assert rv.status_code == 400
    assert "error" in (rv.get_json() or {})

    rv = client.get("/api/projects")
    assert rv.status_code == 200
    assert any(p["id"] == project_id for p in (rv.get_json() or []))

    rv = client.get(f"/api/projects/{project_id}")
    assert rv.status_code == 200
    assert rv.get_json()["id"] == project_id

    rv = client.put(
        f"/api/projects/{project_id}",
        json={"name": "New Name", "description": "Updated"},
    )
    assert rv.status_code == 200
    assert rv.get_json()["name"] == "New Name"

    rv = client.delete(f"/api/projects/{project_id}")
    assert rv.status_code == 200
    assert rv.get_json()["message"] == "Project deleted"

    rv = client.get(f"/api/projects/{project_id}")
    assert rv.status_code == 404