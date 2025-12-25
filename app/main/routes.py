from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import main
from app.models import Task, User, Project, Comment, Subtask, db
from datetime import datetime, date

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.tasks'))
    return render_template('index.html')

@main.route('/projects')
@login_required
def projects():
    projects = Project.query.all()
    return render_template('projects.html', projects=projects)

@main.route('/project/new', methods=['POST'])
@login_required
def new_project():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Название проекта обязательно')
        return redirect(url_for('main.projects'))
    if len(name) > 100:
        flash('Название слишком длинное')
        return redirect(url_for('main.projects'))
        
    project = Project(
        name=name,
        description=request.form.get('description', '').strip(),
        color=request.form.get('color', '#3498db'),
        user_id=current_user.id
    )
    db.session.add(project)
    db.session.commit()
    flash('Проект создан')
    return redirect(url_for('main.projects'))

@main.route('/project/<int:id>/edit', methods=['POST'])
@login_required
def edit_project(id):
    project = Project.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    if not name:
        flash('Название проекта обязательно')
        return redirect(url_for('main.projects'))
    if len(name) > 100:
        flash('Название слишком длинное')
        return redirect(url_for('main.projects'))
        
    project.name = name
    project.description = request.form.get('description', project.description)
    project.color = request.form.get('color', project.color)
    db.session.commit()
    flash('Проект обновлён')
    return redirect(url_for('main.projects'))

@main.route('/project/<int:id>/delete', methods=['POST'])
@login_required
def delete_project(id):
    project = Project.query.get_or_404(id)
    if project.tasks.count() > 0:
        flash('Нельзя удалить проект с задачами')
        return redirect(url_for('main.projects'))
    db.session.delete(project)
    db.session.commit()
    flash('Проект удалён')
    return redirect(url_for('main.projects'))

@main.route('/tasks')
@login_required
def tasks():
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
    projects = Project.query.all()
    users = User.query.all()
    return render_template('tasks.html', tasks=tasks, projects=projects, users=users)

@main.route('/task/new', methods=['POST'])
@login_required
def new_task():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    assignee_ids = request.form.getlist('assignees')
    project_id = request.form.get('project_id')
    status = request.form.get('status', 'todo')
    
    priority = 2
    try:
        priority_val = request.form.get('priority')
        if priority_val:
            priority = int(priority_val)
        if priority not in [1, 2, 3, 4]:
            priority = 2
    except (ValueError, TypeError):
        priority = 2

    deadline_str = request.form.get('deadline')

    if not title:
        flash('Заголовок обязателен')
        return redirect(url_for('main.tasks'))
    if len(title) > 200:
        flash('Заголовок слишком длинный (макс. 200 символов)')
        return redirect(url_for('main.tasks'))
    if len(description) > 2000:
        flash('Описание слишком длинное (макс. 2000 символов)')
        return redirect(url_for('main.tasks'))

    deadline = None
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Неверный формат даты')
            return redirect(url_for('main.tasks'))

    if project_id == '0':
        project_id = None
    elif project_id:
        try:
            project_id = int(project_id)
            project = Project.query.get(project_id)
            if not project:
                project_id = None
        except (ValueError, TypeError):
            project_id = None

    task = Task(
        title=title,
        description=description,
        user_id=current_user.id,
        project_id=project_id,
        status=status,
        priority=priority,
        deadline=deadline
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
            flash('Некорректные данные о пользователях')
            return redirect(url_for('main.tasks'))

    db.session.commit()
    flash('Задача создана')
    return redirect(url_for('main.tasks'))

@main.route('/task/<int:id>')
@login_required
def view_task(id):
    task = Task.query.get_or_404(id)
    if not task.is_visible_to(current_user):
        flash('Нет доступа к этой задаче')
        return redirect(url_for('main.tasks'))
    users = User.query.all()
    return render_template('task_detail.html', task=task, users=users)

@main.route('/task/<int:id>/edit', methods=['POST'])
@login_required
def edit_task(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash('Нет прав на редактирование этой задачи')
        return redirect(url_for('main.view_task', id=id))

    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    assignee_ids = request.form.getlist('assignees')
    project_id = request.form.get('project_id')
    status = request.form.get('status', task.status)
    
    priority = task.priority
    try:
        priority_val = request.form.get('priority')
        if priority_val:
            priority = int(priority_val)
        if priority not in [1, 2, 3, 4]:
            priority = task.priority
    except (ValueError, TypeError):
        priority = task.priority

    deadline_str = request.form.get('deadline')

    if not title:
        flash('Заголовок обязателен')
        return redirect(url_for('main.view_task', id=id))
    if len(title) > 200:
        flash('Заголовок слишком длинный (макс. 200 символов)')
        return redirect(url_for('main.view_task', id=id))
    if len(description) > 2000:
        flash('Описание слишком длинное (макс. 2000 символов)')
        return redirect(url_for('main.view_task', id=id))

    deadline = task.deadline
    if deadline_str == '':
        deadline = None
    elif deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Неверный формат даты')
            return redirect(url_for('main.view_task', id=id))

    if project_id == '0':
        project_id = None
    elif project_id:
        try:
            project_id = int(project_id)
            project = Project.query.get(project_id)
            if not project:
                project_id = task.project_id
        except (ValueError, TypeError):
            project_id = task.project_id

    task.title = title
    task.description = description
    task.project_id = project_id
    task.status = status
    task.priority = priority
    task.deadline = deadline

    if assignee_ids:
        try:
            assignee_ids = [int(i) for i in assignee_ids]
            assignees = []
            for aid in assignee_ids:
                user = User.query.get(aid)
                if user and current_user.can_assign_to(user):
                    assignees.append(user)
            task.assignees.clear()
            task.assignees.extend(assignees)
        except (ValueError, TypeError):
            flash('Некорректные данные о пользователях')
            return redirect(url_for('main.view_task', id=id))
    else:
        task.assignees.clear()

    db.session.commit()
    flash('Задача обновлена')
    return redirect(url_for('main.view_task', id=id))

@main.route('/task/<int:id>/complete', methods=['POST'])
@login_required
def complete_task(id):
    task = Task.query.get_or_404(id)
    if not task.is_visible_to(current_user):
        flash('Нет доступа к этой задаче')
        return redirect(url_for('main.view_task', id=id))
    if task.completed_at is None:
        task.completed_at = datetime.utcnow()
        task.status = 'done'
        db.session.commit()
        flash('Задача отмечена как выполненная')
    return redirect(url_for('main.view_task', id=id))

@main.route('/task/<int:id>/mark_done', methods=['POST'])
@login_required
def mark_task_done(id):
    task = Task.query.get_or_404(id)
    if not task.is_visible_to(current_user):
        flash('Нет доступа к этой задаче')
        return redirect(url_for('main.view_task', id=id))
    if not task.can_mark_as_done(current_user):
        flash('Только исполнитель может отметить задачу как выполненную')
        return redirect(url_for('main.view_task', id=id))
    if task.status == 'todo':
        task.status = 'in_progress'
        db.session.commit()
        flash('Задача переведена в "В работе"')
    elif task.status == 'in_progress':
        task.mark_as_done()
        db.session.commit()
        flash('Задача отправлена на проверку')
    return redirect(url_for('main.view_task', id=id))

@main.route('/task/<int:id>/approve', methods=['POST'])
@login_required
def approve_task(id):
    task = Task.query.get_or_404(id)
    if not task.is_visible_to(current_user):
        flash('Нет доступа к этой задаче')
        return redirect(url_for('main.view_task', id=id))
    if not task.can_approve(current_user):
        flash('Только автор задачи может подтвердить её выполнение')
        return redirect(url_for('main.view_task', id=id))
    if task.status != 'review':
        flash('Задача не находится на проверке')
        return redirect(url_for('main.view_task', id=id))
    task.approve()
    db.session.commit()
    flash('Задача подтверждена и завершена')
    return redirect(url_for('main.view_task', id=id))

@main.route('/task/<int:id>/delete', methods=['POST'])
@login_required
def delete_task(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash('Нет прав на удаление этой задачи')
        return redirect(url_for('main.tasks'))
    db.session.delete(task)
    db.session.commit()
    flash('Задача удалена')
    return redirect(url_for('main.tasks'))

@main.route('/task/<int:id>/comment', methods=['POST'])
@login_required
def add_comment(id):
    task = Task.query.get_or_404(id)
    if not task.is_visible_to(current_user):
        flash('Нет доступа')
        return redirect(url_for('main.view_task', id=id))

    content = request.form.get('content', '').strip()
    if not content:
        flash('Комментарий не может быть пустым')
        return redirect(url_for('main.view_task', id=id))

    comment = Comment(content=content, user_id=current_user.id, task_id=id)
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('main.view_task', id=id))

@main.route('/comment/<int:id>/delete', methods=['POST'])
@login_required
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    task_id = comment.task_id
    if comment.user_id != current_user.id and not current_user.is_admin():
        flash('Нет прав на удаление')
        return redirect(url_for('main.view_task', id=task_id))
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('main.view_task', id=task_id))

@main.route('/task/<int:id>/subtask', methods=['POST'])
@login_required
def add_subtask(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash('Нет прав')
        return redirect(url_for('main.view_task', id=id))

    title = request.form.get('title', '').strip()
    if not title:
        flash('Заголовок подзадачи обязателен')
        return redirect(url_for('main.view_task', id=id))

    subtask = Subtask(title=title, completed=False, task_id=id)
    db.session.add(subtask)
    db.session.commit()
    return redirect(url_for('main.view_task', id=id))

@main.route('/subtask/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_subtask(id):
    subtask = Subtask.query.get_or_404(id)
    task_id = subtask.task_id
    if subtask.task.user_id != current_user.id:
        flash('Нет прав')
        return redirect(url_for('main.view_task', id=task_id))
    subtask.completed = not subtask.completed
    db.session.commit()
    return redirect(url_for('main.view_task', id=task_id))

@main.route('/subtask/<int:id>/delete', methods=['POST'])
@login_required
def delete_subtask(id):
    subtask = Subtask.query.get_or_404(id)
    task_id = subtask.task_id
    if subtask.task.user_id != current_user.id:
        flash('Нет прав')
        return redirect(url_for('main.view_task', id=task_id))
    db.session.delete(subtask)
    db.session.commit()
    return redirect(url_for('main.view_task', id=task_id))

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

@main.route('/project/<int:id>')
@login_required
def view_project(id):
    project = Project.query.get_or_404(id)
    tasks = Task.query.filter_by(project_id=id).all()
    return render_template('project_detail.html', project=project, tasks=tasks)

@main.route('/project/<int:project_id>/task/new', methods=['GET'])
@login_required
def new_task_from_project(project_id):
    project = Project.query.get_or_404(project_id)
    projects = Project.query.all()
    users = User.query.all()
    return render_template('tasks.html', tasks=[], projects=projects, users=users, preselected_project_id=project_id)