# Migration Scripts

This directory contains scripts for data migration and cleanup.

## Available Scripts

### 1. `migrate_add_translations.py`
Adds English translations to existing user messages in the database.

**Purpose:**
- Translates all user messages to English
- Stores translation in `metadata.translated` field
- Required for translation-based loop detection

**Usage:**
```bash
# Dry run (see what would be changed)
python scripts/migrate_add_translations.py --dry-run

# Real migration
python scripts/migrate_add_translations.py

# Process in smaller batches
python scripts/migrate_add_translations.py --batch-size 50
```

**Requirements:**
- `langdetect` package (optional, uses heuristic if not available)
- Database credentials configured in `.env`
- **Windows users**: Script automatically uses SelectorEventLoop for psycopg compatibility

**Note for Windows:**
The script automatically configures the correct event loop policy for Windows.
If you see errors about ProactorEventLoop, the script should handle this automatically.

---

### 2. `cleanup_deprecated_cache.py`
Safely removes deprecated cache files after architectural refactoring.

**Purpose:**
- Removes old cache implementation files
- Keeps necessary files (models, __init__, etc.)
- Helps clean up codebase after migration

**Usage:**
```bash
# Dry run (see what would be deleted)
python scripts/cleanup_deprecated_cache.py --dry-run

# Real cleanup (with confirmation)
python scripts/cleanup_deprecated_cache.py
```

**Files to be deleted:**
- `app/cache/nodes.py`
- `app/cache/cache_layer.py`
- `app/cache/session_manager.py`

**Files kept:**
- `app/cache/__init__.py` (compatibility layer)
- `app/cache/models.py`
- `app/cache/query_normalizer.py`
- `app/cache/cache_stats.py`
- `app/cache/DEPRECATED.md`

---

## Migration Workflow

Recommended order:

1. **Backup your database** (always!)
   ```bash
   pg_dump support_rag > backup_$(date +%Y%m%d).sql
   ```

2. **Test pipeline** with new cache nodes
   - Verify everything works
   - Check logs for errors

3. **Optional: Run translation migration**
   ```bash
   python scripts/migrate_add_translations.py --dry-run
   # If looks good:
   python scripts/migrate_add_translations.py
   ```

4. **After confirming everything works well:**
   ```bash
   python scripts/cleanup_deprecated_cache.py --dry-run
   # If looks good:
   python scripts/cleanup_deprecated_cache.py
   ```

---

## Troubleshooting

### Migration script fails
- Check database connection
- Verify `langdetect` is installed: `pip install langdetect`
- Review error messages in output

### Cleanup script removes wrong files
- Always run with `--dry-run` first
- Check the file list before confirming
- You can restore from git if needed

---

## Rollback

If something goes wrong:

1. **Translation migration**: 
   - Restore database from backup
   - Or manually clear `metadata.translated` fields

2. **Cleanup**:
   - Restore files from git: `git checkout app/cache/`

---

## Support

See `MASTER_PLAN.md` for full context of the architectural refactoring.
