# Deployment Guide

Support RAG is designed to be easily deployable using Docker. For production environments, we recommend using a managed PostgreSQL and Redis instance, but local Docker containers are provided for quick setup.

## 📦 Production Deployment (Docker Compose)

The easiest way to deploy is using the provided `docker-compose.yml`.

1.  **Prepare the environment**:
    ```bash
    cp .env.example .env
    # Set DEBUG=False
    # Set production API keys
    ```

2.  **Build and Start**:
    ```bash
    docker-compose up -d --build
    ```

## ⚙️ Environment Variables

| Variable | Description | Recommended Value |
|----------|-------------|-------------------|
| `APP_NAME` | Name of the application | Support RAG Engine |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://user:pass@db:5432/rag` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `QDRANT_URL` | Qdrant API URL | `http://qdrant:6333` |
| `OPENAI_API_KEY` | Your OpenAI API key | `sk-...` |
| `TELEGRAM_TOKEN` | Bot token from BotFather | `12345:ABC...` |
| `DEBUG` | Enable auto-reload and verbose logs | `False` |

## 🚀 Scaling Considerations

### 1. API Workers
Increase the number of workers in production by overriding the command in `docker-compose.yml`:
```yaml
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 2. Model Hosting
ML models (`sentence-transformers`, `rerankers`) are currently loaded into memory inside the app container.
- **RAM**: Ensure the server has at least 4GB of RAM (8GB+ recommended for production).
- **GPU**: To use GPU acceleration, use the NVIDIA Container Toolkit and update the Dockerfile to use a CUDA-enabled base image.

### 3. Database
- **Backups**: Regularly backup PostgreSQL using `pg_dump` and Qdrant using its snapshot API.
- **pgvector**: Ensure the vector index (HNSW) is tuned for your document count.

## 🛡️ Security

- **Reverse Proxy**: Always run Support RAG behind a proxy like Nginx or Traefik to handle SSL/TLS.
- **Internal Network**: Keep DB, Redis, and Qdrant in a private Docker network (as configured in the default `docker-compose.yml`).
- **Webhooks**: Always provide a `secret` when registering webhooks and verify the HMAC signature on your side.
