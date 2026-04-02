# Portfolio Backend

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supported-336791?logo=postgresql)](https://www.postgresql.org/)

A backend API for managing portfolio projects, chat, and admin features. Built with FastAPI, designed for extensibility and easy deployment.

---

## Features
- Project management endpoints
- Admin authentication and management
- Real-time chat support (WebSocket)
- Email notifications
- Dockerized for easy deployment

## Tech Stack
- **Python 3.10+**
- **FastAPI**
- **Docker**
- **PostgreSQL** (recommended)

## Getting Started

### Prerequisites
- Python 3.10+
- Docker (optional, for containerized deployment)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/mobadara/portfolio-backend.git
   cd portfolio-backend
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running Locally
```bash
uvicorn app.main:app --reload
```

### Using Docker
```bash
docker build -t portfolio-backend .
docker run -d -p 8000:8000 portfolio-backend
```

### API Documentation
Once running, visit [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API docs (Swagger UI).

## Project Structure
```
app/
  main.py           # FastAPI app entrypoint
  models/           # Database models
  routers/          # API route handlers
  services/         # Business logic and utilities
```

## Author
**Muyiwa Obadara**  
[GitHub: @mobadara](https://github.com/mobadara)  
[X: @m_obadara](https://x.com/m_obadara)

## License
This project is licensed under the MIT License.
