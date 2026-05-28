import sqlite3, os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, 'Database', 'my_tailor.db')
FALLBACK = os.path.join(BASE_DIR, 'Database', 'my_tailor new.db')

found = None
for p in [DB_PATH, FALLBACK]:
    if os.path.exists(p):
        found = p
        break

if not found:
    # search cwd
    for f in os.listdir('.'):
        if f.endswith('.db'):
            found = os.path.abspath(f)
            break

if not found:
    db_dir = os.path.join(BASE_DIR, 'Database')
    print("No DB found. BASE_DIR:", BASE_DIR)
    if os.path.exists(db_dir):
        print("DB dir contents:", os.listdir(db_dir))
    else:
        print("DB dir missing. Checking parent dirs...")
        for root, dirs, files in os.walk(BASE_DIR):
            for f in files:
                if f.endswith('.db'):
                    print("Found:", os.path.join(root, f))
else:
    print("Using DB:", found)
    conn = sqlite3.connect(found)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print("Tables:", tables)
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = cur.fetchall()
        print(f"\n  {t}:")
        for c in cols:
            print(f"    col_id={c[0]} name={c[1]} type={c[2]} notnull={c[3]} default={c[4]}")
    conn.close()
