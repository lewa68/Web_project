from flask import jsonify, request
from flask_login import login_required, current_user
from datetime import datetime
from app.models import Task, User, db
from . import api

@api.route('/tasks', methods=['GET'])
@login_required
def get_tasks():
    authored = current_user.authored_tasks.all()
    assigned = current_user.assigned_tasks
    all_tasks = list(set(authored + assigned))
    return jsonify([t.to_dict() for t in all_tasks])

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
    title = data.get('title')
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    task = Task(
        title=title,
        description=data.get('description', ''),
        user_id=current_user.id
    )
    db.session.add(task)
    db.session.flush()

    assignee_ids = data.get('assignee_ids', [])
    if assignee_ids:
        try:
            assignees = []
            for aid in assignee_ids:
                user = User.query.get(aid)
                if user and current_user.can_assign_to(user):
                    assignees.append(user)
            task.assignees.extend(assignees)
        except (ValueError, TypeError):
            pass

    db.session.commit()
    return jsonify(task.to_dict()), 201

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