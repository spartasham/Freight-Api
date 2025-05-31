# Freight Dashboard

A **full‑stack freight‑forwarding dashboard** built with Django REST Framework (backend) and React + RTK Query (frontend). This README guides you through setting up and running the project.

---

## 📋 Overview

* **Backend**: Django 5.0, DRF, PostgreSQL, Celery + Redis for CSV ingestion and consolidation tasks.
* **Frontend**: React (Vite/TypeScript), RTK Query, TanStack React Table, Recharts, Chakra UI.

---

## 🚧 Prerequisites

1. **Python** 3.12+
2. **Node.js** 18+ and **npm**
3. **PostgreSQL** 13+ (create a database/user)
4. **Redis** (one of):

   * Docker (`docker run --name redis -d -p 6379:6379 redis:7`)
   * Memurai Developer Edition (native Windows)
   * WSL2 + `sudo apt install redis-server`
5. **Docker Desktop** (optional, recommended for Redis/containers)
6. (Optional) **VSCode**, **Postman** or **HTTPie** for API testing

---

## 🔧 Backend Setup (Django API)

1. **Clone the repo**

   ```bash
   git clone https://github.com/your-org/freight-dashboard.git
   cd freight-dashboard
   ```

2. **Backend virtualenv**

   ```bash
   python3 -m venv venv            # or `python -m venv venv`
   source venv/bin/activate        # Unix/macOS
   venv\Scripts\activate         # Windows PowerShell
   python -m pip install -U pip
   ```

3. **Install Python dependencies**

   ```bash
   pip install \
     Django==5.0.* \
     djangorestframework==3.* \
     psycopg2-binary \
     celery[redis] \
     django-cors-headers \
     django-filter \
     drf-spectacular
   ```

4. **Configure database**

   * Edit `backend/settings.py` → `DATABASES['default']` with your PostgreSQL credentials.
   * Create the database and user in psql:

     ```sql
     CREATE USER freight WITH PASSWORD 'secret';
     CREATE DATABASE freight OWNER freight;
     ```

5. **Run migrations**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Start Redis** (if not via Docker)

   * **Docker**: automatically up.
   * **Memurai**: service auto-starts.
   * **WSL**: `sudo service redis-server start`.

7. **Run Celery worker**

   ```bash
   celery -A backend worker --loglevel=info --pool=solo
   ```

8. **Run Django dev server**

   ```bash
   python manage.py runserver
   ```

9. **Verify API**

   * `GET http://localhost:8000/api/shipments/`
   * `GET http://localhost:8000/api/schema/swagger-ui/`

10. **Run tests**

    ```bash
    python manage.py test
    ```

---

## ⚙️ Key Endpoints

| Method | Path                          | Description                                   |
| ------ | ----------------------------- | --------------------------------------------- |
| POST   | `/api/imports/`               | Upload CSV → returns import ID & status       |
| GET    | `/api/imports/{id}/progress/` | Poll import progress                          |
| GET    | `/api/shipments/`             | List shipments (filters & pagination)         |
| GET    | `/api/shipments/{id}/`        | Retrieve shipment detail                      |
| GET    | `/api/metrics/`               | KPIs, carrier breakdown, volume & time series |
| GET    | `/api/consolidations/`        | Persisted consolidation groups & shipments    |

---

## 📘 Documentation

* **Swagger UI**: `/api/schema/swagger-ui/`
* **OpenAPI JSON**: `/api/schema/`

---

## 🏗️ Deployment Tips

* Use Gunicorn + nginx for production:

  ```bash
  pip install gunicorn
  gunicorn backend.wsgi:application --workers 4
  ```
* In Docker Compose, replace Redis host with service name `redis`.
* Configure Celery in a Linux container for multiple workers (no `--pool=solo`).

---

## 🤝 Contributing

1. Fork & branch from `main`.
2. Create feature branch: `git checkout -b feature/xyz`.
3. Commit tests and code.
4. Submit PR with description & review.

---

© 2025 Freight Dashboard Inc. All rights reserved.
