"""
Database migration to add UI enhancement columns.
Run this once to upgrade the schema.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".trimp" / "TrimP.db"


def migrate():
    """Add new columns for enhanced UI."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    migrations = [
        # Add model tracking
        "ALTER TABLE compressions ADD COLUMN model_used TEXT DEFAULT 'Claude Sonnet 4.5'",
        
        # Add text previews (first 500 chars of original and compressed)
        "ALTER TABLE compressions ADD COLUMN original_text TEXT",
        "ALTER TABLE compressions ADD COLUMN compressed_text TEXT",
        
        # Add compression method details
        "ALTER TABLE compressions ADD COLUMN compression_method TEXT",
        "ALTER TABLE compressions ADD COLUMN algorithm_details TEXT",
        
        # Add indexes for performance
        "CREATE INDEX IF NOT EXISTS idx_compressions_model ON compressions(model_used)",
    ]
    
    for migration in migrations:
        try:
            cursor.execute(migration)
            print(f"✓ {migration[:60]}...")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"⊘ Column already exists: {migration[:40]}...")
            else:
                print(f"✗ Error: {e}")
    
    conn.commit()
    conn.close()
    print("\n✅ Migration complete!")


if __name__ == "__main__":
    migrate()
