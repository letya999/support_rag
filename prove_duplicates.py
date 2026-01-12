import asyncio
import sys
import os

sys.path.append(os.getcwd())
from app.storage.connection import get_db_connection

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def show_dupes():
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            print("\n🔍 --- ОТЧЕТ О ДУБЛИКАТАХ В БД ---")
            
            # 1. Общая статистика
            await cur.execute("SELECT count(*) FROM documents")
            total = (await cur.fetchone())[0]
            await cur.execute("SELECT count(DISTINCT content) FROM documents")
            distinct = (await cur.fetchone())[0]
            
            print(f"Всего строк в таблице documents: {total}")
            print(f"Уникальных текстов: {distinct}")
            print(f"Количество лишних дублей: {total - distinct}")
            print("=" * 50)
            
            # 2. Список конкретных дубликатов
            query = """
                SELECT content, count(*), array_agg(id) 
                FROM documents 
                GROUP BY content 
                HAVING count(*) > 1
                ORDER BY count(*) DESC
            """
            await cur.execute(query)
            rows = await cur.fetchall()
            
            if not rows:
                print("Дубликатов не найдено.")
            
            for i, (content, count, ids) in enumerate(rows, 1):
                short_content = content.replace('\n', ' ')[:100]
                print(f"№{i}. Копий: {count} | IDs записей: {ids}")
                print(f"Текст: \"{short_content}...\"")
                print("-" * 50)

if __name__ == "__main__":
    asyncio.run(show_dupes())
