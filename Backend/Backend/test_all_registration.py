"""
Automated registration test for all 3 roles.
Run from the Backend directory: python test_all_registration.py
"""
import sqlite3, os, sys
from werkzeug.security import generate_password_hash, check_password_hash

# ── Locate DB ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH  = os.path.join(BASE_DIR, 'Database', 'my_tailor.db')
FALLBACK = os.path.join(BASE_DIR, 'Database', 'my_tailor new.db')

def get_db():
    for p in [DB_PATH, FALLBACK]:
        if os.path.exists(p):
            conn = sqlite3.connect(p)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn, p
    raise FileNotFoundError("No DB found")

conn, db_path = get_db()
print(f"✔  Using DB: {db_path}\n")

PASS = "Test@1234"
hashed = generate_password_hash(PASS)

errors = []

def run(label, fn):
    try:
        fn()
        print(f"  ✅  {label}")
    except Exception as e:
        print(f"  ❌  {label}: {e}")
        errors.append(label)

# ── Clean up test rows from previous runs ────────────────────────────────────
for email in ['test_cust@test.com', 'test_tailor@test.com', 'test_admin@test.com']:
    row = conn.execute("SELECT login_id, role FROM login WHERE email=?", (email,)).fetchone()
    if row:
        lid, role = row['login_id'], row['role']
        if role == 'customer':
            conn.execute("DELETE FROM customer WHERE customer_id=?", (lid,))
        elif role == 'tailor':
            conn.execute("DELETE FROM tailor WHERE tailor_id=?", (lid,))
        elif role == 'admin':
            conn.execute("DELETE FROM admin WHERE admin_id=?", (lid,))
        conn.execute("DELETE FROM login WHERE login_id=?", (lid,))
conn.commit()
print("— Previous test rows cleaned up\n")

# ═══════════════════════════════════════════════════════════════════════════════
print("═" * 60)
print("  CUSTOMER REGISTRATION TEST")
print("═" * 60)

def test_customer_insert():
    cur = conn.execute(
        "INSERT INTO login(email, password, role) VALUES(?,?,'customer')",
        ('test_cust@test.com', hashed)
    )
    lid = cur.lastrowid
    conn.execute(
        """INSERT INTO customer(customer_id, name, email, password,
           contact_num, city, address, gender) VALUES(?,?,?,?,?,?,?,?)""",
        (lid, 'Test Customer', 'test_cust@test.com', hashed, '9800000001',
         'Kolhapur', '123 Test Street', 'Male')
    )
    conn.commit()

run("Customer INSERT into login + customer tables", test_customer_insert)

def test_customer_read():
    row = conn.execute(
        "SELECT c.name, c.contact_num, c.gender, l.role "
        "FROM customer c JOIN login l ON c.customer_id=l.login_id "
        "WHERE c.email='test_cust@test.com'"
    ).fetchone()
    assert row, "Customer row not found after insert"
    assert row['name'] == 'Test Customer', f"Name mismatch: {row['name']}"
    assert row['contact_num'] == '9800000001', f"Phone mismatch: {row['contact_num']}"
    assert row['role'] == 'customer', f"Role mismatch: {row['role']}"
    assert row['gender'] == 'Male', f"Gender mismatch: {row['gender']}"

run("Customer data readable & correct after insert", test_customer_read)

def test_customer_password():
    row = conn.execute("SELECT password FROM login WHERE email='test_cust@test.com'").fetchone()
    assert row and check_password_hash(row['password'], PASS), "Password hash mismatch"

run("Customer password hash verifiable", test_customer_password)

def test_customer_duplicate_email():
    row = conn.execute("SELECT email FROM login WHERE email='test_cust@test.com'").fetchone()
    assert row, "Email should exist (duplicate check)"
    # A second insert should fail with UNIQUE constraint
    try:
        conn.execute("INSERT INTO login(email,password,role) VALUES('test_cust@test.com',?,'customer')", (hashed,))
        conn.rollback()
        raise AssertionError("Duplicate email insert succeeded — UNIQUE constraint missing!")
    except sqlite3.IntegrityError:
        pass  # Expected

run("Duplicate customer email correctly rejected", test_customer_duplicate_email)

# ═══════════════════════════════════════════════════════════════════════════════
print()
print("═" * 60)
print("  TAILOR REGISTRATION TEST")
print("═" * 60)

def test_tailor_insert():
    cur = conn.execute(
        "INSERT INTO login(email, password, role) VALUES(?,?,'tailor')",
        ('test_tailor@test.com', hashed)
    )
    lid = cur.lastrowid
    conn.execute(
        """INSERT INTO tailor(tailor_id, name, shop_name, email, password,
           contact_num, shop_address, speciality, experience, gender_category, status)
           VALUES(?,?,?,?,?,?,?,?,?,?,'Active')""",
        (lid, 'Ravi Kumar', 'Ravi Fashion Hub', 'test_tailor@test.com', hashed,
         '9800000002', 'MG Road, Kolhapur', "Men's Clothing", 5, 'Both')
    )
    conn.commit()

run("Tailor INSERT into login + tailor tables", test_tailor_insert)

def test_tailor_read():
    row = conn.execute(
        "SELECT t.name, t.shop_name, t.contact_num, t.status, t.gender_category, l.role "
        "FROM tailor t JOIN login l ON t.tailor_id=l.login_id "
        "WHERE t.email='test_tailor@test.com'"
    ).fetchone()
    assert row, "Tailor row not found after insert"
    assert row['name'] == 'Ravi Kumar', f"Name mismatch: {row['name']}"
    assert row['shop_name'] == 'Ravi Fashion Hub', f"Shop name mismatch: {row['shop_name']}"
    assert row['contact_num'] == '9800000002', f"Phone mismatch: {row['contact_num']}"
    assert row['status'] == 'Active', f"Status should be Active, got: {row['status']}"
    assert row['role'] == 'tailor', f"Role mismatch: {row['role']}"
    assert row['gender_category'] == 'Both', f"Gender cat mismatch: {row['gender_category']}"

run("Tailor data readable & correct after insert", test_tailor_read)

def test_tailor_name_not_shopname():
    row = conn.execute(
        "SELECT name, shop_name FROM tailor WHERE email='test_tailor@test.com'"
    ).fetchone()
    assert row['name'] == 'Ravi Kumar', "Owner name should be distinct from shop name"
    assert row['shop_name'] == 'Ravi Fashion Hub', "Shop name should be stored correctly"
    assert row['name'] != row['shop_name'], "Owner name and shop name must differ"

run("Tailor owner name stored separately from shop name", test_tailor_name_not_shopname)

def test_tailor_status_active():
    row = conn.execute(
        "SELECT status FROM tailor WHERE email='test_tailor@test.com'"
    ).fetchone()
    assert row['status'] == 'Active', f"Tailor status should be 'Active', got '{row['status']}'"

run("Tailor status is 'Active' (not 'Pending')", test_tailor_status_active)

def test_tailor_login_works():
    row = conn.execute(
        "SELECT password FROM login WHERE email='test_tailor@test.com' AND role='tailor'"
    ).fetchone()
    assert row and check_password_hash(row['password'], PASS), "Tailor login credentials invalid"

run("Tailor login credentials valid", test_tailor_login_works)

# ═══════════════════════════════════════════════════════════════════════════════
print()
print("═" * 60)
print("  ADMIN REGISTRATION TEST")
print("═" * 60)

def test_admin_insert():
    cur = conn.execute(
        "INSERT INTO login(email, password, role) VALUES(?,?,'admin')",
        ('test_admin@test.com', hashed)
    )
    lid = cur.lastrowid
    conn.execute(
        "INSERT INTO admin(admin_id, name, email, password) VALUES(?,?,?,?)",
        (lid, 'Test Admin', 'test_admin@test.com', hashed)
    )
    conn.commit()

run("Admin INSERT into login + admin tables", test_admin_insert)

def test_admin_read():
    row = conn.execute(
        "SELECT a.name, l.role FROM admin a JOIN login l ON a.admin_id=l.login_id "
        "WHERE a.email='test_admin@test.com'"
    ).fetchone()
    assert row, "Admin row not found after insert"
    assert row['name'] == 'Test Admin', f"Name mismatch: {row['name']}"
    assert row['role'] == 'admin', f"Role mismatch: {row['role']}"

run("Admin data readable & correct after insert", test_admin_read)

def test_admin_login_works():
    row = conn.execute(
        "SELECT password FROM login WHERE email='test_admin@test.com' AND role='admin'"
    ).fetchone()
    assert row and check_password_hash(row['password'], PASS), "Admin login credentials invalid"

run("Admin login credentials valid", test_admin_login_works)

# ═══════════════════════════════════════════════════════════════════════════════
print()
print("═" * 60)
print("  CROSS-ROLE VALIDATION TESTS")
print("═" * 60)

def test_no_cross_role_login():
    # Customer email should not match as tailor
    row = conn.execute(
        "SELECT * FROM login WHERE email='test_cust@test.com' AND role='tailor'"
    ).fetchone()
    assert not row, "Customer email matched as tailor — cross-role login possible!"

run("Customer email not loginable as tailor", test_no_cross_role_login)

def test_tailor_in_customer_table():
    row = conn.execute(
        "SELECT * FROM customer WHERE email='test_tailor@test.com'"
    ).fetchone()
    assert not row, "Tailor email found in customer table — role isolation failed"

run("Tailor not duplicated in customer table", test_tailor_in_customer_table)

def test_customer_in_tailor_table():
    row = conn.execute(
        "SELECT * FROM tailor WHERE email='test_cust@test.com'"
    ).fetchone()
    assert not row, "Customer email found in tailor table — role isolation failed"

run("Customer not duplicated in tailor table", test_customer_in_tailor_table)

# ── Cleanup ──────────────────────────────────────────────────────────────────
for email, role_tbl in [
    ('test_cust@test.com', ('customer','customer_id')),
    ('test_tailor@test.com', ('tailor','tailor_id')),
    ('test_admin@test.com', ('admin','admin_id')),
]:
    row = conn.execute("SELECT login_id FROM login WHERE email=?", (email,)).fetchone()
    if row:
        conn.execute(f"DELETE FROM {role_tbl[0]} WHERE {role_tbl[1]}=?", (row['login_id'],))
        conn.execute("DELETE FROM login WHERE login_id=?", (row['login_id'],))
conn.commit()
conn.close()
print("\n— Test rows cleaned up from DB\n")

# ── Summary ──────────────────────────────────────────────────────────────────
print("═" * 60)
total = 13
passed = total - len(errors)
print(f"  RESULTS: {passed}/{total} tests passed")
if errors:
    print(f"  FAILED:  {errors}")
    sys.exit(1)
else:
    print("  ALL TESTS PASSED ✅")
print("═" * 60)
