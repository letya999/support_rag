"""
Cleanup script: Replace deprecated cache files with compatibility stubs.

This script replaces old cache implementation files with lightweight stub files
that re-export from new locations, ensuring backward compatibility.

IMPORTANT: Run this ONLY after verifying that:
1. New cache services and nodes are working correctly
2. You want to maintain backward compatibility with old imports

Usage:
    python scripts/cleanup_deprecated_cache.py [--dry-run]

Options:
    --dry-run    Show what would be changed without actually changing
"""

import argparse
import os
import sys
from pathlib import Path

# Fix for Windows: Ensure compatibility
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Stub file templates
CACHE_LAYER_STUB = '''"""
DEPRECATED: app/cache/cache_layer.py
This file has been moved to app/services/cache/manager.py
"""
import warnings
warnings.warn("Use 'from app.services.cache.manager import ...' instead.", DeprecationWarning, stacklevel=2)
from app.services.cache.manager import CacheManager, get_cache_manager
__all__ = ["CacheManager", "get_cache_manager"]
'''

SESSION_MANAGER_STUB = '''"""
DEPRECATED: app/cache/session_manager.py
This file has been moved to app/services/cache/session.py
"""
import warnings
warnings.warn("Use 'from app.services.cache.session import ...' instead.", DeprecationWarning, stacklevel=2)
from app.services.cache.session import SessionManager
__all__ = ["SessionManager"]
'''

NODES_STUB = '''"""
DEPRECATED: app/cache/nodes.py
Cache nodes have been refactored into separate modules.
"""
import warnings
warnings.warn("Use individual node imports from app.nodes.* instead.", DeprecationWarning, stacklevel=2)
from app.nodes.check_cache.node import check_cache_node
from app.nodes.store_in_cache.node import store_in_cache_node
from app.nodes.cache_similarity.node import cache_similarity_node
__all__ = ["check_cache_node", "store_in_cache_node", "cache_similarity_node"]
'''

STUB_MAP = {
    "app/cache/cache_layer.py": CACHE_LAYER_STUB,
    "app/cache/session_manager.py": SESSION_MANAGER_STUB,
    "app/cache/nodes.py": NODES_STUB,
}

# Files to keep
FILES_TO_KEEP = [
    "app/cache/__init__.py",  # Compatibility layer
    "app/cache/models.py",    # Data models
    "app/cache/query_normalizer.py",  # Query preprocessing
    "app/cache/cache_stats.py",  # Statistics
    "app/cache/DEPRECATED.md",  # Documentation
]


def cleanup_deprecated_files(dry_run: bool = False):
    """Replace deprecated cache files with compatibility stubs."""
    project_root = Path(__file__).parent.parent
    
    print("="*60)
    print("Deprecated Cache Files Cleanup")
    print("="*60)
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No files will be modified\n")
    
    replaced_count = 0
    not_found_count = 0
    
    for file_path, stub_content in STUB_MAP.items():
        full_path = project_root / file_path
        
        print(f"\n📄 {file_path}")
        
        if full_path.exists():
            file_size = full_path.stat().st_size
            print(f"   Original size: {file_size:,} bytes")
            
            if dry_run:
                print(f"   [DRY RUN] Would replace with ~{len(stub_content)} byte stub")
            else:
                try:
                    # Backup original if it's large
                    if file_size > 1000:
                        backup_path = full_path.with_suffix('.py.bak')
                        if not backup_path.exists():
                            full_path.rename(backup_path)
                            print(f"   📦 Backed up to: {backup_path.name}")
                        else:
                            full_path.unlink()
                    else:
                        full_path.unlink()
                    
                    # Write stub
                    full_path.write_text(stub_content, encoding='utf-8')
                    print(f"   ✅ Replaced with compatibility stub ({len(stub_content)} bytes)")
                    replaced_count += 1
                except Exception as e:
                    print(f"   ❌ Error: {e}")
        else:
            print(f"   ⚠️  Not found (will create stub)")
            
            if not dry_run:
                try:
                    full_path.write_text(stub_content, encoding='utf-8')
                    print(f"   ✅ Created stub ({len(stub_content)} bytes)")
                    replaced_count += 1
                except Exception as e:
                    print(f"   ❌ Error creating stub: {e}")
                    not_found_count += 1
    
    print(f"\n{'='*60}")
    print("Files kept for compatibility:")
    for file_path in FILES_TO_KEEP:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ⚠️  {file_path} - Missing!")
    
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Files replaced/created: {replaced_count}")
    print(f"  Total processed: {len(STUB_MAP)}")
    
    if dry_run:
        print("\n⚠️  This was a DRY RUN - no files were modified")
    else:
        print("\n✅ Cleanup completed!")
        print("\nWhat was done:")
        print("  - Old implementation files replaced with lightweight stubs")
        print("  - Stubs re-export from new locations (services/cache, nodes/*)")
        print("  - Full backward compatibility maintained")
        print("  - Deprecated warnings will alert developers to update imports")
        print("\nNext steps:")
        print("  1. Restart the application - it should work normally")
        print("  2. Update imports in your code to use new paths (optional)")
        print("  3. Check logs for deprecation warnings")


def main():
    parser = argparse.ArgumentParser(
        description="Replace deprecated cache files with compatibility stubs"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    
    args = parser.parse_args()
    
    if not args.dry_run:
        print("\n⚠️  WARNING: This will DELETE files from app/cache/")
        print("Make sure you have:")
        print("  1. Backed up your code")
        print("  2. Verified new nodes work correctly")
        print("  3. Updated all imports (or use compatibility layer)")
        
        response = input("\nContinue? (yes/no): ").strip().lower()
        if response != "yes":
            print("❌ Cancelled")
            return
    
    cleanup_deprecated_files(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
