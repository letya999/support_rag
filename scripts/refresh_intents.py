#!/usr/bin/env python3
"""
Скрипт для автогенерации реестра интентов и категорий из базы данных.

Логика:
1. Подключение к Postgres (хранилище документов).
2. Получение списка уникальных категорий (DISTINCT metadata->>'category').
3. Для каждой категории получение списка уникальных интентов (DISTINCT metadata->>'intent').
4. Сборка иерархического YAML-файла.

Использование:
    python scripts/refresh_intents.py
    python scripts/refresh_intents.py --output custom_path.yaml
"""

import sys
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import asyncio
import psycopg
import yaml

from app.settings import settings


# Default output path for the registry
DEFAULT_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "nodes", "_shared_config", "intents_registry.yaml"
)


# Optional enrichment for categories (technical key -> human description)
# This can be extended or loaded from a separate file
CATEGORY_ENRICHMENT = {
    "billing": "Payment, invoices, and subscription billing",
    "technical_support": "Technical issues, API errors, and troubleshooting",
    "account": "Account access, password reset, and profile management",
    "orders": "Order management, tracking, and history",
    "shipping": "Shipping, delivery, and logistics",
    "returns": "Returns, refunds, and exchanges",
    "general": "General information and FAQ",
    "support": "Customer support and assistance",
}


async def fetch_categories_and_intents(db_url: str) -> Dict[str, List[str]]:
    """
    Fetch unique categories and their associated intents from the documents table.
    
    Returns:
        Dict mapping category names to lists of intents
    """
    categories_intents: Dict[str, List[str]] = {}
    
    async with await psycopg.AsyncConnection.connect(db_url, autocommit=True) as conn:
        async with conn.cursor() as cur:
            # Fetch all distinct (category, intent) pairs in one query
            # This is more efficient than multiple queries
            await cur.execute("""
                SELECT 
                    COALESCE(metadata->>'category', 'unknown') as category,
                    COALESCE(metadata->>'intent', 'unknown') as intent,
                    COUNT(*) as doc_count
                FROM documents
                WHERE metadata IS NOT NULL
                GROUP BY 
                    metadata->>'category',
                    metadata->>'intent'
                ORDER BY category, intent
            """)
            
            rows = await cur.fetchall()
            
            for row in rows:
                category = row[0] or "unknown"
                intent = row[1] or "unknown"
                doc_count = row[2]
                
                # Skip unknown/null values
                if category.lower() in ('unknown', 'null', ''):
                    continue
                if intent.lower() in ('unknown', 'null', ''):
                    # Still add the category even without intents
                    if category not in categories_intents:
                        categories_intents[category] = []
                    continue
                
                if category not in categories_intents:
                    categories_intents[category] = []
                
                if intent not in categories_intents[category]:
                    categories_intents[category].append(intent)
    
    return categories_intents


def build_registry_yaml(
    categories_intents: Dict[str, List[str]],
    source_db: str = "postgres:documents"
) -> Dict[str, Any]:
    """
    Build the YAML registry structure from the extracted data.
    """
    registry = {
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_db": source_db,
            "total_categories": len(categories_intents),
            "total_intents": sum(len(intents) for intents in categories_intents.values()),
            "warning": "⚠️ АВТОГЕНЕРИРУЕМЫЙ ФАЙЛ - не редактируйте вручную!"
        },
        "categories": []
    }
    
    for category_name, intents in sorted(categories_intents.items()):
        category_entry = {
            "name": category_name,
            "description": get_category_description(category_name),
            "intents": sorted(intents) if intents else []
        }
        registry["categories"].append(category_entry)
    
    return registry


def get_category_description(category: str) -> str:
    """
    Get a human-readable description for a category.
    Uses enrichment map with fallback to auto-generated description.
    """
    # Check exact match
    if category in CATEGORY_ENRICHMENT:
        return CATEGORY_ENRICHMENT[category]
    
    # Check lowercase match
    lower_cat = category.lower().replace(" ", "_").replace("-", "_")
    if lower_cat in CATEGORY_ENRICHMENT:
        return CATEGORY_ENRICHMENT[lower_cat]
    
    # Fallback: generate description from category name
    readable_name = category.replace("_", " ").replace("-", " ").title()
    return f"Questions related to {readable_name}"


def save_registry(registry: Dict[str, Any], output_path: str) -> None:
    """
    Save the registry to a YAML file.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Add header comment
        f.write("# ============================================================\n")
        f.write("# Intent Registry - AUTO-GENERATED FILE\n")
        f.write("# ============================================================\n")
        f.write("# This file is automatically generated by scripts/refresh_intents.py\n")
        f.write("# DO NOT EDIT MANUALLY - changes will be overwritten!\n")
        f.write("#\n")
        f.write("# To regenerate: python scripts/refresh_intents.py\n")
        f.write("# ============================================================\n\n")
        
        yaml.dump(
            registry, 
            f, 
            default_flow_style=False, 
            allow_unicode=True,
            sort_keys=False,
            width=120
        )


async def refresh_intents(output_path: str = DEFAULT_REGISTRY_PATH) -> bool:
    """
    Main function to refresh the intents registry from the database.
    
    Returns:
        True if successful, False otherwise
    """
    if not settings.DATABASE_URL:
        print("❌ Error: DATABASE_URL is not set in environment.")
        return False
    
    print("🔄 Starting intent registry refresh...")
    print(f"   Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'configured'}")
    print(f"   Output: {output_path}")
    
    try:
        # Fetch data from database
        print("\n📊 Fetching categories and intents from database...")
        categories_intents = await fetch_categories_and_intents(settings.DATABASE_URL)
        
        if not categories_intents:
            print("⚠️  Warning: No categories found in database metadata.")
            print("   Make sure documents have 'category' field in their metadata.")
            # Still create an empty registry
            categories_intents = {}
        
        # Build registry structure
        print(f"\n🏗️  Building registry:")
        print(f"   - Categories: {len(categories_intents)}")
        print(f"   - Total intents: {sum(len(i) for i in categories_intents.values())}")
        
        for cat, intents in sorted(categories_intents.items()):
            print(f"   • {cat}: {len(intents)} intents")
        
        registry = build_registry_yaml(categories_intents)
        
        # Save to file
        save_registry(registry, output_path)
        print(f"\n✅ Registry saved successfully to: {output_path}")
        
        return True
        
    except psycopg.Error as e:
        print(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Refresh the intents registry from database metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/refresh_intents.py
  python scripts/refresh_intents.py --output /path/to/custom_registry.yaml
        """
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=DEFAULT_REGISTRY_PATH,
        help=f"Output path for the registry YAML file (default: {DEFAULT_REGISTRY_PATH})"
    )
    
    args = parser.parse_args()
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    success = asyncio.run(refresh_intents(args.output))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
