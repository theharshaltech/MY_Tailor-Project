"""
Patch script: replaces the /Registration route in app.py with a corrected version.
Run once from the Backend directory: python fix_registration.py
"""
import re

APP_FILE = "app.py"

NEW_ROUTE = '''\
@app.route('/Registration', methods=['GET', 'POST'])
def registration():
    if request.method == 'GET':
        return render_template('Registration.html')

    role     = request.form.get('role', '').strip()
    email    = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    # ── Shared upfront validation ──────────────────────────────────────────
    if not email or not is_valid_email(email):
        flash('Invalid email format.', 'danger')
        return render_template('Registration.html')
    if len(password) < 6:
        flash('Password must be at least 6 characters long.', 'danger')
        return render_template('Registration.html')
    if role not in ['customer', 'tailor', 'admin']:
        flash('Please select a valid role (Customer, Tailor, or Admin).', 'danger')
        return render_template('Registration.html')

    db = get_db()

    # ── Duplicate-email check ───────────────────────────────────────────────
    existing = db.execute("SELECT email FROM login WHERE email=?", (email,)).fetchone()
    if existing:
        db.close()
        flash('This email is already registered. Please login instead.', 'warning')
        return render_template('Registration.html')

    # ── Role-specific field collection & validation BEFORE any DB insert ────
    if role == 'customer':
        name    = request.form.get('name', '').strip()
        phone   = request.form.get('customer_phone', '').strip()
        city    = request.form.get('city', '').strip()
        address = request.form.get('address', '').strip()
        gender  = request.form.get('gender', 'Male').strip()
        if not name:
            db.close()
            flash('Full name is required.', 'danger')
            return render_template('Registration.html')
        if not is_valid_phone(phone):
            db.close()
            flash('Please enter a valid 10-digit phone number.', 'danger')
            return render_template('Registration.html')

    elif role == 'tailor':
        tailor_name     = request.form.get('tailor_name', '').strip()
        shop_name       = request.form.get('shop_name', '').strip()
        phone           = request.form.get('tailor_phone', '').strip()
        location        = request.form.get('location', '').strip()
        speciality      = request.form.get('speciality', 'All Types').strip()
        gender_category = request.form.get('gender_category', 'Both').strip()
        experience      = request.form.get('experience', '0').strip() or '0'
        try:
            experience = int(experience)
        except ValueError:
            experience = 0
        if not tailor_name:
            db.close()
            flash('Owner/Tailor name is required.', 'danger')
            return render_template('Registration.html')
        if not shop_name:
            db.close()
            flash('Shop name is required.', 'danger')
            return render_template('Registration.html')
        if not is_valid_phone(phone):
            db.close()
            flash('Please enter a valid 10-digit phone number.', 'danger')
            return render_template('Registration.html')

    elif role == 'admin':
        admin_name = request.form.get('admin_name', '').strip()
        admin_code = request.form.get('admin_code', '').strip()
        if not admin_name:
            db.close()
            flash('Admin name is required.', 'danger')
            return render_template('Registration.html')
        if admin_code != 'TAILOR_ADMIN_2026':
            db.close()
            flash('Invalid Admin Secret Code.', 'danger')
            return render_template('Registration.html')

    # ── All validation passed — now write to DB ─────────────────────────────
    try:
        hashed_pass = generate_password_hash(password)
        cursor = db.execute(
            "INSERT INTO login(email, password, role) VALUES(?, ?, ?)",
            (email, hashed_pass, role)
        )
        login_id = cursor.lastrowid

        if role == 'customer':
            db.execute(
                """INSERT INTO customer(customer_id, name, email, password,
                   contact_num, city, address, gender) VALUES(?,?,?,?,?,?,?,?)""",
                (login_id, name, email, hashed_pass, phone, city, address, gender)
            )

        elif role == 'tailor':
            db.execute(
                """INSERT INTO tailor(tailor_id, name, shop_name, email, password,
                   contact_num, shop_address, speciality, experience, gender_category, status)
                   VALUES(?,?,?,?,?,?,?,?,?,?,'Active')""",
                (login_id, tailor_name, shop_name, email, hashed_pass,
                 phone, location, speciality, experience, gender_category)
            )

        elif role == 'admin':
            db.execute(
                "INSERT INTO admin(admin_id, name, email, password) VALUES(?,?,?,?)",
                (login_id, admin_name, email, hashed_pass)
            )

        db.commit()
        flash('Registration successful! You can now login with your credentials.', 'success')

    except Exception as e:
        db.rollback()
        flash(f'Registration failed: {str(e)}', 'danger')
        return render_template('Registration.html')

    finally:
        db.close()

    return redirect(url_for('login'))
'''

with open(APP_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Use regex to replace the entire registration function
pattern = r"@app\.route\('/Registration',\s*methods=\['GET',\s*'POST'\]\)\ndef registration\(\):.*?(?=\n\n\n# [═─]|\n\n@app\.route)"
match = re.search(pattern, content, re.DOTALL)
if not match:
    print("ERROR: Could not find the registration route. Trying fallback...")
    # Fallback: find by line markers
    start_marker = "@app.route('/Registration', methods=['GET', 'POST'])"
    end_marker = "    return redirect(url_for('login'))\n"
    
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("ERROR: Start marker not found!")
        exit(1)
    
    # Find the end — search for the next @app.route after registration
    next_route_idx = content.find('\n\n@app.route', start_idx + 10)
    next_comment_idx = content.find('\n\n\n# ', start_idx + 10)
    
    end_idx = min(
        next_route_idx if next_route_idx != -1 else len(content),
        next_comment_idx if next_comment_idx != -1 else len(content)
    )
    
    old_section = content[start_idx:end_idx]
    print("Found section (first 200 chars):", repr(old_section[:200]))
    new_content = content[:start_idx] + NEW_ROUTE + content[end_idx:]
else:
    old_section = match.group(0)
    print("Regex match found (first 200 chars):", repr(old_section[:200]))
    new_content = content[:match.start()] + NEW_ROUTE + content[match.end():]

with open(APP_FILE, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("SUCCESS: Registration route patched in app.py")
print(f"Old length: {len(old_section)} chars, New length: {len(NEW_ROUTE)} chars")
