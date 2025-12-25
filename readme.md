# Task Manager

Веб-приложение для управления задачами с поддержкой иерархической системы управления пользователями.

---

## Основные функции

- Регистрация и вход пользователей
- Создание задач с возможностью назначения **одному или нескольким пользователям**
- Отметка выполнения задачи с автоматической установкой даты и времени
- Иерархия уровней доступа:
  - Администратор (`access_level = 0`) — максимальные права
  - Обычные пользователи (`access_level ≥ 1`)
  - Пользователь может назначать задачи **только тем, у кого уровень доступа не ниже его собственного**
- Только администратор может изменять уровень доступа других пользователей
- RESTful API для управления задачами
- Защита маршрутов: задачи доступны только авторизованным пользователям
- Главная страница отображается **только для гостей**; после входа — перенаправление на список задач

---

## Технологии

- Python 3.10+
- Flask
- Flask-SQLAlchemy (SQLite)
- Flask-Login
- Flask-WTF
- Jinja2
- REST API
- HTML/CSS

---

## Установка и запуск

### 1. Клонируйте репозиторий:

```bash
git clone https://github.com/lewa68/Web_project.git
cd Web_project
```

### 2. Создайте виртуальное окружение и активируйте его:

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**
```bash
source venv/bin/activate
```

### 3. Установите зависимости:

```bash
pip install -r requirements.txt
```

### 4. Запустите приложение:

```bash
python run.py
```

Приложение будет доступно по адресу: **http://localhost:5000**

---

## REST API

### Эндпоинты задач

- `GET /api/tasks` — список всех задач (видимых пользователю)
- `GET /api/tasks/<id>` — получить задачу по ID
- `POST /api/tasks` — создать задачу
- `PUT /api/tasks/<id>` — обновить задачу
- `DELETE /api/tasks/<id>` — удалить задачу
- `PUT /api/tasks/<id>/complete` — отметить задачу как выполненную

### Примеры запросов

```bash
curl -X GET http://localhost:5000/api/tasks -H "Cookie: session=..."

curl -X POST http://localhost:5000/api/tasks -H "Content-Type: application/json" -d '{"title": "Новая задача", "description": "Описание задачи"}'

curl -X PUT http://localhost:5000/api/tasks/1 -H "Content-Type: application/json" -d '{"title": "Обновленная задача", "description": "Новое описание"}'

curl -X DELETE http://localhost:5000/api/tasks/1

curl -X PUT http://localhost:5000/api/tasks/1/complete
```

### Коды ответов

- `200 OK` — успешный запрос (GET, PUT)
- `201 Created` — задача успешно создана
- `400 Bad Request` — ошибка валидации данных
- `403 Forbidden` — нет прав доступа
- `404 Not Found` — задача не найдена
- `302 Found` — перенаправление (для неавторизованных)

---

## Тестирование

```bash
python -m pytest tests/
```

---

## Структура проекта

```
Web_project/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── auth.py
│   ├── main/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── tasks.py
│   ├── templates/
│   └── static/
├── tests/
│   ├── __init__.py
│   └── test_api.py
├── requirements.txt
├── README.md
└── run.py
```

---

## Данные администратора по умолчанию

При первом запуске автоматически создаётся администратор:

**Логин:** `admin`  
**Пароль:** `admin`