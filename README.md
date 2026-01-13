# Support RAG System

> A powerful, modular RAG (Retrieval-Augmented Generation) system with semantic caching, hybrid search, and multi-hop reasoning.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

## 📋 Table of Contents

- [What is Support RAG?](#what-is-support-rag)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Documentation](#documentation)
- [Project Structure](#project-structure)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## 💡 What is Support RAG?

Support RAG is an advanced open-source RAG system designed for high-performance automated customer support and knowledge retrieval. It goes beyond simple semantic search by integrating semantic caching, hybrid search (lexical + vector), and a modular pipeline architecture with 29+ specialized nodes.

It is built to handle complex queries, manage conversation state, and provide accurate, context-aware responses with citations.

## ✨ Key Features

- **🚀 Modular Pipeline Architecture**: 29+ specialized nodes for flexible query processing
- **🧠 Semantic Caching**: Caches responses based on semantic similarity to reduce latency and costs
- **🔍 Hybrid Search**: Combines Dense Retrieval (Vector) and Sparse Retrieval (BM25/Lexical) for best accuracy
- **🔄 Multi-hop Reasoning**: Breaks down complex user queries into sub-questions
- **🛡️ Guardrails**: Input and output validation to ensure safety and quality
- **💬 Conversation Management**: Handles context and history for natural multi-turn dialogue
- **🔌 Webhooks & API**: Real-time event notifications and comprehensive REST API

## 🚀 Quick Start

Get up and running in minutes using Docker Compose.

1.  **Clone the repository**
    ```bash
    git clone https://github.com/letya999/support_rag.git
    cd support_rag
    ```

2.  **Configure Environment**
    ```bash
    cp .env.example .env
    # Edit .env with your API keys (OpenAI, etc.)
    ```

3.  **Start Services**
    ```bash
    docker-compose up -d
    ```

4.  **Ingest Data** (Optional initial setup)
    ```bash
    docker-compose exec app python scripts/ingest.py --file datasets/qa_data.json
    ```

5.  **Test API**
    ```bash
    curl -X POST http://localhost:8000/api/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d '{"messages": [{"role": "user", "content": "How do I return an item?"}]}'
    ```

## 🛠️ Installation

### Prerequisites
- Docker & Docker Compose
- Python 3.9+ (for local development)
- PostgreSQL
- Redis

### Local Development Setup

For those who want to contribute or run without Docker:

1.  Create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Run migrations and start the server:
    ```bash
    python scripts/run_migrations.py
    uvicorn app.main:app --reload
    ```

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed instructions.

## 📖 Usage

### REST API

The system provides a comprehensive API for chat completions and RAG queries.

**Example Request:**
```json
POST /api/v1/chat/completions
{
  "messages": [
    {"role": "user", "content": "Tell me about shipping policies."}
  ],
  "temperature": 0.7
}
```

### Telegram Bot

A Telegram bot integration is included. Configure your `TELEGRAM_BOT_TOKEN` in `.env` and start the bot container.

## 📚 Documentation

- [**Development Guide**](DEVELOPMENT.md): Setup, testing, and contribution guide.
- [**Architecture**](docs/ARCHITECTURE.md): Deep dive into the system design, nodes, and data flow.
- [**API Documentation**](docs/API.md): Detailed API reference.
- [**Database Schema**](docs/DATABASE_SCHEMA.md): Database structure and tables.

## 📂 Project Structure

```
support_rag/
├── app/                 # Main application code
│   ├── api/             # API endpoints
│   ├── core/            # Config and core logic
│   ├── nodes/           # Pipeline nodes (processing logic)
│   └── services/        # Business logic services
├── datasets/            # Example datasets
├── docs/                # Documentation
├── scripts/             # Utility and setup scripts
├── tests/               # Test suite
├── docker-compose.yml   # Docker services config
└── requirements.txt     # Python dependencies
```

## ❓ FAQ

**Q: Can I use my own LLM?**
A: Yes, the system handles OpenAI-compatible APIs. Configure the base URL and API key in `.env`.

**Q: How does caching work?**
A: We use Redis for semantic caching. Similar queries are matched using vector embeddings to return cached responses instantly.

## 🤝 Contributing

We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to submit pull requests, report issues, and setup your development environment.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

If you have any questions or run into issues, please open an issue on GitHub.
