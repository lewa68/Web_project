from app import create_app, db
from app.models import User

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', access_level=0)
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)