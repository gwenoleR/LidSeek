import sqlite3
import os

MIGRATIONS = [
    {
        'name': 'add_source_username_and_blacklist',
        'sql': [
            # Add source_username field to albums
            """
            ALTER TABLE albums ADD COLUMN source_username TEXT;
            """,
            # Table pour blacklist des sources par album
            """
            CREATE TABLE IF NOT EXISTS album_blacklist_sources (
                album_id TEXT NOT NULL,
                username TEXT NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (album_id, username)
            );
            """
        ]
    }
]

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'downloads.db')


def run_migrations():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Create migration table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS migrations (
                name TEXT PRIMARY KEY,
                applied_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        for migration in MIGRATIONS:
            cursor.execute('SELECT name FROM migrations WHERE name = ?', (migration['name'],))
            if cursor.fetchone():
                print(f"Migration déjà appliquée: {migration['name']}")
                continue
            for sql in migration['sql']:
                try:
                    cursor.execute(sql)
                except sqlite3.OperationalError as e:
                    # Ignore l'erreur si la colonne existe déjà
                    if 'duplicate column name' in str(e) or 'already exists' in str(e):
                        continue
                    else:
                        raise
            cursor.execute('INSERT INTO migrations (name) VALUES (?)', (migration['name'],))
            conn.commit()
            print(f"Migration appliquée: {migration['name']}")

if __name__ == "__main__":
    run_migrations()
