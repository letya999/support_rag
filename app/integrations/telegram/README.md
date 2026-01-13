# Telegram Bot Integration

## Architecture

This Telegram bot is designed as an **isolated microservice** that communicates with the main RAG API via HTTP.

### Key Principles

1. **No Direct Database Access**: The bot does not connect to PostgreSQL or any other database directly.
2. **HTTP-Only Communication**: All interactions with the RAG system happen through the REST API.
3. **Minimal Dependencies**: The bot has its own minimal requirement set (`requirements.bot.txt`) with no dependencies on internal API modules.
4. **Standard Logging**: Uses standard Python `logging` module, not custom `app.logging_config`.

### Dependency Rules

❌ **FORBIDDEN**:
- Importing from `app.services.*`
- Importing from `app.storage.*`
- Importing from `app.nodes.*`
- Importing from `app.api.*`
- Direct database connections (`psycopg`, etc.)
- Custom logging configurations from API container

✅ **ALLOWED**:
- Importing from `app.integrations.telegram.*` (own modules)
- HTTP requests to the API container (for configuration, queries, etc.)

### Why This Matters

- **Separation of Concerns**: Bot and API can be scaled independently
- **Deployment Flexibility**: Bot can run on a separate server/container
- **Security**: Bot has no direct access to sensitive backend resources
- **Maintainability**: Changes to API internals don't break the bot

### Configuration

The bot fetches all configuration dynamically from the API:
- **Bot phrases**: Retrieved from `GET /api/v1/config/bot-phrases` on startup
- **Environment variables**: Read from `.env` file

**No file-system access to API container's config files is required.**

### Running

```bash
# In Docker
docker-compose up telegram_bot

# Locally (for development)
python -m app.integrations.telegram.main
```

### Environment Variables

- `TELEGRAM_BOT_TOKEN`: Telegram bot token from BotFather
- `API_URL`: URL of the RAG API (e.g., `http://api:8000`)
- `REDIS_URL`: Redis connection string (e.g., `redis://redis:6379`)
