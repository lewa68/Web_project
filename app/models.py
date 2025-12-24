from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from datetime import datetime

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

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    completed_at = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    author = db.relationship('User', back_populates='authored_tasks')
    assignees = db.relationship('User', secondary=task_assignees, back_populates='assigned_tasks')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'author_id': self.user_id,
            'assignee_ids': [u.id for u in self.assignees]
        }

    def is_visible_to(self, user):
        return user.id == self.user_id or user in self.assignees

    def __repr__(self):
        return f'<Task {self.title}>'