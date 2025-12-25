from flask import jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, date
from app.models import Task, User, Project, Comment, Subtask, db
from . import api

@api.route('/tasks', methods=['GET'])
@login_required
def get_tasks():
    query = Task.query.filter(
        (Task.user_id == current_user.id) | (Task.assignees.contains(current_user))
    )

    status = request.args.get('status')
    if status in ['todo', 'in_progress', 'review', 'done']:
        query = query.filter(Task.status == status)

    overdue = request.args.get('overdue')
    if overdue == 'true':
        query = query.filter(Task.deadline < date.today(), Task.completed_at.is_(None))

    due_today = request.args.get('due_today')
    if due_today == 'true':
        query = query.filter(Task.deadline == date.today(), Task.completed_at.is_(None))

    tasks = query.all()
    return jsonify([t.to_dict() for t in tasks])

@api.route('/tasks/<int:id>', methods=['GET'])
@login_required
def get_task(id):
    task = Task.query.get_or_404(id)
    if not task.is_visible_to(current_user):
        return jsonify({'error': 'Access denied'}), 403
    return jsonify(task.to_dict())

@api.route('/tasks', methods=['POST'])
@login_required
def create_task():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    if len(title) > 200:
        return jsonify({'error': 'Title too long (max 200 characters)'}), 400
    if len(data.get('description', '')) > 2000:
        return jsonify({'error': 'Description too long (max 2000 characters)'}), 400

    project_id = data.get('project_id')
    if project_id is not None:
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Invalid project_id'}), 400

    priority = data.get('priority', 2)
    if priority not in [1, 2, 3, 4]:
        priority = 2

    deadline = None
    if data.get('deadline'):
        try:
            deadline = datetime.strptime(data['deadline'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid deadline format. Use YYYY-MM-DD'}), 400

    task = Task(
        title=title,
        description=data.get('description', '').strip(),
        user_id=current_user.id,
        project_id=project_id,
        status=data.get('status', 'todo'),
        priority=priority,
        deadline=deadline
    )
    db.session.add(task)
    db.session.flush()

    assignee_ids = data.get('assignee_ids', [])
    if assignee_ids:
        assignees = []
        for aid in assignee_ids:
            user = User.query.get(aid)
            if user and current_user.can_assign_to(user):
                assignees.append(user)
        task.assignees.extend(assignees)

    subtasks_data = data.get('subtasks', [])
    for sub in subtasks_data:
        if isinstance(sub, dict) and 'title' in sub:
            title = sub['title'].strip()
            if title:
                st = Subtask(title=title, completed=sub.get('completed', False))
                task.subtasks.append(st)

    db.session.commit()
    return jsonify(task.to_dict()), 201

@api.route('/tasks/<int:id>', methods=['PUT'])
@login_required
def update_task(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    if len(title) > 200:
        return jsonify({'error': 'Title too long (max 200 characters)'}), 400
    if len(data.get('description', '')) > 2000:
        return jsonify({'error': 'Description too long (max 2000 characters)'}), 400

    project_id = data.get('project_id')
    if project_id is not None:
        if project_id == 0:
            project_id = None
        else:
            project = Project.query.get(project_id)
            if not project:
                return jsonify({'error': 'Invalid project_id'}), 400

    priority = data.get('priority', task.priority)
    if priority not in [1, 2, 3, 4]:
        priority = task.priority

    deadline = task.deadline
    if 'deadline' in data:
        if data['deadline'] is None:
            deadline = None
        else:
            try:
                deadline = datetime.strptime(data['deadline'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid deadline format. Use YYYY-MM-DD'}), 400

    task.title = title
    task.description = data.get('description', task.description)
    task.project_id = project_id
    task.status = data.get('status', task.status)
    task.priority = priority
    task.deadline = deadline

    assignee_ids = data.get('assignee_ids', [])
    if isinstance(assignee_ids, list):
        task.assignees.clear()
        for aid in assignee_ids:
            user = User.query.get(aid)
            if user and current_user.can_assign_to(user):
                task.assignees.append(user)

    db.session.commit()
    return jsonify(task.to_dict()), 200

@api.route('/tasks/<int:id>', methods=['DELETE'])
@login_required
def delete_task(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    db.session.delete(task)
    db.session.commit()
    return jsonify({'message': 'Task deleted'}), 200

@api.route('/tasks/<int:id>/complete', methods=['PUT'])
@login_required
def complete_task(id):
    task = Task.query.get_or_404(id)
    if not task.is_visible_to(current_user):
        return jsonify({'error': 'Access denied'}), 403
    if task.completed_at is None:
        task.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify(task.to_dict())

@api.route('/tasks/<int:id>/comments', methods=['POST'])
@login_required
def add_comment(id):
    task = Task.query.get_or_404(id)
    if not task.is_visible_to(current_user):
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json() or {}
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    if len(content) > 1000:
        return jsonify({'error': 'Comment too long'}), 400

    comment = Comment(content=content, user_id=current_user.id, task_id=id)
    db.session.add(comment)
    db.session.commit()
    return jsonify(comment.to_dict()), 201

@api.route('/comments/<int:id>', methods=['DELETE'])
@login_required
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    if comment.user_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Access denied'}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'message': 'Comment deleted'}), 200

@api.route('/tasks/<int:id>/subtasks', methods=['POST'])
@login_required
def add_subtask(id):
    task = Task.query.get_or_404(id)

    if not (current_user.is_admin() or task.user_id == current_user.id):
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    if len(title) > 100:
        return jsonify({'error': 'Title too long'}), 400
    
    subtask = Subtask(title=title, completed=False, task_id=id)
    db.session.add(subtask)
    db.session.commit()
    return jsonify(subtask.to_dict()), 201


@api.route('/subtasks/<int:id>', methods=['PUT'])
@login_required
def update_subtask(id):
    subtask = Subtask.query.get_or_404(id)
    task = subtask.task
    
    if not (current_user.is_admin() or task.user_id == current_user.id):
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json() or {}
    subtask.completed = bool(data.get('completed', subtask.completed))
    db.session.commit()
    return jsonify(subtask.to_dict())


@api.route('/subtasks/<int:id>', methods=['DELETE'])
@login_required
def delete_subtask(id):
    subtask = Subtask.query.get_or_404(id)
    task = subtask.task
    
    if not (current_user.is_admin() or task.user_id == current_user.id):
        return jsonify({'error': 'Access denied'}), 403
    
    db.session.delete(subtask)
    db.session.commit()
    return jsonify({'message': 'Subtask deleted'}), 200
