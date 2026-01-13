# План исправления проблем производительности

**Дата анализа:** 2026-01-13
**Всего найдено проблем:** 19

---

## 🔴 Критический приоритет (P0) - Исправить немедленно

### 1. Отсутствие пула соединений Redis

**Файлы:**
- `app/services/staging.py:20-22` (9+ использований в методах на строках 84, 95, 106, 133, 162, 185, 204, 271, 323)
- `app/integrations/telegram/storage.py:40`

**Проблема:**
```python
async def _get_redis(self):
    return await aioredis.from_url(self.redis_url, ...)  # Новое соединение каждый раз!
```
Создается и закрывается новое соединение при каждой операции.

**Влияние:**
- 9+ циклов создания/закрытия соединения на операцию с черновиком
- Огромные накладные расходы на установку TCP соединения
- Потенциальное исчерпание file descriptors

**План исправления:**
```python
# Реализовать singleton паттерн для пула соединений
class RedisPool:
    _instance = None
    _pool = None

    @classmethod
    async def get_pool(cls):
        if cls._pool is None:
            cls._pool = await aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10
            )
        return cls._pool
```

**Оценка улучшения:** 80-90% снижение времени на операции с Redis

---

### 2. N+1 паттерн в обнаружении дубликатов

**Файл:** `app/services/qa_validators/duplicate_detector.py:29-60`

**Проблема:**
```python
# Метод find_duplicates - строки 29-34
for i in range(len(pairs)):           # O(n)
    for j in range(i + 1, len(pairs)):  # O(n)
        if cls._are_duplicate(pairs[i], pairs[j]):  # O(m)

# Метод remove_duplicates - строки 54-60
for pair in pairs:
    for seen_q, idx in seen_questions.items():  # O(n²)
        if cls._are_questions_similar(q_normalized, seen_q):  # difflib.SequenceMatcher - дорого
```

**Влияние:**
- Для 1000 пар: ~500,000 сравнений
- Каждое сравнение использует `difflib.SequenceMatcher()` - O(m*n)
- Экспоненциальный рост времени выполнения

**План исправления:**

**Вариант 1: Хэш-подход**
```python
from typing import Dict, Set

def find_duplicates_optimized(pairs: List[QAPair]) -> List[List[int]]:
    # Создать нормализованные хэши вопросов
    question_hashes: Dict[str, List[int]] = {}
    for i, pair in enumerate(pairs):
        normalized = normalize_text(pair.question)
        hash_key = " ".join(sorted(normalized.split()[:10]))  # Первые 10 слов
        question_hashes.setdefault(hash_key, []).append(i)

    # Группы с одинаковыми хэшами - кандидаты на дубликаты
    duplicates = []
    for indices in question_hashes.values():
        if len(indices) > 1:
            # Точная проверка только внутри группы
            duplicates.extend(check_group_similarity(pairs, indices))

    return duplicates
```

**Вариант 2: MinHash / LSH для приблизительного поиска**
```python
from datasketch import MinHash, MinHashLSH

def find_duplicates_minhash(pairs: List[QAPair], threshold=0.8):
    lsh = MinHashLSH(threshold=threshold, num_perm=128)
    minhashes = {}

    for i, pair in enumerate(pairs):
        m = MinHash(num_perm=128)
        for word in normalize_text(pair.question).split():
            m.update(word.encode('utf8'))
        lsh.insert(i, m)
        minhashes[i] = m

    duplicates = []
    processed = set()

    for i in range(len(pairs)):
        if i in processed:
            continue
        result = lsh.query(minhashes[i])
        if len(result) > 1:
            duplicates.append(list(result))
            processed.update(result)

    return duplicates
```

**Оценка улучшения:**
- Вариант 1: O(n²) → O(n*k) где k << n (размер группы)
- Вариант 2: O(n²) → O(n log n)
- Ожидаемое ускорение: 100-1000x для больших датасетов

---

## ⚠️ Высокий приоритет (P1) - Исправить в течение недели

### 3. Линейный поиск в списке активных узлов

**Файл:** `app/pipeline/graph_builder.py:81-251`

**Проблема:**
```python
# 11+ проверок вида:
input_guardrails_enabled = "input_guardrails" in active_node_names  # O(n) каждый раз
if "session_starter" in active_node_names:  # O(n)
if "clarification_questions" in active_node_names:  # O(n)
# ... и так далее
```

**Влияние:**
- ~20 узлов в конфигурации × 11 проверок = 220 итераций по списку
- Выполняется при каждом построении графа

**План исправления:**
```python
# Строка 55-58: при создании active_node_names
active_node_names = [n["name"] for n in pipeline_config if n.get("enabled", False)]
active_node_names_set = set(active_node_names)  # ДОБАВИТЬ ЭТУ СТРОКУ

# Затем во всех проверках заменить:
# БЫЛО: "input_guardrails" in active_node_names
# СТАЛО: "input_guardrails" in active_node_names_set

# Строки для замены: 81, 84, 109, 118, 124, 164, 175, 189-191, 203, 207, 217, 240, 251
```

**Оценка улучшения:** O(n) → O(1), ускорение ~20x на каждую проверку

---

### 4. Дорогая сериализация JSON для логирования

**Файлы:**
- `app/observability/input_state_filter.py:118-119`
- `app/observability/output_state_validator.py:135`
- `app/services/staging.py:305`

**Проблема:**
```python
# Сериализация больших объектов только для подсчета размера
original_size = len(json.dumps({k: state[k] for k in all_keys}, default=str))
filtered_size = len(json.dumps({k: state[k] for k in kept_keys}, default=str))
```

**Влияние:**
- Двойная сериализация больших state объектов
- Выполняется на каждом запросе
- CPU и память расходуются на статистику

**План исправления:**

**Вариант 1: Приблизительная оценка размера**
```python
def estimate_size(obj: Any, visited: set = None) -> int:
    """Быстрая оценка размера объекта без сериализации"""
    if visited is None:
        visited = set()

    obj_id = id(obj)
    if obj_id in visited:
        return 0
    visited.add(obj_id)

    if isinstance(obj, str):
        return len(obj)
    elif isinstance(obj, (int, float, bool, type(None))):
        return 8
    elif isinstance(obj, (list, tuple)):
        return sum(estimate_size(item, visited) for item in obj)
    elif isinstance(obj, dict):
        return sum(estimate_size(k, visited) + estimate_size(v, visited)
                   for k, v in obj.items())
    else:
        return len(str(obj))

# Использование:
original_size = estimate_size({k: state[k] for k in all_keys})
filtered_size = estimate_size({k: state[k] for k in kept_keys})
```

**Вариант 2: Условное логирование**
```python
# Считать размер только если уровень логирования DEBUG
if logger.isEnabledFor(logging.DEBUG):
    original_size = len(json.dumps({k: state[k] for k in all_keys}, default=str))
    filtered_size = len(json.dumps({k: state[k] for k in kept_keys}, default=str))
    logger.debug(f"Size reduction: {original_size} → {filtered_size}")
```

**Оценка улучшения:** 90% снижение CPU на логирование

---

### 5. Двойной round-trip в кэш при каждом попадании

**Файл:** `app/services/cache/manager.py:85-92`

**Проблема:**
```python
if data:
    entry = CacheEntry.model_validate_json(data)
    entry.hit_count += 1
    await self.set(query_normalized, entry)  # Дополнительная операция SET!
```

**Влияние:**
- Каждое попадание в кэш = 2 операции Redis (GET + SET)
- Удвоение latency на кэшированные запросы

**План исправления:**

**Вариант 1: Redis HINCRBY**
```python
async def get(self, query: str) -> Optional[CacheEntry]:
    query_normalized = self._normalize_query(query)

    if self.redis.is_available():
        key = f"{self.cache_prefix}{query_normalized}"

        # Получить данные
        data = await self.redis.get(key)
        if data:
            entry = CacheEntry.model_validate_json(data)

            # Инкремент счетчика без повторной сериализации
            await self.redis.hincrby(f"{key}:stats", "hit_count", 1)

            # Обновить TTL
            await self.redis.expire(key, self.cache_ttl_seconds)

            return entry
```

**Вариант 2: Асинхронное обновление статистики**
```python
# Не блокировать GET ради обновления статистики
async def get(self, query: str) -> Optional[CacheEntry]:
    # ... получение данных ...
    if data:
        entry = CacheEntry.model_validate_json(data)

        # Обновить статистику асинхронно (fire-and-forget)
        asyncio.create_task(self._update_hit_stats(query_normalized))

        return entry

async def _update_hit_stats(self, query: str):
    """Фоновое обновление статистики"""
    try:
        await self.redis.hincrby(f"{self.cache_prefix}{query}:stats", "hit_count", 1)
    except Exception as e:
        logger.debug(f"Failed to update cache stats: {e}")
```

**Оценка улучшения:** 50% снижение latency на кэшированные запросы

---

### 6. Линейный поиск метаданных в результатах

**Файл:** `app/nodes/retrieval/search.py:93`

**Проблема:**
```python
best_doc_metadata = next(
    (r.metadata for r in unique_results if r.content == best_doc_content), {}
)
```

**Влияние:**
- O(n) поиск при каждом извлечении
- Сравнение строк (content) может быть дорогим

**План исправления:**
```python
# Создать словарь для O(1) lookup
content_to_metadata = {r.content: r.metadata for r in unique_results}
best_doc_metadata = content_to_metadata.get(best_doc_content, {})

# Или еще лучше - хранить вместе:
content_metadata_pairs = [(r.content, r.metadata) for r in unique_results]
best_doc_content, best_doc_metadata = content_metadata_pairs[0]
```

**Оценка улучшения:** O(n) → O(1)

---

## 📊 Средний приоритет (P2) - Исправить в течение месяца

### 7. Неэффективные вычисления среднего значения

**Файлы:**
- `app/services/cache/stats.py:138, 142`
- `app/services/metadata_generation/embedding_classifier.py:167, 172`

**Проблема:**
```python
avg_cached_time = sum(self.cached_response_times) / len(self.cached_response_times)
avg_full_time = sum(self.full_response_times) / len(self.full_response_times)
```

**План исправления:**
```python
# Вариант 1: statistics.mean()
from statistics import mean, StatisticsError

try:
    avg_cached_time = mean(self.cached_response_times)
    avg_full_time = mean(self.full_response_times)
except StatisticsError:
    avg_cached_time = avg_full_time = 0

# Вариант 2: numpy (если уже используется)
import numpy as np
avg_cached_time = np.mean(self.cached_response_times)
avg_full_time = np.mean(self.full_response_times)

# Вариант 3: инкрементальное вычисление среднего
# При добавлении каждого значения:
self.cached_sum += response_time
self.cached_count += 1
# При получении среднего:
avg_cached_time = self.cached_sum / self.cached_count if self.cached_count > 0 else 0
```

**Оценка улучшения:** Минимальное, но чище код

---

### 8. Блокирующий DNS lookup в async коде

**Файл:** `app/utils/url_security.py:103`

**Проблема:**
```python
addr_info = socket.getaddrinfo(hostname, None)  # Блокирует event loop!
```

**План исправления:**
```python
import asyncio

# Вариант 1: asyncio.get_event_loop().getaddrinfo()
async def _resolve_hostname_async(hostname: str) -> List[str]:
    loop = asyncio.get_event_loop()
    try:
        addr_info = await loop.getaddrinfo(hostname, None)
        return [addr[4][0] for addr in addr_info]
    except Exception as e:
        logger.warning(f"DNS resolution failed: {e}")
        return []

# Вариант 2: aiodns (нужна установка)
import aiodns
resolver = aiodns.DNSResolver()

async def _resolve_hostname_async(hostname: str) -> List[str]:
    try:
        result = await resolver.gethostbyname(hostname, socket.AF_INET)
        return result.addresses
    except aiodns.error.DNSError as e:
        logger.warning(f"DNS resolution failed: {e}")
        return []
```

**Оценка улучшения:** Не блокирует event loop

---

### 9. FIFO кэш вместо LRU

**Файл:** `app/nodes/classification/classifier.py:11-34`

**Проблема:**
```python
self._cache = {}
self._cache_size = 1000

def _add_to_cache(self, text: str, output: ClassificationOutput):
    if len(self._cache) >= self._cache_size:
        self._cache.pop(next(iter(self._cache)))  # FIFO вместо LRU
```

**План исправления:**
```python
from functools import lru_cache
from typing import Tuple

# Вариант 1: functools.lru_cache
@lru_cache(maxsize=1000)
def _classify_cached(self, text: str) -> Tuple:
    """Обертка для кэширования (tuple для hashable)"""
    result = self._classify_internal(text)
    return (result.category, result.confidence, tuple(result.keywords))

# Вариант 2: collections.OrderedDict (manual LRU)
from collections import OrderedDict

self._cache = OrderedDict()

def _add_to_cache(self, text: str, output: ClassificationOutput):
    if text in self._cache:
        self._cache.move_to_end(text)  # Обновить позицию
    else:
        if len(self._cache) >= self._cache_size:
            self._cache.popitem(last=False)  # Удалить самый старый
        self._cache[text] = output

# Вариант 3: cachetools.LRUCache
from cachetools import LRUCache
self._cache = LRUCache(maxsize=1000)
```

**Оценка улучшения:** Лучший hit rate, меньше промахов кэша

---

### 10. O(n×m) проверка точки в прямоугольнике

**Файл:** `app/services/document_loaders/pdf_loader.py:89-92`

**Проблема:**
```python
for word in words:  # N слов
    for (tx0, ttop, tx1, tbottom) in table_rects:  # M таблиц
        if tx0 <= cx <= tx1 and ttop <= cy <= tbottom:
```

**План исправления:**
```python
# Вариант 1: R-tree spatial index
from rtree import index

def not_inside_tables_optimized(words, table_rects):
    # Построить R-tree для таблиц
    idx = index.Index()
    for i, (tx0, ttop, tx1, tbottom) in enumerate(table_rects):
        idx.insert(i, (tx0, ttop, tx1, tbottom))

    # Фильтровать слова
    result = []
    for word in words:
        cx, cy = word_center(word)
        # Быстрый поиск пересечений - O(log m)
        if not list(idx.intersection((cx, cy, cx, cy))):
            result.append(word)

    return result

# Вариант 2: Предварительная сортировка (если R-tree недоступен)
def not_inside_tables_sorted(words, table_rects):
    if not table_rects:
        return words

    # Сортировать таблицы по X
    sorted_tables = sorted(table_rects, key=lambda t: t[0])

    result = []
    for word in words:
        cx, cy = word_center(word)

        # Бинарный поиск потенциальных таблиц
        inside = False
        for tx0, ttop, tx1, tbottom in sorted_tables:
            if cx < tx0:  # Все следующие таблицы тоже справа
                break
            if tx0 <= cx <= tx1 and ttop <= cy <= tbottom:
                inside = True
                break

        if not inside:
            result.append(word)

    return result
```

**Оценка улучшения:** O(n×m) → O(n log m)

---

### 11. Неэффективные преобразования list↔set

**Файлы:**
- `app/nodes/aggregation/lightweight.py:33, 100, 130`
- `app/nodes/query_expansion/expander.py:35`

**Проблема:**
```python
return {k: list(set(v)) for k, v in entities.items() if v}  # Теряется порядок
extras = list(set(extras))
all_queries = list(set([question] + [q.strip() for q in expanded_queries if q.strip()]))
```

**План исправления:**
```python
# Вариант 1: dict.fromkeys() для сохранения порядка (Python 3.7+)
return {k: list(dict.fromkeys(v)) for k, v in entities.items() if v}
extras = list(dict.fromkeys(extras))

# Вариант 2: Если порядок не важен - оставить set
return {k: list(set(v)) for k, v in entities.items() if v}  # OK если порядок не важен

# Для query expansion - сохранить оригинальный запрос первым:
all_queries = [question] + [q.strip() for q in expanded_queries
                            if q.strip() and q.strip() != question]
# Или:
seen = {question}
all_queries = [question]
for q in expanded_queries:
    q = q.strip()
    if q and q not in seen:
        all_queries.append(q)
        seen.add(q)
```

**Оценка улучшения:** Сохранение порядка, предсказуемость результатов

---

## 📝 Низкий приоритет (P3) - Технический долг

### 12. Накопление больших списков в SCAN циклах

**Файлы:**
- `app/services/cache/manager.py:123-128`
- `app/services/staging.py:277-281, 328-332, 336-340`

**Проблема:**
```python
while True:
    cursor, keys = await self.redis.scan(cursor, match=pattern)
    keys_to_delete.extend(new_keys)  # Растущий список
```

**План исправления:**
```python
# Обрабатывать батчами вместо накопления
cursor = 0
deleted_count = 0
while True:
    cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)

    if keys:
        # Обработать сразу вместо накопления
        deleted_count += await self._delete_batch(keys)

    if cursor == 0:
        break
```

---

### 13. Компиляция regex паттернов в цикле

**Файл:** `app/utils/url_security.py:152-159`

**Проблема:**
```python
for pattern in suspicious_patterns:
    if re.search(pattern, url):  # Компиляция на каждой итерации
```

**План исправления:**
```python
# На уровне модуля
SUSPICIOUS_PATTERNS_COMPILED = [
    re.compile(r"\.\.\/"),
    re.compile(r"file:\/\/"),
    # ... остальные паттерны
]

# В функции:
for pattern in SUSPICIOUS_PATTERNS_COMPILED:
    if pattern.search(url):
        return False
```

---

### 14. Конкатенация строк в цикле

**Файл:** `app/services/document_loaders/pdf_loader.py:144, 176`

**Проблема:**
```python
page_blocks[-1].content += " " + line_text  # O(n²)
```

**План исправления:**
```python
# Накопить в список, затем join
text_parts = []
for line in lines:
    text_parts.append(line_text)
final_text = " ".join(text_parts)
```

---

### 15. Использование range(len()) вместо enumerate

**Файлы:**
- `app/pipeline/graph_builder.py:170`
- `app/services/qa_validators/duplicate_detector.py:29-30`

**Проблема:**
```python
for i in range(len(pipeline_nodes) - 1):
    current_node = pipeline_nodes[i]
    next_node = pipeline_nodes[i+1]
```

**План исправления:**
```python
# Вариант 1: zip
for current_node, next_node in zip(pipeline_nodes, pipeline_nodes[1:]):
    # использовать current_node и next_node

# Вариант 2: enumerate (если нужен индекс)
for i, current_node in enumerate(pipeline_nodes[:-1]):
    next_node = pipeline_nodes[i+1]
```

---

### 16. Множественные итерации по одним данным

**Файл:** `app/nodes/retrieval/node.py:114-118`

**Проблема:**
```python
for results in all_results:
    for r in results:
        if r.content not in seen_contents:
            unique_results.append(r)

docs = [r.content for r in unique_results]  # Вторая итерация
scores = [r.score for r in unique_results]  # Третья итерация
```

**План исправления:**
```python
# Одна итерация с распаковкой
unique_results = []
seen_contents = set()

for results in all_results:
    for r in results:
        if r.content not in seen_contents:
            unique_results.append(r)
            seen_contents.add(r.content)

# Распаковать за один проход
docs, scores, metadatas = zip(*[(r.content, r.score, r.metadata)
                                 for r in unique_results]) if unique_results else ([], [], [])
```

---

### 17. Отсутствие pipeline для Redis операций

**Файл:** `app/services/staging.py:345-351`

**Проблема:**
```python
for i in range(0, len(keys_to_delete), batch_size):
    batch = keys_to_delete[i:i + batch_size]
    if batch:
        deleted_count += await redis.delete(*batch)  # Отдельный round-trip на батч
```

**План исправления:**
```python
# Использовать Redis pipeline
pipeline = redis.pipeline()

for i in range(0, len(keys_to_delete), batch_size):
    batch = keys_to_delete[i:i + batch_size]
    if batch:
        pipeline.delete(*batch)

# Один round-trip для всех операций
results = await pipeline.execute()
deleted_count = sum(results)
```

---

### 18. Последовательный парсинг JSON в цикле

**Файл:** `app/services/staging.py:302-312`

**Проблема:**
```python
for d_json in drafts_json:
    if d_json:
        d = json.loads(d_json)  # Последовательно
```

**План исправления:**
```python
# Если датасет большой - использовать executor pool
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def parse_drafts_parallel(drafts_json):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        tasks = [
            loop.run_in_executor(executor, json.loads, d_json)
            for d_json in drafts_json if d_json
        ]
        return await asyncio.gather(*tasks)

# Использование:
parsed_drafts = await parse_drafts_parallel(drafts_json)
```

---

### 19. Сложные вложенные list comprehensions

**Файл:** `app/services/document_loaders/pdf_loader.py:58`

**Проблема:**
```python
clean_table = [[(cell or "").strip() for cell in row] for row in table_data]
```

**План исправления:**
```python
# Для больших таблиц - использовать генератор или numpy
def clean_table_data(table_data):
    for row in table_data:
        yield [cell.strip() if cell else "" for cell in row]

clean_table = list(clean_table_data(table_data))

# Или с numpy (если таблицы большие):
import numpy as np
table_array = np.array(table_data, dtype=str)
clean_table = np.char.strip(np.where(table_array == None, '', table_array)).tolist()
```

---

## 📈 Сводная таблица приоритетов

| Приоритет | Проблема | Файл | Ожидаемое улучшение |
|-----------|----------|------|---------------------|
| P0 | Redis connection pool | staging.py, telegram/storage.py | 80-90% |
| P0 | N+1 в детекторе дубликатов | duplicate_detector.py | 100-1000x |
| P1 | Линейный поиск в списке | graph_builder.py | 20x |
| P1 | JSON serialization для логов | input_state_filter.py | 90% |
| P1 | Двойной cache round-trip | cache/manager.py | 50% |
| P1 | Линейный поиск метаданных | retrieval/search.py | n→1 |
| P2 | Блокирующий DNS | url_security.py | Не блокирует event loop |
| P2 | FIFO → LRU кэш | classifier.py | Лучший hit rate |
| P2 | O(n×m) точка в прямоугольнике | pdf_loader.py | log(m) |
| P2 | Вычисление среднего | stats.py | Минимальное |
| P2 | list↔set конверсии | aggregation/lightweight.py | Сохранение порядка |
| P3 | SCAN список аккумуляция | cache/manager.py | Память |
| P3 | Regex компиляция | url_security.py | CPU |
| P3 | Конкатенация строк | pdf_loader.py | CPU |
| P3 | range(len()) | graph_builder.py | Читаемость |
| P3 | Множественные итерации | retrieval/node.py | CPU |
| P3 | Redis без pipeline | staging.py | Latency |
| P3 | Последовательный JSON parse | staging.py | Параллелизм |
| P3 | Сложные comprehensions | pdf_loader.py | Читаемость |

---

## 🎯 Рекомендуемый порядок исправлений

1. **Неделя 1:** P0 проблемы (Redis pool + N+1)
2. **Неделя 2:** P1 проблемы (list lookups, JSON serialization, cache)
3. **Неделя 3:** P2 проблемы (DNS, LRU, O(n×m))
4. **Неделя 4:** P3 проблемы (технический долг)

---

## 📊 Ожидаемый эффект

После исправления всех P0 и P1 проблем:
- **Latency:** снижение на 60-80%
- **Throughput:** увеличение на 2-3x
- **CPU usage:** снижение на 40-50%
- **Memory usage:** снижение на 20-30%
- **Redis connections:** снижение с ~100/sec до ~1 постоянное соединение

---

**Примечание:** Все изменения должны быть покрыты тестами перед деплоем в production.
