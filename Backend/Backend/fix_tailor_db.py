import sqlite3
import os

paths = [
    r'y:\My_Tailor_google _COPY updated\My_Tailor_google _COPY alternative\My_Tailor\Backend\Backend\mytailor.db',
    r'y:\My_Tailor_google _COPY updated\My_Tailor_google _COPY alternative\My_Tailor\Database\my_tailor.db',
    r'y:\My_Tailor_google _COPY updated\My_Tailor_google _COPY alternative\My_Tailor\Database\my_tailor new.db',
]

# Activate all tailors and ensure status column exists
print("=== Scanning Databases ===")
for path in paths:
    if not os.path.exists(path):
        print(f"NOT FOUND: {path}")
        continue
    conn = sqlite3.connect(path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"\n{os.path.basename(path)}: {tables}")

    if 'tailor' not in tables:
        conn.close()
        continue

    # Show tailor table columns
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tailor)").fetchall()]
    print(f"  Columns: {cols}")

    # Ensure status column exists (Active by default, no payment required)
    alter_sqls = [
        "ALTER TABLE tailor ADD COLUMN status TEXT DEFAULT 'Active'",
        "ALTER TABLE tailor ADD COLUMN gender_category TEXT DEFAULT 'Both'",
    ]
    for sql in alter_sqls:
        try:
            conn.execute(sql)
            print(f"  [ADDED] {sql.split('ADD COLUMN')[1].split()[0]}")
        except sqlite3.OperationalError:
            print(f"  [OK]    {sql.split('ADD COLUMN')[1].split()[0]} already exists")

    # Activate all tailors (no payment gate)
    r = conn.execute("UPDATE tailor SET status='Active' WHERE status IS NULL OR status != 'Active'")
    conn.commit()
    print(f"  Activated {r.rowcount} tailor rows")

    # Show tailor list
    tailors = conn.execute("SELECT tailor_id, shop_name, status FROM tailor").fetchall()
    print(f"\n  === Tailors ({len(tailors)}) ===")
    for t in tailors:
        print(f"    ID={t[0]} | {t[1]} | status={t[2]}")

    conn.close()

print("\nDone.")
