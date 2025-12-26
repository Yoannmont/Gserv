# Gserv

A Django-based platform for managing game server instances using Docker containers. The system provides a REST API for creating, configuring, and managing game servers with support for multiple games, versions, and user roles.

## Overview

Gserv allows users to deploy and manage game servers through a web interface. Each server runs in an isolated Docker container with configurable resources, ports, and environment variables. The platform handles server lifecycle operations including creation, startup, shutdown, updates, and monitoring.

## Features

- Multi-game support with version management
- Docker-based server deployment
- User authentication and authorization with JWT
- Role-based access control for server management
- Health check monitoring for server instances
- Resource limits and port mapping configuration
- Server metrics collection (CPU, memory, players)
- Asynchronous task processing with Celery
- RESTful API with Django REST Framework

## Technology Stack

- Django 6.0
- Django REST Framework
- PostgreSQL (production) / SQLite (development)
- Docker SDK for Python
- Celery with Redis
- JWT authentication
- Channels for WebSocket support

## Project Structure

```
Gserv/
├── accounts/          # User authentication and profiles
├── games/             # Game definitions and versions
├── servers/           # Server instances and management
├── docker_manager/    # Docker container management
├── api/               # API routing and configuration
├── config/            # Django settings and configuration
└── requirements/      # Python dependencies
```

## Prerequisites

- Python 3.12+
- Docker and Docker SDK
- Redis (for Celery)
- PostgreSQL (for production)

## Installation

### Development Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd Gserv
```

2. Create and activate a virtual environment:
```bash
python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements/dev.lock
```

4. Create a `.env` file in the project root with required variables, use .env.example to help:
```env
SECRET_KEY=your-secret-key-here
DOCKER_HOST=unix://var/run/docker.sock
CELERY_BROKER_URL=redis://localhost:6379/0
CORS_ALLOWED_ORIGINS=http://localhost:3000
SERVERS_DATA_PATH=/path/to/servers/data
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Create a superuser:
```bash
python manage.py createsuperuser
```

7. Start the development server:
```bash
python manage.py runserver
```

8. In a separate terminal, start Celery worker:
```bash
celery -A config worker -l info
```

9. Start Celery beat (for scheduled tasks):
```bash
celery -A config beat -l info
```

## Configuration

### Docker Configuration

The system requires access to a Docker daemon. Ensure Docker is running and accessible. The default connection uses the Unix socket at `/var/run/docker.sock`. For remote Docker hosts, configure `DOCKER_HOST` accordingly.

## API Documentation

The API documentation is automatically generated using drf-yasg and is available at:

- **Swagger UI**: `http://localhost:8000/swagger/`
- **ReDoc**: `http://localhost:8000/redoc/`
- **OpenAPI Schema (JSON)**: `http://localhost:8000/swagger.json`
- **OpenAPI Schema (YAML)**: `http://localhost:8000/swagger.yaml`

The Swagger UI provides an interactive interface to explore and test API endpoints. Authentication tokens can be added using the "Authorize" button in the Swagger UI.

### Authentication

All API endpoints require authentication using JWT tokens:

```bash
# Login
POST /api/auth/login/
{
    "username": "user",
    "password": "password"
}

# Response includes access and refresh tokens
{
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

Include the access token in subsequent requests:
```bash
Authorization: Bearer <access_token>
```

### Example API Usage

**Creating a Server:**
```bash
POST /api/servers/
{
    "name": "My Minecraft Server",
    "game": 1,
    "game_version": 1,
    "description": "A test server",
    "port": 25565,
    "max_players": 20
}
```

**Managing Servers:**
- Start server: `POST /api/servers/{id}/start/`
- Stop server: `POST /api/servers/{id}/stop/`
- Restart server: `POST /api/servers/{id}/restart/`
- Get server metrics: `GET /api/servers/{id}/metrics/`
- Get server logs: `GET /api/servers/{id}/logs/`

**Server Roles:**
Assign management roles to users:
```bash
POST /api/servers/{id}/roles/
{
    "username_input": "username",
    "role": "manager"
}
```

Available roles:
- `viewer`: Read-only access
- `manager`: Can control server (start/stop) but not modify settings
- `editor`: Can modify settings and control server
- `admin`: Full access except server deletion

## Production Deployment

For production deployment:

1. Set `DJANGO_CONFIGURATION=Prod` environment variable
2. Configure production database (PostgreSQL recommended)
3. Set up proper secret key management
4. Configure static files serving
5. Set up reverse proxy (nginx recommended)
6. Configure SSL/TLS certificates
7. Set up monitoring and logging

## Background Tasks

The system uses Celery for asynchronous operations:

- Server creation and deletion
- Server start/stop operations
- Status synchronization with Docker
- Health check monitoring
- Metrics collection

Scheduled tasks run via Celery Beat:
- Container status synchronization
- Server health checks

## Monitoring

Server metrics are collected periodically and available via the API:

- CPU usage percentage
- Memory usage (MB and percentage)
- Players online
- TPS (Ticks Per Second) for supported games
- Uptime in seconds


