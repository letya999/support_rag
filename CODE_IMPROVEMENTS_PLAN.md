# Support RAG - План улучшений (Пересмотренный)

**На основе глубокого анализа кода после фидбэка**

---

## ОСНОВНЫЕ ВЫВОДЫ ПОСЛЕ АНАЛИЗА

### ✅ Что работает хорошо (пересмотрено)

1. **Input/Output Contracts + Filtering - РАБОТАЕТ ОТЛИЧНО**
   - ✅ BaseNode имеет полноценную систему валидации
   - ✅ InputStateFilter фильтрует входные данные перед execute()
   - ✅ OutputStateValidator валидирует/фильтрует выходные данные
   - ✅ 30+ нод определяют INPUT_CONTRACT и OUTPUT_CONTRACT
   - ❌ **ПРОБЛЕМА:** Фильтрация НЕ валидирует обязательные поля (required)

   ```python
   # app/nodes/base_node/base_node.py - missing validation for required fields
   # If a node says INPUT_CONTRACT["required"] = ["question"]
   # But state doesn't have "question" - это НЕ проверяется!
   ```

2. **Configuration System - ХОРОШО СПРОЕКТИРОВАНА**
   - ✅ Трехуровневая иерархия (global.yaml → node config.yaml → pipeline_config.yaml)
   - ✅ pipeline_config.yaml auto-генерируется из node configs
   - ✅ Parameters вынесены в YAML, не в код
   - ✅ 90% параметров конфигурируется
   - ❌ **ПРОБЛЕМА:** Hardcoded defaults как fallback'ы есть в нодах (по необходимости)

   ```python
   # app/nodes/easy_classification/node.py:46-50
   i_threshold = params.get("intent_confidence_threshold", 0.3)  # Fallback
   ```

   **ЭТО НОРМАЛЬНО** - fallback нужен если конфиг отсутствует. Но defaults должны быть документированы.

3. **State Bloat НЕ ПРОБЛЕМА**
   - ✅ Есть система фильтрации - ноды получают только нужные им поля
   - ✅ Нет необходимости разделять State на StateCore + RetrievalContext
   - ✅ Все поля нужны для разных ноды в разных контекстах
   - ❌ **РЕАЛЬНАЯ ПРОБЛЕМА:** Legacy fields на самом деле АКТИВНО ИСПОЛЬЗУЮТСЯ

4. **Service Instantiation - НАМЕРЕННЫЙ ПАТТЕРН**
   - ✅ Сервисы создаются в execute() для **node independence**
   - ✅ Ноды не зависят от DI контейнера
   - ✅ Это позволяет тестировать ноды независимо
   - ⚠️ **МОЖЕТ БЫТЬ ОПТИМИЗИРОВАНО:** Но нужно сохранить независимость

---

## ПЕРЕРАБОТАННЫЙ ПЛАН УЛУЧШЕНИЙ

### 🔴 IMMEDIATE (4-6 часов работы)

#### 1. Fix Bare `except:` Clauses (1 час) ✓ CLEAR FIX

**Проблема:**
```python
# 6 файлов с bare except
try:
    payload = await request.json()
except:  # ❌ Ловит KeyboardInterrupt, SystemExit!
    raise HTTPException(status_code=400)
```

**Файлы для исправления:**
- `app/api/v1/webhooks.py` - line 104
- `app/services/discovery_service.py` - ?
- `app/services/embeddings.py` - ?
- + 3 еще файла

**Решение:**
```python
# ✅ Специфичные exceptions
except json.JSONDecodeError as e:
    logger.warning(f"Invalid JSON: {e}")
    raise HTTPException(status_code=400, detail="Invalid JSON")
except asyncio.CancelledError:
    raise  # Всегда пробрасываем
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(status_code=500)
```

**Impact:** ⭐⭐⭐⭐⭐ - CRITICAL для production reliability

---

#### 2. API Error Response Standardization (2 часа) ✓ CLEAR FIX

**Проблема:**
```python
# Разные форматы ошибок в разных endpoints
return {"message": "Validation Error", "details": str(exc)}  # format 1
raise HTTPException(status_code=500, detail=str(e))          # format 2
return {"error": "Some error"}                                # format 3
```

**Решение: Единый ErrorResponse + Envelope**

Создать `app/api/models/error_models.py`:
```python
from enum import Enum

class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMITED = "RATE_LIMITED"

@dataclass
class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str

@dataclass
class ErrorResponse(BaseModel):
    code: ErrorCode
    message: str
    details: List[ErrorDetail] = []

class Envelope[T](BaseModel):
    data: Optional[T] = None
    error: Optional[ErrorResponse] = None
    meta: MetaResponse

# Usage - все endpoints должны возвращать Envelope
@router.post("/chat/completions")
async def create_completion(request: ChatCompletionRequest) -> Envelope[ChatCompletionResponse]:
    try:
        result = await pipeline.execute(request)
        return Envelope(data=result, meta=MetaResponse(...))
    except ValueError as e:
        return Envelope(
            error=ErrorResponse(
                code=ErrorCode.VALIDATION_ERROR,
                message=str(e)
            ),
            meta=MetaResponse(...)
        )
```

**Обновить все endpoints в:**
- `app/api/v1/chat.py`
- `app/api/v1/webhooks.py`
- `app/api/v1/ingestion.py`
- `app/api/v1/analysis.py`
- И остальные...

**Impact:** ⭐⭐⭐⭐ - Улучшает client-side error handling

---

#### 3. Fix BaseNode Required Input Validation (2 часа) ✓ CAREFUL FIX

**Проблема:**
```python
# Контракт говорит что question REQUIRED
INPUT_CONTRACT = {"required": ["question"], "optional": [...]}

# Но валидация НЕ проверяет что question есть!
input_to_processed = self._input_filter.apply(state)  # ❌ Просто фильтрует, не валидирует required
```

**Решение: Добавить валидацию required полей**

Обновить `app/observability/input_state_filter.py`:
```python
class InputStateFilter:
    def apply(self, state: Dict[str, Any]) -> Dict[str, Any]:
        contract = self.validator.get_input_contract()

        # ✅ ШАГ 1: Проверить что все required поля присутствуют
        missing_fields = []
        for required_field in contract.required:
            if required_field not in state:
                missing_fields.append(required_field)

        if missing_fields and self.strict_mode:
            raise ValueError(f"Missing required fields: {missing_fields}")
        elif missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")

        # ШАГ 2: Фильтровать только нужные поля
        allowed_fields = contract.all_fields
        filtered = {}
        for key, value in state.items():
            if key in allowed_fields:
                filtered[key] = value

        return filtered
```

**Добавить конфиг для strict mode:**
```yaml
# app/_shared_config/global.yaml
validation:
  strict_required_inputs: false  # true в development, false в production

# app/_shared_config/validation_config.py
@dataclass
class ValidationConfig:
    strict_required_inputs: bool = False  # Error on missing required vs Warning
```

**Impact:** ⭐⭐⭐ - Помогает отловить ошибки ранней

---

### 🟡 WEEK 1 (6-8 часов работы)

#### 4. Document Configuration Defaults (1.5 часа) ✓ DOCUMENTATION

**Проблема:**
Hardcoded defaults не документированы. Когда конфиг отсутствует, используются defaults из кода.

**Решение: Создать документ с default'ами**

Создать `docs/CONFIGURATION_DEFAULTS.md`:
```markdown
# Configuration Defaults

## Global Defaults (from global.yaml)

| Parameter | Default | Range | Meaning |
|-----------|---------|-------|---------|
| `timeout_ms` | 5000 | 1000-60000 | Node execution timeout in milliseconds |
| `retry_count` | 3 | 0-10 | Number of retries for failed operations |
| `confidence_threshold` | 0.3 | 0.0-1.0 | Minimum confidence to consider result valid |
| `session_ttl_hours` | 24 | 1-168 | Session lifetime in hours |
| `session_timeout_minutes` | 30 | 5-1440 | Inactivity timeout in minutes |
| `default_language` | "en" | "en", "ru", "de" | Default language for processing |

## Node Defaults

### easy_classification
- `intent_confidence_threshold`: 0.4 (0.0-1.0) - Minimum for intent match
- `category_confidence_threshold`: 0.4 (0.0-1.0) - Minimum for category match
- `skip_if_low_confidence`: true - Skip this node if below threshold
- `fallback_intent`: "unknown" - Intent if no match
- `fallback_category`: "General" - Category if no match

### dialog_analysis
- `negative_sentiment_threshold`: -0.3 (-1.0 to 1.0) - Sentiment cutoff
- `detect_repeated_questions`: true - Enable loop detection
- `topic_loop_similarity_threshold`: 0.9 (0.0-1.0) - Cosine similarity for loop
- `topic_loop_window_size`: 4 (2-10) - History window for loop detection
- `topic_loop_min_messages`: 3 (2-20) - Min messages to consider loop
...
```

**Где документировать?**
1. `docs/CONFIGURATION_DEFAULTS.md` - главный документ
2. Каждый node config.yaml - примеры параметров с пояснениями
3. `claude.md` - ссылка на документацию конфигурации

**Impact:** ⭐⭐⭐ - Улучшает onboarding и понимание параметров

---

#### 5. Add Output Contract Validation (1.5 часа) ✓ SAFE FIX

**Проблема:**
OUTPUT_CONTRACT может быть нарушен, но это только логируется (warning), не валидируется.

```python
class GenerationNode(BaseNode):
    OUTPUT_CONTRACT = {
        "guaranteed": ["answer"],
        "conditional": []
    }

    async def execute(self, state):
        return {
            "answer": "...",
            "extra_field_not_in_contract": "..."  # ❌ Не проверяется!
        }
```

**Решение: Добавить option для strict output validation**

В `app/observability/validation_config.py`:
```python
@dataclass
class ValidationConfig:
    # Existing
    filter_inputs: bool = True
    filter_outputs: bool = False  # ← DEFAULT: don't filter (maintain backward compat)
    log_violations: bool = True

    # NEW
    strict_output: bool = False  # Error if output has fields not in contract
```

В `app/observability/output_state_validator.py`:
```python
class OutputStateValidator:
    def apply(self, output: Dict[str, Any]) -> Dict[str, Any]:
        contract = self.validator.get_output_contract()

        if not contract.guaranteed and not contract.conditional:
            return output  # No contract defined

        # Check for guaranteed fields
        missing_guaranteed = [f for f in contract.guaranteed if f not in output]
        if missing_guaranteed:
            if self.config.strict_output:
                raise ValueError(f"Missing guaranteed fields: {missing_guaranteed}")
            else:
                logger.warning(f"Missing guaranteed fields: {missing_guaranteed}")

        # Check for unexpected fields
        allowed = set(contract.all_fields)
        unexpected = [f for f in output if f not in allowed]
        if unexpected:
            if self.config.strict_output:
                logger.warning(f"Unexpected output fields: {unexpected} (filtered out)")
                return {k: v for k, v in output.items() if k in allowed}
            else:
                logger.debug(f"Unexpected output fields: {unexpected} (passed through)")
                return output

        return output
```

**Использование:**
```python
# В development:
OBSERVABILITY_VALIDATION_STRICT_OUTPUT=true

# В production:
OBSERVABILITY_VALIDATION_STRICT_OUTPUT=false  # Maintain compatibility
```

**Impact:** ⭐⭐⭐ - Помогает разработчикам отловить ошибки контрактов

---

#### 6. Service Instantiation - Efficiency Analysis (2 часа) ⚠️ RESEARCH

**Проблема:**
Сервисы создаются в execute() на каждый вызов. Это намеренно для node independence, но может быть неэффективно.

**Анализ:**
```python
# Pattern 1: Created per request (node independence)
async def execute(self, state):
    service = ClassificationService()  # NEW each time
    return await service.classify(question)

# Pattern 2: Created in __init__ (caching)
def __init__(self):
    self.service = MetadataFilteringService()  # Cached

async def execute(self, state):
    return await self.service.filter(...)
```

**Вопрос: Какие сервисы дорогостоящие?**

Нужно измерить:
1. Какие сервисы дорого создавать? (load models, allocate memory)
2. Какие можно переиспользовать без side effects?
3. Какие нужно пересоздавать для thread safety?

**Решение: Шаблон с lazy initialization**

```python
class ClassificationNode(BaseNode):
    _service_instance: Optional[ClassificationService] = None
    _service_lock = asyncio.Lock()

    @classmethod
    async def get_service(cls) -> ClassificationService:
        """Get or create service singleton."""
        if cls._service_instance is None:
            async with cls._service_lock:
                if cls._service_instance is None:
                    cls._service_instance = ClassificationService()
        return cls._service_instance

    async def execute(self, state):
        service = await self.get_service()  # Reused after first creation
        return await service.classify(question)
```

**ВАЖНО:** Это должно быть опциональным! Нельзя менять сегодня.

**Impact:** ⭐⭐⭐ - Потенциальное улучшение performance (нужно измерить)

---

### 🟢 WEEK 2 (4-6 часов работы)

#### 7. Clean Up Legacy Fields (1 час) ✓ NOT NEEDED NOW

**На самом деле это НЕ legacy!**

```python
# Активно используется
matched_intent:     RoutingNode пишет → ArchiveSession читает
matched_category:   MetadataFiltering пишет → Retrieval читает
semantic_intent:    ClassificationNode пишет → Routing использует

# Только логируется, не используется
semantic_intent_confidence, semantic_category_confidence, semantic_time
```

**Решение:**
- ❌ НЕ удалять matched_intent, matched_category
- ⚠️ Пересмотреть semantic_*_confidence, semantic_time
- ✅ Если не используются - документировать как deprecated

---

#### 8. Comprehensive Testing Strategy (Ongoing) - SKIP FOR NOW

Как попросил пользователь.

---

#### 9. Documentation Improvements (2-3 часа)

Создать/улучшить:

1. **docs/NODE_CONTRACT_GUIDE.md**
   - Как определить INPUT_CONTRACT
   - Как определить OUTPUT_CONTRACT
   - Примеры from existing nodes
   - Best practices

2. **docs/CONFIGURATION_DEFAULTS.md**
   - Таблица всех параметров с defaults
   - Диапазоны допустимых значений
   - Примеры переопределения

3. **docs/API_ERROR_HANDLING.md**
   - Единый format ErrorResponse
   - ErrorCode enum и значения
   - Примеры для каждого error type

---

## ПЕРЕРАБОТАННАЯ МАТРИЦА ПРИОРИТИЗАЦИИ

| # | Задача | Часов | Серьезность | Статус | Неделя |
|----|---------|-------|-------------|--------|--------|
| 1️⃣ | Fix bare except: (6 файлов) | 1h | 🔴 HIGH | READY | IMMEDIATE |
| 2️⃣ | API Error Standardization | 2h | 🔴 HIGH | READY | IMMEDIATE |
| 3️⃣ | BaseNode Required Validation | 2h | 🟡 MEDIUM | READY | IMMEDIATE |
| 4️⃣ | Document Config Defaults | 1.5h | 🟢 LOW | READY | Week 1 |
| 5️⃣ | Output Contract Validation | 1.5h | 🟡 MEDIUM | READY | Week 1 |
| 6️⃣ | Service Instance Efficiency | 2h | 🟡 MEDIUM | RESEARCH | Week 1 |
| 7️⃣ | Documentation Improvements | 3h | 🟢 LOW | READY | Week 2 |
| 8️⃣ | Testing Coverage | 16h | 🟡 MEDIUM | SKIP | - |

---

## ИТОГОВЫЕ ВЫВОДЫ

### ✅ ЧТО ХОРОШО
- Input/Output контракты + фильтрация - отличная система
- Configuration system - хорошо структурирована
- Service instantiation паттерн - намеренный для independence
- State структура - не блокирует с фильтрацией

### ❌ ЧТО НУЖНО ИСПРАВИТЬ (PRIORITY)
1. Bare except clauses - security/reliability issue
2. API Error format inconsistency - developer experience
3. Required input validation - missing from contracts
4. Webhook security - skip на сейчас (как сказал)

### ⚠️ ЧТО МОЖНО УЛУЧШИТЬ (NICE TO HAVE)
- Service instance efficiency - нужно профилировать
- Output contract validation - опционально
- Documentation defaults - улучшит onboarding

### 🟢 НЕ НУЖНО МЕНЯТЬ
- State bloat - фильтрация работает, структура логична
- Legacy fields - активно используются, не legacy
- Tests - skip на сейчас
