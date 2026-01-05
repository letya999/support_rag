# План реализации автоматического генерирования метаданных для QA документов

## 1. Обзор задачи

**Цель**: Автоматически генерировать метаданные (категории, интенты, требование handoff) для неразмеченного `qa.json`, позволяя пользователю просмотреть, согласовать или отредактировать предложенные метаданные.

**Входные данные**: JSON файл формата:
```json
[
  {
    "question": "How do I reset my password?",
    "answer": "You can reset..."
  }
]
```

**Выходные данные**: JSON с добавленными метаданными:
```json
[
  {
    "question": "How do I reset my password?",
    "answer": "You can reset...",
    "metadata": {
      "category": "Account Access",
      "intent": "reset_password",
      "requires_handoff": false,
      "confidence": {
        "category_score": 0.95,
        "intent_score": 0.92
      }
    }
  }
]
```

---

## 2. Архитектурное решение

### 2.1 Основные компоненты

#### A. **QAMetadataGenerator** (новый сервис)
Основной сервис для генерирования метаданных.

**Местоположение**: `app/services/metadata_generation/generator.py`

**Ответственность**:
- Загрузка и парсинг JSON файлов с Q&A парами
- Классификация каждого вопроса (категория + интент)
- Определение требуемости handoff (на основе правил + LLM)
- Автогенерирование кластеров категорий и интентов из данных
- Возврат структурированного результата с предложенными метаданными

**Ключевые методы**:
```python
class QAMetadataGenerator:
    async def generate_metadata_batch(
        self,
        qa_pairs: List[Dict[str, str]],
        num_categories: int = 15,
        num_intents_per_category: int = 3,
        config: MetadataGenConfig = None
    ) -> MetadataGenerationResult:
        """
        Генерирует метаданные для всех Q&A пар.

        Returns:
            - proposed_categories: List[CategoryProposal]
            - proposed_intents: List[IntentProposal]
            - qa_with_metadata: List[QAPairWithMetadata]
            - clustering_summary: Dict
        """

    async def detect_handoff_requirement(
        self,
        question: str,
        answer: str,
        category: str,
        intent: str
    ) -> bool:
        """Определяет, требуется ли передача оператору"""

    async def validate_assignments(
        self,
        qa_pairs_with_metadata: List[QAPairWithMetadata]
    ) -> ValidationResult:
        """Валидирует согласованность категорий/интентов"""
```

#### B. **MetadataClusterizer** (новый модуль)
Кластеризация вопросов в категории и интенты.

**Местоположение**: `app/services/metadata_generation/clustering.py`

**Ответственность**:
- На основе embeddings вопросов выполняет K-means кластеризацию
- Генерирует человекочитаемые имена для кластеров (используя LLM)
- Создает иерархию: Category → Intent
- Возвращает автоматически сгенерированные список категорий и интентов

**Ключевые методы**:
```python
class MetadataClusterizer:
    async def cluster_questions(
        self,
        questions: List[str],
        num_categories: int = 15,
        num_intents_per_category: int = 3
    ) -> ClusteringResult:
        """K-means кластеризация + генерирование имен"""

    async def generate_cluster_names(
        self,
        clusters: Dict[int, List[str]],
        cluster_type: str = "category"  # или "intent"
    ) -> Dict[int, str]:
        """Использует LLM для генерирования названий кластеров"""
```

#### C. **HandoffDetector** (новый компонент)
Определяет необходимость handoff.

**Местоположение**: `app/services/metadata_generation/handoff_detector.py`

**Ответственность**:
- Правило-базированная детекция (keywords: "operator", "human", "contact support", etc.)
- LLM-based детекция для сложных случаев
- Confidence score для каждого решения

---

### 2.2 API эндпоинты

#### 1. **POST /documents/metadata-generation/analyze**
Анализ загруженного JSON и генерирование предложенных метаданных.

**Request**:
```json
{
  "file_name": "qa.json",
  "num_categories": 15,
  "num_intents_per_category": 3,
  "language": "en"
}
```

**Response**:
```json
{
  "status": "success",
  "analysis_id": "uuid",
  "proposed_structure": {
    "categories": [
      {
        "id": "cat_1",
        "name": "Account Access",
        "description": "Password reset, login issues, account recovery",
        "suggested_intents": [
          "reset_password",
          "account_recovery",
          "login_help"
        ]
      }
    ],
    "qa_pairs": [
      {
        "id": 0,
        "question": "How do I reset my password?",
        "answer": "You can reset...",
        "suggested_category": "Account Access",
        "suggested_intent": "reset_password",
        "suggested_requires_handoff": false,
        "confidence": {
          "category": 0.95,
          "intent": 0.92,
          "handoff": 0.98
        }
      }
    ],
    "statistics": {
      "total_pairs": 10,
      "total_categories": 8,
      "total_intents": 24,
      "confidence_distribution": {...}
    }
  }
}
```

#### 2. **POST /documents/metadata-generation/review**
Пользователь просматривает и редактирует предложенные метаданные.

**Request**:
```json
{
  "analysis_id": "uuid",
  "user_corrections": [
    {
      "qa_index": 0,
      "corrected_category": "Account Access",
      "corrected_intent": "reset_password",
      "corrected_requires_handoff": false,
      "note": "User confirmed this is correct"
    }
  ],
  "category_renames": [
    {
      "original_name": "Account Access",
      "new_name": "User Account Management"
    }
  ]
}
```

**Response**:
```json
{
  "status": "review_accepted",
  "validated": true,
  "conflicts": [],
  "ready_for_ingestion": true,
  "summary": {
    "total_corrections": 1,
    "category_changes": 1
  }
}
```

#### 3. **POST /documents/metadata-generation/confirm**
Финализация и сохранение метаданных в базу.

**Request**:
```json
{
  "analysis_id": "uuid",
  "action": "save_with_metadata"
}
```

**Response**:
```json
{
  "status": "success",
  "ingested_count": 10,
  "registry_updated": true,
  "message": "Successfully ingested 10 Q&A pairs with metadata. Registry refreshed."
}
```

#### 4. **GET /documents/metadata-generation/preview/:analysis_id**
Получить текущее состояние анализа.

---

### 2.3 Система хранения временных данных

**Местоположение**: `app/services/metadata_generation/storage.py`

Используем Redis для кэширования анализа:
```python
class AnalysisCache:
    async def save_analysis(self, analysis_id: str, analysis: MetadataGenerationResult, ttl: int = 3600)
    async def get_analysis(self, analysis_id: str) -> MetadataGenerationResult
    async def delete_analysis(self, analysis_id: str)
```

---

## 3. Детали реализации

### 3.1 Алгоритм генерирования категорий и интентов

**Шаг 1**: Получить embeddings всех вопросов
```python
embeddings = await get_embedding(question) for each question
```

**Шаг 2**: K-means кластеризация на N категорий
```python
# Используем scikit-learn
from sklearn.cluster import KMeans
kmeans = KMeans(n_clusters=num_categories, random_state=42, n_init=10)
category_labels = kmeans.fit_predict(embeddings)
```

**Шаг 3**: Для каждой категории — вложенная K-means на M интентов
```python
# Для каждой категории:
  category_questions = [q for q, label in zip(questions, category_labels) if label == cat_id]
  category_embeddings = embeddings[category_labels == cat_id]

  # K-means для интентов
  intent_kmeans = KMeans(n_clusters=num_intents_per_category, ...)
  intent_labels = intent_kmeans.fit_predict(category_embeddings)
```

**Шаг 4**: Генерирование названий кластеров через LLM
```python
# Для каждого кластера категорий:
top_questions = get_top_k_questions(cluster, k=3)
prompt = f"""
Based on these support questions:
{top_questions}

Generate a concise category name (1-2 words) that describes them.
"""
category_name = await llm.generate(prompt)
```

---

### 3.2 Детекция Handoff

**Правило-базированная детекция** (быстро):
```python
HANDOFF_KEYWORDS = [
    "operator", "human", "agent", "call", "phone",
    "customer service", "representative", "escalate",
    "support ticket", "contact support"
]

def detect_handoff_rule_based(question: str, answer: str) -> Tuple[bool, float]:
    score = 0.0
    if any(kw in question.lower() for kw in HANDOFF_KEYWORDS):
        score += 0.5
    if any(kw in answer.lower() for kw in HANDOFF_KEYWORDS):
        score += 0.3

    return score > 0.5, min(score, 1.0)
```

**LLM-based детекция** (для сложных случаев):
```python
if rule_score < 0.6:  # Неясные случаи
    llm_result = await llm_classifier.classify(question, answer)
    # Returns: {requires_handoff: bool, confidence: float}
```

---

### 3.3 Модели Pydantic

**Местоположение**: `app/services/metadata_generation/models.py`

```python
class MetadataGenConfig(BaseModel):
    num_categories: int = 15
    num_intents_per_category: int = 3
    language: str = "en"
    min_confidence_threshold: float = 0.6
    allow_ambiguous: bool = True

class QAPair(BaseModel):
    question: str
    answer: str

class QAPairWithMetadata(BaseModel):
    question: str
    answer: str
    metadata: Dict[str, Any] = {
        "category": str,
        "intent": str,
        "requires_handoff": bool,
        "confidence": {
            "category_score": float,
            "intent_score": float,
            "handoff_score": float
        }
    }

class CategoryProposal(BaseModel):
    id: str
    name: str
    description: str
    suggested_intents: List[str]
    question_count: int

class MetadataGenerationResult(BaseModel):
    analysis_id: str
    timestamp: datetime
    proposed_categories: List[CategoryProposal]
    qa_with_metadata: List[QAPairWithMetadata]
    statistics: Dict[str, Any]

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str]
    warnings: List[str]
```

---

## 4. Интеграция с существующим кодом

### 4.1 Использование существующих компонентов

1. **SemanticClassificationService** (app/nodes/easy_classification/semantic_classifier.py)
   - Используем для классификации отдельных вопросов
   - Предоставляет embeddings и scores

2. **IntentRegistryService** (app/nodes/_shared_config/intent_registry.py)
   - Вычитываем существующие категории/интенты
   - Обновляем после финализации генерирования

3. **DocumentIngestionService** (app/services/ingestion)
   - Используем для сохранения итоговых Q&A пар с метаданными

4. **get_embedding()** (app/integrations/embeddings.py)
   - Получение embeddings для K-means кластеризации

### 4.2 Изменения в существующих файлах

**1. app/api/routes.py** - Добавить новые эндпоинты (см. раздел 2.2)

**2. app/dataset/schema.py** - Расширить EvalItem:
```python
class QAPairWithMetadata(BaseModel):
    question: str
    answer: str
    metadata: Optional[Dict[str, Any]] = None
```

**3. app/settings.py** - Добавить конфиг:
```python
class Settings(BaseSettings):
    # Metadata generation
    METADATA_GEN_CACHE_TTL: int = 3600
    METADATA_GEN_DEFAULT_CATEGORIES: int = 15
    METADATA_GEN_DEFAULT_INTENTS: int = 3
```

---

## 5. Процесс использования

### Поток пользователя

```
1. Пользователь загружает qa.json (без метаданных)
   POST /documents/metadata-generation/analyze

2. Система анализирует и показывает:
   - Предложенные 15 категорий
   - Для каждой категории — 3 интента
   - Для каждого Q&A — suggested метаданные

3. Пользователь может:
   a) Согласиться со всеми предложениями
   b) Переименовать категории
   c) Переассайнить Q&A на другие категории/интенты
   d) Уточнить требование handoff

4. Пользователь отправляет коррекции:
   POST /documents/metadata-generation/review

5. Система валидирует и показывает конфликты (если есть)

6. Пользователь финализирует:
   POST /documents/metadata-generation/confirm

7. Система сохраняет:
   - Q&A пары с метаданными в БД
   - Обновляет intents_registry.yaml
   - Рефрешит SemanticClassificationService
```

---

## 6. Конфигурация (YAML)

**Новый файл**: `config/metadata_generation.yaml`

```yaml
metadata_generation:
  # Алгоритм
  clustering:
    algorithm: "kmeans"  # или "hierarchical", "dbscan"
    random_state: 42
    n_init: 10

  # Дефолтные параметры
  defaults:
    num_categories: 15
    num_intents_per_category: 3
    min_confidence_threshold: 0.6

  # Handoff детекция
  handoff_detection:
    use_rules: true
    use_llm: true
    llm_threshold: 0.6  # Использовать LLM если rule_score < 0.6

  # Кэш
  cache:
    backend: "redis"
    ttl_seconds: 3600

  # Обогащение описаний (аналогично CATEGORY_ENRICHMENT в refresh_intents.py)
  enrichment:
    auto_generate: true
    language: "en"
```

---

## 7. Примеры использования

### Пример 1: Генерирование метаданных

```bash
curl -X POST http://localhost:8000/documents/metadata-generation/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "qa.json",
    "num_categories": 15,
    "num_intents_per_category": 3,
    "language": "en"
  }'

# Response: analysis_id = "a1b2c3d4-..."
```

### Пример 2: Просмотр и редактирование

```bash
curl -X POST http://localhost:8000/documents/metadata-generation/review \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_id": "a1b2c3d4-...",
    "user_corrections": [
      {
        "qa_index": 0,
        "corrected_category": "Account Access",
        "corrected_intent": "password_reset",
        "corrected_requires_handoff": false
      }
    ],
    "category_renames": [
      {
        "original_name": "Misc",
        "new_name": "General Information"
      }
    ]
  }'
```

### Пример 3: Финализация

```bash
curl -X POST http://localhost:8000/documents/metadata-generation/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_id": "a1b2c3d4-...",
    "action": "save_with_metadata"
  }'
```

---

## 8. Тестирование

### Unit тесты
- `tests/services/metadata_generation/test_generator.py`
- `tests/services/metadata_generation/test_clustering.py`
- `tests/services/metadata_generation/test_handoff_detector.py`

### Integration тесты
- `tests/api/test_metadata_generation_endpoints.py`

### Пример тестовых данных
```python
# fixtures/qa_samples.py
SAMPLE_QA_PAIRS = [
    {"question": "How do I reset my password?", "answer": "..."},
    {"question": "Where is my order?", "answer": "..."},
    # ... 10 пар
]
```

---

## 9. Миграция данных

После реализации:

1. Существующие Q&A пары (в БД) получат автоматические метаданные через:
   ```bash
   python scripts/auto_metadata_migration.py
   ```

2. Обновить `intents_registry.yaml`:
   ```bash
   python scripts/refresh_intents.py
   ```

3. Рефрешить классификатор:
   ```
   POST /admin/refresh-intents
   ```

---

## 10. Альтернативные подходы (не выбраны)

### Вариант 1: Использовать только LLM для классификации
- ❌ Дорого (N запросов к API)
- ❌ Медленнее
- ✅ Потенциально более точно

### Вариант 2: Использовать готовые иерархические таксономии
- ❌ Не гибко для разных доменов
- ✅ Скорее

**Выбранный подход**: Комбинированный
- K-means кластеризация (быстро) + LLM для названий (точно)

---

## 11. Метрики и мониторинг

Через Langfuse:
- Время генерирования метаданных
- Распределение confidence scores
- Количество пользовательских коррекций
- Accuracy категоризации (после получения feedback)

---

## 12. Примечания по реализации

1. **Concurrency**: Все операции async (используем asyncio + executor для scikit-learn)
2. **Ошибки**: Graceful degradation (если embedding fails, используем fallback)
3. **Локализация**: Поддержать multilingual embeddings (multilingual-e5-base)
4. **Масштабируемость**: K-means может быть медленным для 100k+, рассмотреть mini-batch версию
5. **Тайм-ауты**: Установить разумные пределы на анализ (max 10 минут)

---

## 13. Зависимости

Дополнительно к существующим `requirements.txt`:
- scikit-learn >= 1.0 (уже есть)
- sentence-transformers >= 3.3.0 (уже есть для embeddings)

Никаких новых зависимостей!

