"""
HTTP-level integration test for the /Registration and /Login routes.
Run WHILE Flask is running: python test_http_registration.py
"""
import requests, sys

BASE = "http://127.0.0.1:5000"
session = requests.Session()   # keeps cookies for flash messages

PASS = "Test@1234"

errors = []
def run(label, fn):
    try:
        fn()
        print(f"  [PASS] {label}")
    except AssertionError as e:
        print(f"  [FAIL] {label}: {e}")
        errors.append(label)

def check_server():
    r = requests.get(BASE + "/Registration", timeout=3)
    assert r.status_code == 200, f"Server not reachable: {r.status_code}"
run("Flask server is running", check_server)

# ─────────────────────────────────────────────────────────────────
print("\n--- CUSTOMER REGISTRATION ---")

def reg_customer():
    s = requests.Session()
    r = s.post(BASE + "/Registration", data={
        "role": "customer",
        "email": "http_test_cust@test.com",
        "password": PASS,
        "name": "HTTP Test Customer",
        "customer_phone": "9911000001",
        "gender": "Male",
        "city": "Kolhapur",
        "address": "123 Test St",
    }, allow_redirects=False)
    # Should redirect to /Login (302)
    assert r.status_code == 302, f"Expected 302 redirect, got {r.status_code}. Body: {r.text[:300]}"
    assert "/Login" in r.headers.get("Location",""), f"Redirect not to /Login: {r.headers.get('Location')}"

run("Customer registration returns 302 -> /Login", reg_customer)

def reg_customer_dup():
    s = requests.Session()
    r = s.post(BASE + "/Registration", data={
        "role": "customer",
        "email": "http_test_cust@test.com",
        "password": PASS,
        "name": "HTTP Test Customer",
        "customer_phone": "9911000001",
        "gender": "Male",
        "city": "Kolhapur",
        "address": "123 Test St",
    }, allow_redirects=True)
    # Should show the registration page again with error
    assert r.status_code == 200, f"Unexpected status: {r.status_code}"
    body = r.text.lower()
    assert "already registered" in body or "email" in body, \
        f"No duplicate-email error message found. Body snippet: {r.text[:400]}"

run("Duplicate customer email shows error on Registration page", reg_customer_dup)

def login_customer():
    s = requests.Session()
    r = s.post(BASE + "/Login", data={
        "role": "customer",
        "email": "http_test_cust@test.com",
        "password": PASS,
    }, allow_redirects=False)
    assert r.status_code == 302, f"Expected 302 redirect on login, got {r.status_code}"
    assert "customer" in r.headers.get("Location","").lower() or "/customer" in r.headers.get("Location",""), \
        f"Expected redirect to customer dashboard, got: {r.headers.get('Location')}"

run("Registered customer can login and is redirected to dashboard", login_customer)

def login_customer_wrong_role():
    s = requests.Session()
    r = s.post(BASE + "/Login", data={
        "role": "tailor",        # Wrong role
        "email": "http_test_cust@test.com",
        "password": PASS,
    }, allow_redirects=True)
    assert r.status_code == 200, f"Expected 200 (login page with error), got {r.status_code}"
    assert "Login" in r.text or "invalid" in r.text.lower(), \
        "Expected login failure for wrong role"

run("Customer login as 'tailor' role correctly fails", login_customer_wrong_role)

# ─────────────────────────────────────────────────────────────────
print("\n--- TAILOR REGISTRATION ---")

def reg_tailor():
    s = requests.Session()
    r = s.post(BASE + "/Registration", data={
        "role": "tailor",
        "email": "http_test_tailor@test.com",
        "password": PASS,
        "tailor_name": "HTTP Test Tailor",
        "shop_name": "HTTP Test Shop",
        "tailor_phone": "9911000002",
        "location": "MG Road Kolhapur",
        "speciality": "All Types",
        "gender_category": "Both",
        "experience": "5",
    }, allow_redirects=False)
    assert r.status_code == 302, f"Expected 302 redirect, got {r.status_code}. Body: {r.text[:500]}"
    assert "/Login" in r.headers.get("Location",""), f"Redirect not to /Login: {r.headers.get('Location')}"

run("Tailor registration returns 302 -> /Login", reg_tailor)

def reg_tailor_no_owner_name():
    """Should fail validation — tailor_name is blank"""
    s = requests.Session()
    r = s.post(BASE + "/Registration", data={
        "role": "tailor",
        "email": "http_test_tailor2@test.com",
        "password": PASS,
        "tailor_name": "",          # Missing
        "shop_name": "HTTP Test Shop 2",
        "tailor_phone": "9911000003",
        "location": "MG Road",
    }, allow_redirects=True)
    assert r.status_code == 200, f"Expected 200 (error page), got {r.status_code}"
    body = r.text.lower()
    assert "required" in body or "name" in body, \
        f"Expected validation error for missing name. Body: {r.text[:300]}"

run("Tailor registration without owner name shows validation error", reg_tailor_no_owner_name)

def reg_tailor_bad_phone():
    s = requests.Session()
    r = s.post(BASE + "/Registration", data={
        "role": "tailor",
        "email": "http_test_tailor3@test.com",
        "password": PASS,
        "tailor_name": "Bad Phone Tailor",
        "shop_name": "Some Shop",
        "tailor_phone": "123",      # Invalid phone
        "location": "Somewhere",
    }, allow_redirects=True)
    assert r.status_code == 200, f"Expected 200 (error page), got {r.status_code}"
    body = r.text.lower()
    assert "phone" in body or "10-digit" in body or "valid" in body, \
        f"Expected phone validation error. Body: {r.text[:300]}"

run("Tailor registration with invalid phone shows error", reg_tailor_bad_phone)

def login_tailor():
    s = requests.Session()
    r = s.post(BASE + "/Login", data={
        "role": "tailor",
        "email": "http_test_tailor@test.com",
        "password": PASS,
    }, allow_redirects=False)
    assert r.status_code == 302, f"Expected 302 redirect on tailor login, got {r.status_code}"
    location = r.headers.get("Location", "")
    assert "tailor" in location.lower() or "/tailor" in location, \
        f"Expected redirect to tailor dashboard, got: {location}"

run("Registered tailor can login and is redirected to tailor dashboard", login_tailor)

# ─────────────────────────────────────────────────────────────────
print("\n--- ADMIN REGISTRATION ---")

def reg_admin():
    s = requests.Session()
    r = s.post(BASE + "/Registration", data={
        "role": "admin",
        "email": "http_test_admin@test.com",
        "password": PASS,
        "admin_name": "HTTP Test Admin",
        "admin_code": "TAILOR_ADMIN_2026",
    }, allow_redirects=False)
    assert r.status_code == 302, f"Expected 302 redirect, got {r.status_code}. Body: {r.text[:300]}"
    assert "/Login" in r.headers.get("Location",""), f"Redirect not to /Login: {r.headers.get('Location')}"

run("Admin registration with correct code returns 302 -> /Login", reg_admin)

def reg_admin_wrong_code():
    s = requests.Session()
    r = s.post(BASE + "/Registration", data={
        "role": "admin",
        "email": "http_test_admin2@test.com",
        "password": PASS,
        "admin_name": "Bad Admin",
        "admin_code": "WRONG_CODE",
    }, allow_redirects=True)
    assert r.status_code == 200, f"Expected 200 (error page), got {r.status_code}"
    body = r.text.lower()
    assert "invalid" in body or "secret" in body or "code" in body, \
        f"Expected invalid admin code error. Body: {r.text[:300]}"

run("Admin registration with wrong secret code shows error", reg_admin_wrong_code)

# ─────────────────────────────────────────────────────────────────
print("\n--- GENERAL VALIDATION ---")

def reg_short_password():
    s = requests.Session()
    r = s.post(BASE + "/Registration", data={
        "role": "customer",
        "email": "shortpass@test.com",
        "password": "123",          # Too short
        "name": "Short Pass",
        "customer_phone": "9911000004",
        "gender": "Male",
    }, allow_redirects=True)
    assert r.status_code == 200
    body = r.text.lower()
    assert "6 character" in body or "password" in body, \
        f"Expected short password error. Body: {r.text[:300]}"

run("Registration with password < 6 chars shows error", reg_short_password)

def reg_invalid_email():
    s = requests.Session()
    r = s.post(BASE + "/Registration", data={
        "role": "customer",
        "email": "notanemail",
        "password": PASS,
        "name": "Bad Email",
        "customer_phone": "9911000005",
        "gender": "Male",
    }, allow_redirects=True)
    assert r.status_code == 200
    body = r.text.lower()
    assert "email" in body or "invalid" in body, \
        f"Expected invalid email error. Body: {r.text[:300]}"

run("Registration with invalid email shows error", reg_invalid_email)

# ─────────────────────────────────────────────────────────────────
# Cleanup test records
print("\nCleaning up test DB rows...")
import sqlite3, os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH  = os.path.join(BASE_DIR, 'Database', 'my_tailor.db')
conn = sqlite3.connect(DB_PATH)
test_emails = [
    ('customer', 'customer', 'customer_id', 'http_test_cust@test.com'),
    ('tailor',   'tailor',   'tailor_id',   'http_test_tailor@test.com'),
    ('admin',    'admin',    'admin_id',    'http_test_admin@test.com'),
]
for role, tbl, pk, email in test_emails:
    row = conn.execute("SELECT login_id FROM login WHERE email=? AND role=?", (email, role)).fetchone()
    if row:
        conn.execute(f"DELETE FROM {tbl} WHERE {pk}=?", (row[0],))
        conn.execute("DELETE FROM login WHERE login_id=?", (row[0],))
conn.commit()
conn.close()
print("Done.\n")

# ─────────────────────────────────────────────────────────────────
total = 11
passed = total - len(errors)
print("=" * 60)
print(f"  HTTP INTEGRATION RESULTS: {passed}/{total} passed")
if errors:
    print(f"  FAILED: {errors}")
    sys.exit(1)
else:
    print("  ALL HTTP TESTS PASSED!")
print("=" * 60)
