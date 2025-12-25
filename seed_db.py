import os
import sys
from datetime import datetime, timedelta, date

# Добавляем корневую папку в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Project, Task, Comment, Subtask

def seed_database():
    app = create_app()
    app.app_context().push()

    # Очистка базы
    db.drop_all()
    db.create_all()

    # Создание пользователей
    users = []
    admin = User(username='admin', access_level=0)
    admin.set_password('admin')
    users.append(admin)

    managers = []
    for i in range(1, 4):
        user = User(username=f'manager{i}', access_level=1)
        user.set_password('pass')
        users.append(user)
        managers.append(user)

    workers = []
    for i in range(1, 6):
        user = User(username=f'worker{i}', access_level=2)
        user.set_password('pass')
        users.append(user)
        workers.append(user)

    db.session.add_all(users)
    db.session.commit()

    # Создание проектов
    projects = []
    project_names = ['Разработка сайта', 'Мобильное приложение', 'Маркетинговая кампания']
    colors = ['#3498db', '#e74c3c', '#2ecc71']
    
    for i, (name, color) in enumerate(zip(project_names, colors)):
        project = Project(
            name=name,
            description=f'Проект {name.lower()} для компании',
            color=color,
            user_id=admin.id
        )
        projects.append(project)
        db.session.add(project)
    db.session.commit()

    # Создание задач
    tasks = []
    statuses = ['todo', 'in_progress', 'review', 'done']
    priorities = [1, 2, 3, 4]
    titles = [
        'Создать макет главной страницы',
        'Реализовать авторизацию',
        'Написать API для пользователей',
        'Тестирование функционала',
        'Подготовить презентацию',
        'Настроить аналитику',
        'Исправить баги в мобильной версии',
        'Обновить документацию',
        'Провести код-ревью',
        'Развернуть на продакшене'
    ]

    for i, title in enumerate(titles):
        status = statuses[i % len(statuses)]
        priority = priorities[i % len(priorities)]
        project = projects[i % len(projects)]
        author = managers[i % len(managers)]
        
        # Дедлайн: от сегодня до +30 дней
        deadline = date.today() + timedelta(days=(i * 3) % 30)
        
        task = Task(
            title=title,
            description=f'Подробное описание задачи "{title}"',
            status=status,
            priority=priority,
            deadline=deadline,
            user_id=author.id,
            project_id=project.id,
            created_at=datetime.now() - timedelta(hours=i*2)
        )
        tasks.append(task)
        db.session.add(task)
    db.session.commit()

    # Назначение исполнителей
    for i, task in enumerate(tasks):
        # Назначаем 1-2 исполнителей
        assignees = []
        if i % 3 == 0:
            assignees = workers[:2]
        elif i % 3 == 1:
            assignees = [workers[i % len(workers)]]
        else:
            assignees = [workers[(i+1) % len(workers)]]
        
        task.assignees.extend(assignees)
    db.session.commit()

    # Создание подзадач
    subtask_titles = ['Исследование', 'Реализация', 'Тестирование', 'Документация']
    for i, task in enumerate(tasks):
        for j in range(2 + (i % 3)):
            completed = (j == 0)  # Первую подзадачу помечаем как выполненную
            subtask = Subtask(
                title=f'{subtask_titles[j % len(subtask_titles)]} для "{task.title[:20]}..."',
                completed=completed,
                task_id=task.id
            )
            db.session.add(subtask)
    db.session.commit()

    # Создание комментариев
    comments = [
        'Начал работу над задачей',
        'Возникли сложности с API',
        'Требуется помощь менеджера',
        'Задача почти готова',
        'Проверьте, пожалуйста',
        'Отличная работа!',
        'Нужно доработать согласно ТЗ',
        'Сроки горят!'
    ]
    
    for i, task in enumerate(tasks):
        for j in range(i % 4):  # 0-3 комментария на задачу
            author = workers[j % len(workers)] if j % 2 == 0 else managers[j % len(managers)]
            comment = Comment(
                content=comments[(i + j) % len(comments)],
                user_id=author.id,
                task_id=task.id,
                created_at=task.created_at + timedelta(minutes=(j+1)*30)
            )
            db.session.add(comment)
    db.session.commit()

    print('База данных успешно заполнена тестовыми данными!')
    print(f'Пользователей: {len(users)}')
    print(f'Проектов: {len(projects)}')
    print(f'Задач: {len(tasks)}')
    print('\nДанные для входа:')
    print('Админ: admin / admin')
    print('Менеджер: manager1 / pass')
    print('Исполнитель: worker1 / pass')

if __name__ == '__main__':
    seed_database()