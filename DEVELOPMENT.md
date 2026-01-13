# Development Guide

This document provides instructions for developers who want to contribute to Support RAG or run it locally for development purposes.

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed:
- **Python**: 3.9 or higher
- **Docker & Docker Compose**: For running infrastructure services (PostgreSQL, Redis, Qdrant)
- **Git**: For version control

## 🚀 Local Setup

Follow these steps to set up your development environment:

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/letya999/support_rag.git
    cd support_rag
    ```

2.  **Create a Virtual Environment**
    ```bash
    python -m venv venv
    # Activate on Windows:
    .\venv\Scripts\activate
    # Activate on Linux/macOS:
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration**
    Copy the example environment file and fill in your details (API keys, DB credentials, etc.):
    ```bash
    cp .env.example .env
    ```

5.  **Start Infrastructure Services**
    Use Docker Compose to start PostgreSQL, Redis, and Qdrant:
    ```bash
    docker-compose up -d db redis qdrant
    ```

6.  **Run Database Migrations**
    ```bash
    python scripts/run_migrations.py
    ```

## 🏗️ Running the Application

### Start the API Server
Run the FastAPI application with auto-reload enabled:
```bash
uvicorn app.main:app --reload --port 8000
```
The API will be available at `http://localhost:8000`. You can access the Interactive Swagger UI at `http://localhost:8000/docs`.

### Start the Telegram Bot
If you are developing the Telegram integration:
```bash
# Ensure TELEGRAM_BOT_TOKEN is set in your .env
python -m app.bot.main
```

## 📂 Project Structure

- `app/`: Source code of the application.
  - `api/`: FastAPI routers and schemas.
  - `core/`: Core configurations and base classes.
  - `nodes/`: The pipeline "Nodes" that define the RAG logic.
  - `services/`: Business logic and database interactions.
  - `models/`: Database models and Pydantic schemas.
- `scripts/`: Utility scripts for ingestion, migrations, and benchmarking.
- `datasets/`: Sample data for testing and ingestion.
- `docs/`: Detailed documentation files.

## 🧪 Development Workflow

### Adding a New Node
1.  Create a new directory in `app/nodes/`.
2.  Extend the `BaseNode` class.
3.  Define `INPUT_CONTRACT` and `OUTPUT_CONTRACT`.
4.  Implement the `execute` method.
5.  Register the node in the pipeline configuration.

### Logging
Always use the logger instead of `print()`. We use structured logging to make logs easier to parse in production.
```python
from app.core.logging import logger

logger.info("Processing query", extra={"query": "hello"})
```

## 🤝 Contributing

1.  **Fork** the repository.
2.  Create a **feature branch** (`git checkout -b feature/amazing-feature`).
3.  **Commit** your changes following [Conventional Commits](https://www.conventionalcommits.org/).
4.  **Push** to the branch (`git status`, `git commit`, `git push origin feature/amazing-feature`).
5.  Open a **Pull Request**.

## 🆘 Troubleshooting

- **Database Connection Issues**: Ensure the Docker containers are running (`docker ps`) and the credentials in `.env` match.
- **Dependency Errors**: Try updating pip and reinstalling: `pip install --upgrade pip && pip install -r requirements.txt`.
