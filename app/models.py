from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from datetime import datetime, date

task_assignees = db.Table(
    'task_assignees',
    db.Column('task_id', db.Integer, db.ForeignKey('task.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    extend_existing=True
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    access_level = db.Column(db.Integer, default=1, nullable=False)

    authored_tasks = db.relationship('Task', back_populates='author', lazy='dynamic')
    assigned_tasks = db.relationship('Task', secondary=task_assignees, back_populates='assignees')
    comments = db.relationship('Comment', back_populates='author', lazy='dynamic')
    authored_projects = db.relationship('Project', back_populates='author', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.access_level == 0

    def can_manage(self, other):
        return self.is_admin()

    def can_assign_to(self, other):
        return self.access_level <= other.access_level

    def __repr__(self):
        return f'<User {self.username} (L{self.access_level})>'

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#3498db')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    tasks = db.relationship('Task', back_populates='project', lazy='dynamic')
    author = db.relationship('User', back_populates='authored_projects')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'author_id': self.user_id,
            'author_username': self.author.username if self.author else 'Unknown'
        }

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)
    status = db.Column(db.String(20), default='todo')
    priority = db.Column(db.Integer, default=2)
    deadline = db.Column(db.Date, nullable=True)

    author = db.relationship('User', back_populates='authored_tasks')
    assignees = db.relationship('User', secondary=task_assignees, back_populates='assigned_tasks')
    project = db.relationship('Project', back_populates='tasks')
    comments = db.relationship('Comment', back_populates='task', cascade='all, delete-orphan')
    subtasks = db.relationship('Subtask', back_populates='task', cascade='all, delete-orphan')

    def is_visible_to(self, user):
        if user.is_admin():
            return True
        return user.id == self.user_id or user in self.assignees

    def is_overdue(self):
        return self.deadline and self.deadline < date.today() and not self.completed_at

    def get_priority_emoji(self):
        return {1: '🟢', 2: '🟡', 3: '🟠', 4: '🔴'}.get(self.priority, '⚪')

    def get_status_display(self):
        return {
            'todo': 'К выполнению',
            'in_progress': 'В работе',
            'review': 'На проверке',
            'done': 'Готово'
        }.get(self.status, self.status)

    def get_status_color(self):
        return {
            'todo': '#95a5a6',
            'in_progress': '#3498db',
            'review': '#f39c12',
            'done': '#2ecc71'
        }.get(self.status, '#95a5a6')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'author_id': self.user_id,
            'assignee_ids': [u.id for u in self.assignees],
            'project_id': self.project_id,
            'status': self.status,
            'priority': self.priority,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'priority_emoji': self.get_priority_emoji(),
            'is_overdue': self.is_overdue(),
            'subtasks': [s.to_dict() for s in self.subtasks],
            'comments_count': len(self.comments)
        }

    def can_mark_as_done(self, user):
        if user.is_admin():
            return True
        return user in self.assignees

    def can_approve(self, user):
        if user.is_admin():
            return True
        return user.id == self.user_id

    def mark_as_done(self):
        self.status = 'review'
        self.completed_at = None

    def approve(self):
        self.status = 'done'
        self.completed_at = datetime.now()

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

    author = db.relationship('User', back_populates='comments')
    task = db.relationship('Task', back_populates='comments')

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'author': self.author.username,
            'author_id': self.author.id,
            'task_id': self.task_id
        }

class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

    task = db.relationship('Task', back_populates='subtasks')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'completed': self.completed,
            'task_id': self.task_id
        }