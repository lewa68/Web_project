from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import main
from app.models import Task, User, db
from datetime import datetime

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.tasks'))
    return render_template('index.html')

@main.route('/tasks')
@login_required
def tasks():
    authored = current_user.authored_tasks.all()
    assigned = current_user.assigned_tasks
    all_tasks = list(set(authored + assigned))
    users = User.query.all()
    return render_template('tasks.html', tasks=all_tasks, users=users)

@main.route('/task/new', methods=['POST'])
@login_required
def new_task():
    title = request.form.get('title')
    description = request.form.get('description')
    assignee_ids = request.form.getlist('assignees')

    if not title:
        flash('Заголовок обязателен')
        return redirect(url_for('main.tasks'))

    task = Task(
        title=title,
        description=description,
        user_id=current_user.id
    )
    db.session.add(task)
    db.session.flush()

    if assignee_ids:
        try:
            assignee_ids = [int(i) for i in assignee_ids]
            assignees = []
            for aid in assignee_ids:
                user = User.query.get(aid)
                if user and current_user.can_assign_to(user):
                    assignees.append(user)
            task.assignees.extend(assignees)
        except (ValueError, TypeError):
            pass

    db.session.commit()
    flash('Задача создана')
    return redirect(url_for('main.tasks'))

@main.route('/task/<int:id>/complete', methods=['POST'])
@login_required
def complete_task(id):
    task = Task.query.get_or_404(id)
    if not task.is_visible_to(current_user):
        flash('Нет доступа к этой задаче')
        return redirect(url_for('main.tasks'))
    if task.completed_at is None:
        task.completed_at = datetime.utcnow()
        db.session.commit()
        flash('Задача отмечена как выполненная')
    return redirect(url_for('main.tasks'))

@main.route('/admin')
@login_required
def admin():
    if not current_user.is_admin():
        flash('Доступ запрещён')
        return redirect(url_for('main.tasks'))
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('admin.html', users=users)

@main.route('/admin/user/<int:user_id>/set_level', methods=['POST'])
@login_required
def set_user_access_level(user_id):
    if not current_user.is_admin():
        flash('Нет прав')
        return redirect(url_for('main.admin'))
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Нельзя изменить свой уровень')
        return redirect(url_for('main.admin'))
    try:
        level = int(request.form.get('level', 1))
        if level < 0:
            level = 0
        user.access_level = level
        db.session.commit()
        flash(f'Уровень доступа пользователя {user.username} установлен на {level}')
    except (ValueError, TypeError):
        flash('Некорректный уровень')
    return redirect(url_for('main.admin'))