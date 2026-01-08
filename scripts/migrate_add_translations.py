"""
Migration script: Add translations to existing messages in database.

This script translates all existing user messages to English and stores
the translation in the metadata.translated field for use by loop detector.

Usage:
    python scripts/migrate_add_translations.py [--dry-run] [--batch-size N]

Options:
    --dry-run       Don't actually update database, just show what would be done
    --batch-size N  Process N messages at a time (default: 100)
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Fix for Windows: Psycopg requires SelectorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.storage.persistence import PersistenceManager
from app.nodes.query_translation.translator import translator

# Import language detection
try:
    from langdetect import detect, detect_langs
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    print("⚠️  langdetect not available, using simple heuristic")


async def get_messages_without_translation():
    """Get all user messages that don't have metadata.translated."""
    from app.storage.persistence import get_db_connection
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT id, session_id, content, metadata
                FROM messages
                WHERE role = 'user'
                ORDER BY created_at ASC
            """)
            rows = await cur.fetchall()
            
            messages_to_translate = []
            for row in rows:
                msg_id, session_id, content, metadata = row
                metadata = metadata or {}
                
                # Check if translation already exists
                if not metadata.get("translated"):
                    messages_to_translate.append({
                        "id": msg_id,
                        "session_id": session_id,
                        "content": content,
                        "metadata": metadata
                    })
            
            return messages_to_translate


async def translate_message(content: str) -> tuple[str, str]:
    """
    Translate message to English.
    
    Returns:
        tuple: (detected_language, translated_content)
    """
    # Detect language
    detected_lang = "en"
    
    if LANGDETECT_AVAILABLE:
        try:
            detected = detect_langs(content)
            if detected:
                detected_lang = detected[0].lang
        except Exception as e:
            print(f"  ⚠️  Language detection failed: {e}, assuming Russian")
            # Simple heuristic fallback
            has_cyrillic = any('а' <= char.lower() <= 'я' for char in content)
            detected_lang = "ru" if has_cyrillic else "en"
    else:
        # Simple heuristic
        has_cyrillic = any('а' <= char.lower() <= 'я' for char in content)
        detected_lang = "ru" if has_cyrillic else "en"
    
    # If already English, no translation needed
    if detected_lang == "en":
        return detected_lang, content
    
    # Translate to English
    try:
        translated = translator.translate_query(content, target_lang="en")
        return detected_lang, translated
    except Exception as e:
        print(f"  ⚠️  Translation failed: {e}, using original")
        return detected_lang, content


async def update_message_metadata(msg_id: int, new_metadata: dict, dry_run: bool = False):
    """Update message metadata in database."""
    if dry_run:
        print(f"  [DRY RUN] Would update message {msg_id} with metadata: {new_metadata}")
        return
    
    from app.storage.persistence import get_db_connection
    import json
    
    async with get_db_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE messages
                SET metadata = %s
                WHERE id = %s
            """, (json.dumps(new_metadata), msg_id))
            await conn.commit()


async def migrate_translations(dry_run: bool = False, batch_size: int = 100):
    """Main migration function."""
    print("🔍 Finding messages without translations...")
    messages = await get_messages_without_translation()
    
    total = len(messages)
    print(f"📊 Found {total} messages to translate")
    
    if total == 0:
        print("✅ All messages already have translations!")
        return
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made\n")
    
    translated_count = 0
    errors = 0
    
    for i, msg in enumerate(messages, 1):
        try:
            print(f"\n[{i}/{total}] Processing message {msg['id']}...")
            print(f"  Content: {msg['content'][:60]}...")
            
            # Translate
            detected_lang, translated = await translate_message(msg['content'])
            print(f"  Detected language: {detected_lang}")
            print(f"  Translated: {translated[:60]}...")
            
            # Update metadata
            new_metadata = msg['metadata'].copy()
            new_metadata['translated'] = translated
            new_metadata['detected_language'] = detected_lang
            
            await update_message_metadata(msg['id'], new_metadata, dry_run=dry_run)
            
            translated_count += 1
            
            # Progress indicator
            if i % batch_size == 0:
                print(f"\n✅ Progress: {i}/{total} ({i/total*100:.1f}%)")
                
        except Exception as e:
            print(f"  ❌ Error processing message {msg['id']}: {e}")
            errors += 1
            continue
    
    print(f"\n{'='*60}")
    print("📊 Migration Summary:")
    print(f"  Total messages: {total}")
    print(f"  Successfully translated: {translated_count}")
    print(f"  Errors: {errors}")
    
    if dry_run:
        print("\n⚠️  This was a DRY RUN - no changes were made to the database")
    else:
        print("\n✅ Migration completed!")


def main():
    parser = argparse.ArgumentParser(
        description="Add English translations to existing messages in database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually update database, just show what would be done"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Process N messages at a time (default: 100)"
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("Message Translation Migration")
    print("="*60)
    
    asyncio.run(migrate_translations(
        dry_run=args.dry_run,
        batch_size=args.batch_size
    ))


if __name__ == "__main__":
    main()
