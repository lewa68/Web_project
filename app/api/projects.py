from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models import Project, db

api = Blueprint('projects', __name__)

@api.route('/projects', methods=['GET'])
@login_required
def get_projects():
    projects = Project.query.all()
    return jsonify([p.to_dict() for p in projects])

@api.route('/projects/<int:id>', methods=['GET'])
@login_required
def get_project(id):
    project = Project.query.get_or_404(id)
    return jsonify(project.to_dict())

@api.route('/projects', methods=['POST'])
@login_required
def create_project():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    if len(name) > 100:
        return jsonify({'error': 'Name too long'}), 400
        
    project = Project(
        name=name,
        user_id=current_user.id,
        description=data.get('description', '').strip(),
        color=data.get('color', '#3498db')
    )
    db.session.add(project)
    db.session.commit()
    return jsonify(project.to_dict()), 201

@api.route('/projects/<int:id>', methods=['PUT'])
@login_required
def update_project(id):
    project = Project.query.get_or_404(id)
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    if len(name) > 100:
        return jsonify({'error': 'Name too long'}), 400
        
    project.name = name
    project.description = data.get('description', project.description)
    project.color = data.get('color', project.color)
    db.session.commit()
    return jsonify(project.to_dict())

@api.route('/projects/<int:id>', methods=['DELETE'])
@login_required
def delete_project(id):
    project = Project.query.get_or_404(id)
    if project.tasks.count() > 0:
        return jsonify({'error': 'Cannot delete project with tasks'}), 400
    db.session.delete(project)
    db.session.commit()
    return jsonify({'message': 'Project deleted'}), 200