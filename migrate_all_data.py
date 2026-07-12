"""Migrate all data from legacy DB to project DB, then delete legacy."""
import sqlite3
from pathlib import Path
import shutil

legacy_db = Path.home() / ".trimp" / "TrimP.db"
project_db = Path.home() / "Projects/copilot-token-optimizer/data/TrimP.db"

print(f"Migrating from: {legacy_db}")
print(f"           to: {project_db}")
print()

if not legacy_db.exists():
    print("✅ Legacy database doesn't exist - nothing to migrate")
    exit(0)

# Backup legacy database first
backup_path = legacy_db.parent / "TrimP.db.backup"
shutil.copy(legacy_db, backup_path)
print(f"✅ Backed up legacy DB to: {backup_path}")

# Connect to both
src = sqlite3.connect(str(legacy_db))
src.row_factory = sqlite3.Row
dst = sqlite3.connect(str(project_db))

tables_to_migrate = [
    'sessions', 'turns', 'checkpoints', 'compressions', 
    'quality_scores', 'archives', 'session_files', 'model_routing',
    'token_budgets', 'compression_patterns', 'savings', 'memory_audits',
    'config', 'loop_detections', 'activity_modes'
]

migrated_counts = {}

for table in tables_to_migrate:
    try:
        # Check if table exists in source
        count = src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count == 0:
            migrated_counts[table] = 0
            continue
            
        # Get all rows
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        
        # Get column names
        columns = [desc[0] for desc in src.execute(f"SELECT * FROM {table} LIMIT 1").description]
        placeholders = ','.join(['?' for _ in columns])
        col_str = ','.join(columns)
        
        # Insert or replace into destination
        for row in rows:
            try:
                dst.execute(
                    f"INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({placeholders})",
                    tuple(row)
                )
            except Exception as e:
                print(f"  ⚠️  Error inserting into {table}: {e}")
                continue
        
        migrated_counts[table] = len(rows)
        
    except Exception as e:
        print(f"  ⚠️  Error migrating {table}: {e}")
        migrated_counts[table] = 0

dst.commit()
src.close()
dst.close()

print("\n📊 Migration Summary:")
for table, count in migrated_counts.items():
    if count > 0:
        print(f"  ✅ {table}: {count} rows")

print(f"\n✅ Migration complete!")
print(f"   Backup saved at: {backup_path}")
print(f"\n⚠️  To delete legacy database, run:")
print(f"   rm {legacy_db}")
