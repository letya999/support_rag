# Telegram Bot - Isolated Microservice

## Архитектура

Telegram бот работает как **stateless микросервис**, полностью изолированный от основного RAG API. Он не имеет прямого доступа к базе данных или Redis, а взаимодействует с API только через HTTP.

### Принципы изоляции

1. **Без зависимостей от ядра API**: Бот не импортирует модули из `app.services` или `app.storage`
2. **Без доступа к БД**: Вся работа с историей и сессиями делегируется backend API
3. **Без Redis**: Бот не управляет состоянием локально
4. **HTTP-only коммуникация**: Все взаимодействие с API через REST

## Компоненты

### 1. `bot.py` - Основной обработчик

**Stateless-архитектура:**
- Не хранит историю сообщений локально
- Генерирует стабильный `session_id` на основе `user_id`: `tg_sess_{user_id}`
- Передает пустой `conversation_history=[]` в API
- Доверяет backend'у загрузку истории через `SessionStarterNode`

**Команды:**
- `/start` - Приветствие
- `/help` - Справка

### 2. `pipeline_client.py` - HTTP клиент для RAG API

Отправляет запросы на `/api/v1/chat/completions` с:
- `question` - вопрос пользователя
- `conversation_history` - пустой массив (backend сам загрузит из БД)
- `user_id` - Telegram user ID
- `session_id` - стабильный идентификатор сессии
- `user_metadata` - метаданные пользователя (username, language, etc.)

### 3. `models.py` - Pydantic модели

Модели для контрактов с API:
- `RAGRequest` - запрос к пайплайну
- `RAGResponse` - ответ от пайплайна
- `MessageRole` - роль сообщения (user/assistant)

### 4. `main.py` - Entry point

Инициализирует:
- `RAGPipelineClient` - HTTP клиент
- `SupportRAGBot` - Telegram бот
- Загружает фразы бота из API endpoint `/api/v1/config/bot-phrases`

## Зависимости (`requirements.bot.txt`)

```txt
python-telegram-bot>=20.0
aiohttp>=3.9.0
pydantic>=2.0.0
```

**Удалены:**
- `redis` - больше не нужен
- `python-dotenv` - не требуется (env переменные загружаются Docker)
- `pydantic-settings` - была причиной конфликта
- `PyYAML` - конфигурация теперь загружается из API

## Переменные окружения

```bash
TELEGRAM_BOT_TOKEN=your_bot_token  # Обязательно
API_URL=http://api:8000            # URL основного RAG API
```

## Как работает история диалогов

1. **Пользователь отправляет сообщение** в Telegram
2. **Бот** получает сообщение и формирует `session_id = f"tg_sess_{user_id}"`
3. **Бот отправляет** в API:
   ```json
   {
     "question": "...",
     "conversation_history": [],  // Пустой!
     "user_id": "123456",
     "session_id": "tg_sess_123456",
     "user_metadata": {...}
   }
   ```
4. **API запускает пайплайн**:
   - `SessionStarterNode` видит `session_id`
   - Загружает историю из PostgreSQL через `PersistenceManager.get_session_messages()`
   - Перезаписывает `conversation_history` в State
5. **Пайплайн обрабатывает** запрос с полной историей
6. **`ArchiveSessionNode`** сохраняет новое сообщение в БД
7. **Бот получает ответ** и отправляет пользователю

## Запуск

### Docker Compose (продакшн)

```bash
docker-compose up -d telegram-bot
```

### Локальная разработка

```bash
cd app/integrations/telegram
export TELEGRAM_BOT_TOKEN="your_token"
export API_URL="http://localhost:8000"
python -m app.integrations.telegram.main
```

## Архитектурные решения

### Почему без Redis?

**Проблема:** Дублирование ответственности. И бот, и API управляют историей.

**Решение:** Single Source of Truth - PostgreSQL в основном API.

**Преимущества:**
- ✅ Бот перезапускается без потери истории
- ✅ История доступна из веб-интерфейса и других каналов
- ✅ Нет рассинхронизации между Redis и Postgres
- ✅ Упрощенная архитектура бота

### Почему стабильный session_id?

**Альтернатива:** `session_id = f"{user_id}_{timestamp}"`

**Проблема:** При перезапуске бота создается новая сессия, история теряется.

**Решение:** `session_id = f"tg_sess_{user_id}"` - один пользователь = одна сессия.

### Почему conversation_history пустой?

**Контракт API:** Поле `conversation_history` опциональное. Если не передано или пустое, `SessionStarterNode` загрузит из БД.

**Преимущество:** Бот не тратит ресурсы на кэширование и передачу истории.

## Мониторинг

Логи бота включают:
- Идентификатор пользователя
- Первые 50 символов запроса
- ID сессии
- Статус ответа от API

Пример:
```
2026-01-14 09:55:34 - User 123456: How do I return an item?...
2026-01-14 09:55:34 - Querying RAG pipeline for user 123456 (session tg_sess_123456)
2026-01-14 09:55:35 - Response sent to user 123456
```

## Устранение неполадок

### "ModuleNotFoundError: No module named 'pydantic_settings'"

**Решение:** Зависимость удалена из `requirements.bot.txt`. Пересоберите образ:
```bash
docker-compose build telegram-bot
```

### "Failed to connect to RAG pipeline"

**Проверьте:**
1. API запущен и доступен по `API_URL`
2. Бот может достучаться до API (network в docker-compose)
3. Endpoint `/api/v1/chat/completions` отвечает

### История не сохраняется

**Проверьте:**
1. `session_id` стабильный (не меняется между запросами)
2. `ArchiveSessionNode` включен в пайплайне
3. PostgreSQL доступна и таблица `messages` существует

## Roadmap

- [ ] Добавить команду `/history` через API endpoint
- [ ] Webhook режим вместо polling
- [ ] Поддержка inline buttons для escalation
- [ ] Метрики (количество запросов, latency)
