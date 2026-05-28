"""
test_tailor_reg.py — Updated to reflect the removal of the Admin Revenue Model.
Tailors no longer require payment or activation; they are Active by default after registration.
"""
import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = r'y:\My_Tailor_google _COPY updated\My_Tailor_google _COPY alternative\My_Tailor\Database\my_tailor.db'

def test_tailor_registration():
    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Check existing tailors
    tailors = conn.execute("SELECT tailor_id, shop_name, status FROM tailor").fetchall()
    print(f"\n=== Tailor Registration Test ===")
    print(f"Total tailors: {len(tailors)}")
    for t in tailors:
        print(f"  ID={t['tailor_id']} | {t['shop_name']} | status={t['status']}")

    # Verify all tailors are Active (no payment required)
    inactive = [t for t in tailors if t['status'] != 'Active']
    if inactive:
        print(f"\n  WARNING: {len(inactive)} tailor(s) are not Active:")
        for t in inactive:
            print(f"     - {t['shop_name']} (status={t['status']})")
    else:
        print(f"\n  PASS: All {len(tailors)} tailors are Active -- no payment gate required.")

    conn.close()

if __name__ == "__main__":
    test_tailor_registration()
