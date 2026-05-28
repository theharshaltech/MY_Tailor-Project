import sqlite3
import os

db_paths = [
    r'Database\my_tailor.db',
    r'Database\my_tailor new.db',
]

base = os.path.dirname(os.path.abspath(__file__))

for rel_path in db_paths:
    path = os.path.join(base, rel_path)
    if not os.path.exists(path):
        print(f'SKIP (not found): {path}')
        continue
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row

        cols = [r[1] for r in conn.execute('PRAGMA table_info(tailor)').fetchall()]
        print(f'\n--- {os.path.basename(path)} ---')
        print(f'Tailor columns: {cols}')

        ocols = [r[1] for r in conn.execute('PRAGMA table_info(orders)').fetchall()]
        print(f'Orders columns: {ocols}')

        # Ensure status column exists, then activate all tailors
        if 'status' not in cols:
            conn.execute("ALTER TABLE tailor ADD COLUMN status TEXT DEFAULT 'Active'")
            print('Added status column')
        
        conn.execute("UPDATE tailor SET status='Active'")
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM tailor WHERE status='Active'").fetchone()[0]
        print(f'Active tailors after migration: {count}')

        # Remove service_fee from orders if it exists (optional cleanup note)
        if 'service_fee' in ocols:
            print('NOTE: service_fee column exists in orders table - it is now unused and safe to ignore.')

        conn.close()
        print(f'Migration complete for {os.path.basename(path)}')
    except Exception as e:
        print(f'ERROR on {path}: {e}')

print('\nAll done.')
