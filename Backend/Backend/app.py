from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import re
from datetime import datetime
import io
from fpdf import FPDF
from flask import send_file
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = 'mytailor_secret_key_2025'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, 'Database', 'my_tailor.db')
FALLBACK_DB_PATH = os.path.join(BASE_DIR, 'Database', 'my_tailor new.db')


# ─────────────────────────────────────────
#  PDF REPORT HELPER
# ─────────────────────────────────────────
class TailorPDFReport(FPDF):
    def __init__(self, tailor_name, report_type="Monthly Report"):
        super().__init__()
        self.tailor_name = tailor_name
        self.report_type = report_type
        self.report_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def header(self):
        self.set_fill_color(26, 35, 64) # Navy
        self.rect(0, 0, 210, 40, 'F')
        self.set_y(10)
        self.set_font("Arial", 'B', 24)
        self.set_text_color(200, 151, 58) # Gold
        self.cell(0, 10, "MY TAILOR", ln=True, align='L')
        self.set_font("Arial", 'B', 12)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f"Shop: {self.tailor_name} | {self.report_type}", ln=True, align='L')
        
        # Date at top right
        self.set_y(10)
        self.set_font("Arial", '', 10)
        self.set_text_color(255, 255, 255)
        self.cell(0, 5, f"Generated: {self.report_date}", ln=True, align='R')
        
        # Reset cursor to below the navy bar (height 40)
        self.set_y(50)


    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()} | Performance Report | My Tailor", align='C')

    def section_title(self, title):
        self.set_font("Arial", 'B', 14)
        self.set_text_color(26, 35, 64)
        self.set_draw_color(200, 151, 58)
        self.cell(0, 10, title, ln=True)
        self.line(self.get_x(), self.get_y() - 2, self.get_x() + 190, self.get_y() - 2)
        self.ln(3)

    def create_table_header(self, columns, widths):
        self.set_font("Arial", 'B', 10)
        self.set_fill_color(240, 240, 240)
        self.set_text_color(26, 35, 64)
        for i in range(len(columns)):
            self.cell(widths[i], 8, columns[i], border=1, align='C', fill=True)
        self.ln()

# ─────────────────────────────────────────
#  DB HELPER
# ─────────────────────────────────────────
def get_db():
    last_error = None
    for path in (DB_PATH, FALLBACK_DB_PATH):
        if not os.path.exists(path):
            continue
        try:
            conn = sqlite3.connect(path, timeout=20)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("SELECT 1").fetchone()
            return conn
        except sqlite3.Error as exc:
            last_error = exc
    raise last_error or sqlite3.OperationalError("No database file available")

def setup_db(conn):
    """Perform all database migrations and initialization on a connection."""
    try:
        # Initialize new tables if they don't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_progress (
                progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                stage TEXT NOT NULL,
                image_path TEXT,
                notes TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                tailor_id INTEGER,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
                FOREIGN KEY (tailor_id) REFERENCES tailor(tailor_id)
            )
        """)
        try:
            conn.execute("ALTER TABLE notification ADD COLUMN tailor_id INTEGER")
        except sqlite3.OperationalError:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expense (
                expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tailor_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tailor_id) REFERENCES tailor(tailor_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alteration (
                alteration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                issue_description TEXT NOT NULL,
                media_path TEXT,
                status TEXT DEFAULT 'Pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        """)
        # Ensure each column exists in tailor table individually
        for col_sql in [
            "ALTER TABLE tailor ADD COLUMN status TEXT DEFAULT 'Active'",
            "ALTER TABLE tailor ADD COLUMN gender_category TEXT DEFAULT 'Both'",
        ]:
            try:
                conn.execute(col_sql)
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Migration for orders table - Payment Module
        for col_sql in [
            "ALTER TABLE orders ADD COLUMN completed_date DATE",
            "ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT 'Unpaid'",
            "ALTER TABLE orders ADD COLUMN payment_method TEXT",
        ]:
            try:
                conn.execute(col_sql)
            except sqlite3.OperationalError:
                pass

        # SEEDING: Add 15 sample tailors if the table is empty (Demo Requirement)
        tailor_count = conn.execute("SELECT COUNT(*) FROM tailor").fetchone()[0]
        if tailor_count < 2:  # Assuming less than 2 means empty or only admin-seeded
            sample_tailors = [
                ("Amit Patil", "Patil Gents Wear", "Kolhapur City", "Male"),
                ("Sneha Kulkarni", "Sneha Ladies Boutique", "Ichalkaranji", "Female"),
                ("Rahul Shinde", "Royal Tailors", "Jaysingpur", "Both"),
                ("Priya Deshmukh", "Priya Fashion", "Gadhinglaj", "Female"),
                ("Sanjay More", "Perfect Fit", "Kagal", "Male"),
                ("Deepa Jadhav", "Deepa Creations", "Shirol", "Female"),
                ("Vikram Powar", "Vikram Styles", "Hupari", "Male"),
                ("Anjali Mane", "Anjali Designer", "Radhanagari", "Female"),
                ("Rohan Gaikwad", "Modern Tailors", "Gaganbawda", "Both"),
                ("Meena Chavan", "Meena Garments", "Panhala", "Female"),
                ("Kiran Lohar", "Kiran Stitch", "Shahuwadi", "Male"),
                ("Pooja Naik", "Pooja Boutique", "Hatkanangale", "Female"),
                ("Sameer Sheikh", "Sameer Gents", "Vadgaon", "Male"),
                ("Tanvi Joshi", "Tanvi Silks", "Kurundwad", "Female"),
                ("Omkar Rane", "Omkar Fashion", "Nipani", "Both")
            ]
            for name, shop, loc, gen in sample_tailors:
                email = shop.lower().replace(' ', '') + "@example.com"
                pass_hash = generate_password_hash("password123")
                # Insert into login
                cur = conn.execute("INSERT INTO login(email, password, role) VALUES(?,?, 'tailor')", (email, pass_hash))
                tid = cur.lastrowid
                # Insert into tailor
                conn.execute("""
                    INSERT INTO tailor(tailor_id, name, shop_name, email, password, shop_address, speciality, gender_category, status)
                    VALUES(?,?,?,?,?,?,'All Types',?,'Active')
                """, (tid, name, shop, email, pass_hash, loc, gen))
        
        conn.commit()
    except Exception as e:
        print(f"Database setup error: {e}")
        conn.rollback()

def init_db():
    """Run database migrations and setup once at startup."""
    try:
        conn = get_db()
        setup_db(conn)
        conn.close()
    except Exception as e:
        print(f"Database initialization error: {e}")

# Call init_db at the end of the script before app.run()


def ensure_tailor_profile(db, email, default_name=None):
    tailor = db.execute(
        "SELECT * FROM tailor WHERE email=?", (email,)
    ).fetchone()
    if tailor:
        return tailor

    login_row = db.execute(
        "SELECT login_id, password FROM login WHERE email=? AND role='tailor'",
        (email,)
    ).fetchone()
    if not login_row:
        return None

    shop_name = (default_name or email.split('@')[0]).strip() or 'Tailor Shop'
    # Automatically seed the tailor table if they exist in login but not in tailor
    try:
        db.execute(
            """INSERT INTO tailor(tailor_id, name, shop_name, email, password, speciality, status) 
               VALUES(?,?,?,?,?,'All Types','Active')""",
            (login_row['login_id'], shop_name, shop_name, email, login_row['password'])
        )
        db.commit()
    except Exception:
        db.rollback()

    return db.execute("SELECT * FROM tailor WHERE email=?", (email,)).fetchone()


# ─────────────────────────────────────────
#  ROOT — redirect to login
# ─────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


# ─────────────────────────────────────────
#  LOGIN
# ─────────────────────────────────────────
@app.route('/Login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('Login.html')

    email    = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    role     = request.form.get('role', '').strip()

    db   = get_db()
    user = db.execute(
        "SELECT * FROM login WHERE email=? AND role=?",
        (email, role)
    ).fetchone()

    if not user or not check_password_hash(user['password'], password):
        db.close()
        flash("Invalid credentials. Please try again.", "danger")
        return render_template("Login.html")

    session['email'] = email
    session['role']  = role

    if role == 'customer':
        row = db.execute(
            "SELECT customer_id, name, gender FROM customer WHERE email=?", (email,)
        ).fetchone()
        session['user_id'] = row['customer_id']
        session['name']    = row['name']
        session['gender']  = row['gender']
        db.close()
        return redirect(url_for('customer_dashboard'))

    elif role == 'tailor':
        row = ensure_tailor_profile(db, email)
        if not row:
            db.close()
            flash("Tailor profile could not be loaded. Please contact admin.", "danger")
            return render_template("Login.html")
        
        session['user_id'] = row['tailor_id']
        session['name']    = row['shop_name']
        session['status']  = row['status']
        
        db.close()
        return redirect(url_for('tailor_dashboard'))

    elif role == 'admin':
        row = db.execute(
            "SELECT admin_id, name FROM admin WHERE email=?", (email,)
        ).fetchone()
        session['user_id'] = row['admin_id']
        session['name']    = row['name']
        db.close()
        return redirect(url_for('admin_dashboard'))

    db.close()
    return redirect(url_for('login'))



# ─────────────────────────────────────────
#  FORGOT PASSWORD
# ─────────────────────────────────────────
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('Forgot_Password.html')
    
    email = request.form.get('email', '').strip()
    role  = request.form.get('role', '').strip()
    
    db = get_db()
    user = db.execute(
        "SELECT * FROM login WHERE email=? AND role=?", (email, role)
    ).fetchone()
    db.close()
    
    if user:
        session['reset_email'] = email
        session['reset_role']  = role
        return redirect(url_for('reset_password'))
    else:
        flash('Email address not found for this role.', 'danger')
        return redirect(url_for('forgot_password'))

def is_valid_email(email):
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

def is_valid_phone(phone):
    return phone.isdigit() and len(phone) == 10

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session:
        flash('Please verify your email first.', 'warning')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'GET':
        return render_template('Reset_Password.html')
    
    new_pass = request.form.get('password', '').strip()
    email    = session['reset_email']
    role     = session['reset_role']
    
    if len(new_pass) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('reset_password'))
    
    db = get_db()
    try:
        hashed_pass = generate_password_hash(new_pass)
        # Update login table
        db.execute(
            "UPDATE login SET password=? WHERE email=? AND role=?",
            (hashed_pass, email, role)
        )
        
        # Update role-specific table
        if role == 'customer':
            db.execute("UPDATE customer SET password=? WHERE email=?", (hashed_pass, email))
        elif role == 'tailor':
            db.execute("UPDATE tailor SET password=? WHERE email=?", (hashed_pass, email))
        elif role == 'admin':
            db.execute("UPDATE admin SET password=? WHERE email=?", (hashed_pass, email))
        
        db.commit()
        session.pop('reset_email', None)
        session.pop('reset_role', None)
        flash('Password updated successfully! Please login.', 'success')
        return redirect(url_for('login'))
    except Exception as e:
        db.rollback()
        flash(f'Error updating password: {str(e)}', 'danger')
        return redirect(url_for('reset_password'))
    finally:
        db.close()


# ─────────────────────────────────────────
#  LOGOUT
# ─────────────────────────────────────────
@app.route('/Logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ─────────────────────────────────────────
#  TAILOR ACTIVATION (legacy redirect)
# ─────────────────────────────────────────
@app.route('/tailor/activation')
def tailor_activation():
    # Registration fees removed — redirect directly to dashboard
    return redirect(url_for('tailor_dashboard'))


# ─────────────────────────────────────────
#  REGISTRATION
# ─────────────────────────────────────────
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



# ═══════════════════════════════════════════
#  CUSTOMER ROUTES
# ═══════════════════════════════════════════

@app.route('/customer/dashboard')
def customer_dashboard():
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    db  = get_db()
    cid = session['user_id']
    
    total_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE customer_id=?", (cid,)).fetchone()['c'] or 0
    in_progress = db.execute("SELECT COUNT(*) AS c FROM orders WHERE customer_id=? AND status IN ('Pending', 'In Progress', 'Accepted')", (cid,)).fetchone()['c'] or 0
    completed = db.execute("SELECT COUNT(*) AS c FROM orders WHERE customer_id=? AND status='Completed'", (cid,)).fetchone()['c'] or 0
    cancelled = db.execute("SELECT COUNT(*) AS c FROM orders WHERE customer_id=? AND status IN ('Cancelled', 'Rejected')", (cid,)).fetchone()['c'] or 0

    orders = db.execute("""
        SELECT o.*, t.shop_name
        FROM orders o
        LEFT JOIN tailor t ON o.tailor_id = t.tailor_id
        WHERE o.customer_id=? 
        ORDER BY o.order_date DESC
    """, (cid,)).fetchall()

    progress_updates = db.execute("""
        SELECT * FROM order_progress 
        WHERE order_id IN (SELECT order_id FROM orders WHERE customer_id=?)
        ORDER BY timestamp ASC
    """, (cid,)).fetchall()
    
    alterations = db.execute("""
        SELECT * FROM alteration 
        WHERE order_id IN (SELECT order_id FROM orders WHERE customer_id=?)
        ORDER BY created_at DESC
    """, (cid,)).fetchall()
    
    progress_dict = {}
    for p in progress_updates:
        if p['order_id'] not in progress_dict:
            progress_dict[p['order_id']] = []
        progress_dict[p['order_id']].append(p)

    alt_dict = {}
    for a in alterations:
        if a['order_id'] not in alt_dict:
            alt_dict[a['order_id']] = []
        alt_dict[a['order_id']].append(a)

    meas = db.execute(
        "SELECT * FROM measurement WHERE customer_id=?", (cid,)
    ).fetchone()

    top_tailors = db.execute("SELECT * FROM tailor ORDER BY rating DESC LIMIT 3").fetchall()

    notifications = db.execute("SELECT * FROM notification WHERE customer_id=? AND is_read=0 ORDER BY created_at DESC", (cid,)).fetchall()

    db.close()
    
    return render_template('Customer_Dashboard.html', orders=orders,
                           measurement=meas, name=session.get('name'),
                           gender=session.get('gender', 'Male'),
                           total_orders=total_orders, in_progress=in_progress,
                           completed=completed, cancelled=cancelled,
                           top_tailors=top_tailors, notifications=notifications,
                           progress_dict=progress_dict, alt_dict=alt_dict)


@app.route('/customer/place-order', methods=['GET', 'POST'])
def place_order():
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    db = get_db()
    cid = session['user_id']

    # 1. Profile Validation
    cust = db.execute("SELECT contact_num, address FROM customer WHERE customer_id=?", (cid,)).fetchone()
    if not cust or not cust['contact_num'] or not cust['address']:
        flash('Please complete your profile (Phone & Address) in the Profile section before placing an order.', 'warning')
        db.close()
        return redirect(url_for('customer_profile'))

    # 2. Measurement Validation
    meas = db.execute("SELECT chest, waist FROM measurement WHERE customer_id=?", (cid,)).fetchone()
    if not meas or not meas['chest'] or not meas['waist']:
        flash('Please provide your basic measurements (Chest & Waist) in the Measurements section before placing an order.', 'warning')
        db.close()
        return redirect(url_for('measurements'))

    if request.method == 'POST':
        tailor_id     = request.form.get('tailor')
        gender        = request.form.get('gender')
        dress_type    = request.form.get('dress_type')
        fabric        = request.form.get('fabric')
        delivery_date = request.form.get('delivery_date')
        notes         = request.form.get('notes', '')
        order_date    = datetime.now().strftime('%Y-%m-%d')

        # 3. Date Validation
        if order_date and delivery_date:
            try:
                if datetime.strptime(delivery_date, '%Y-%m-%d') < datetime.strptime(order_date, '%Y-%m-%d'):
                    flash('Delivery date cannot be before order date.', 'danger')
                    db.close()
                    return redirect(url_for('place_order'))
            except ValueError:
                flash('Invalid date format.', 'danger')
                db.close()
                return redirect(url_for('place_order'))

        # 4. Fetch Service Info
        service = db.execute(
            "SELECT service_id, price FROM service WHERE service_name=?", (dress_type,)
        ).fetchone()
        
        if not service:
            flash(f'The selected dress type "{dress_type}" is currently not available for booking. Please contact support.', 'danger')
            db.close()
            return redirect(url_for('place_order'))

        service_id = service['service_id']
        amount     = service['price'] if service else 0

        # Handle Design Reference Image Upload
        design_ref_path = None
        design_file = request.files.get('design_ref')
        if design_file and design_file.filename:
            filename = secure_filename(design_file.filename)
            # Create uploads directory if it doesn't exist
            upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'design_refs')
            os.makedirs(upload_folder, exist_ok=True)
            
            # Add timestamp to filename to prevent overwriting
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            save_name = f"{timestamp}_{filename}"
            design_file.save(os.path.join(upload_folder, save_name))
            design_ref_path = f"uploads/design_refs/{save_name}"

        # 5. Save Order
        try:
            cursor = db.execute(
                """INSERT INTO orders(customer_id, tailor_id, service_id, gender,
                   dress_type, fabric, order_date, delivery_date, amount, status, notes, design_ref)
                   VALUES(?,?,?,?,?,?,?,?,?,'Pending',?,?)""",
                (cid, tailor_id, service_id, gender, dress_type, fabric,
                 order_date, delivery_date, amount, notes, design_ref_path)
            )
            order_id = cursor.lastrowid
            
            # Notify Tailor
            db.execute(
                "INSERT INTO notification(tailor_id, customer_id, message) VALUES(?, ?, ?)",
                (tailor_id, cid, f"New order received: #{order_id} for {dress_type} from {session.get('name')}")
            )
            
            db.commit()
            flash('Order placed successfully! You can track it in your order history.', 'success')
        except Exception as e:
            db.rollback()
            flash(f'Error placing order: {str(e)}', 'danger')
            db.close()
            return redirect(url_for('place_order'))

        db.close()
        return redirect(url_for('order_history'))

    tailors  = db.execute("SELECT * FROM tailor").fetchall()
    services = db.execute("SELECT * FROM service").fetchall()
    db.close()
    return render_template('Place_order.html', tailors=tailors,
                           services=services, name=session.get('name'),
                           gender=session.get('gender', 'Male'))


@app.route('/customer/order-history')
def order_history():
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    db = get_db()
    cid = session['user_id']
    orders = db.execute("""
        SELECT o.*, t.shop_name, s.service_name
        FROM orders o
        LEFT JOIN tailor  t ON o.tailor_id  = t.tailor_id
        LEFT JOIN service s ON o.service_id = s.service_id
        WHERE o.customer_id = ?
        ORDER BY o.order_date DESC
    """, (cid,)).fetchall()

    total_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE customer_id=?", (cid,)).fetchone()['c'] or 0
    pending = db.execute("SELECT COUNT(*) AS c FROM orders WHERE customer_id=? AND status='Pending'", (cid,)).fetchone()['c'] or 0
    in_progress = db.execute("SELECT COUNT(*) AS c FROM orders WHERE customer_id=? AND status IN ('In Progress', 'Accepted')", (cid,)).fetchone()['c'] or 0
    completed = db.execute("SELECT COUNT(*) AS c FROM orders WHERE customer_id=? AND status='Completed'", (cid,)).fetchone()['c'] or 0

    progress_updates = db.execute("""
        SELECT * FROM order_progress 
        WHERE order_id IN (SELECT order_id FROM orders WHERE customer_id=?)
        ORDER BY timestamp ASC
    """, (cid,)).fetchall()
    
    progress_dict = {}
    for p in progress_updates:
        if p['order_id'] not in progress_dict:
            progress_dict[p['order_id']] = []
        progress_dict[p['order_id']].append(p)

    db.close()
    return render_template('Order_History.html', orders=orders,
                           name=session.get('name'),
                           total_orders=total_orders, pending=pending,
                           in_progress=in_progress, completed=completed,
                           progress_dict=progress_dict)


@app.route('/customer/order/cancel/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    db = get_db()
    cid = session['user_id']
    
    # Notify tailor
    order = db.execute("SELECT tailor_id FROM orders WHERE order_id=? AND customer_id=?", (order_id, cid)).fetchone()
    if order:
        db.execute(
            "UPDATE orders SET status='Cancelled' WHERE order_id=? AND customer_id=? AND status='Pending'",
            (order_id, cid)
        )
        if db.total_changes > 0:
            db.execute(
                "INSERT INTO notification(tailor_id, customer_id, message) VALUES(?, ?, ?)",
                (order['tailor_id'], cid, f"Order #{order_id} has been cancelled by the customer.")
            )
        db.commit()
    db.close()
    flash('Order cancelled.', 'info')
    return redirect(url_for('order_history'))


@app.route('/customer/order/edit/<int:order_id>', methods=['GET', 'POST'])
def edit_order(order_id):
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    db = get_db()
    cid = session['user_id']
    
    order = db.execute("SELECT * FROM orders WHERE order_id=? AND customer_id=?", (order_id, cid)).fetchone()
    if not order:
        flash('Order not found.', 'danger')
        db.close()
        return redirect(url_for('order_history'))
        
    if order['status'] not in ['Pending', 'Not Yet Accepted']:
        flash('Order is already in process. Please contact the tailor for changes.', 'danger')
        db.close()
        return redirect(url_for('order_history'))

    if request.method == 'POST':
        dress_type    = request.form.get('dress_type')
        fabric        = request.form.get('fabric')
        delivery_date = request.form.get('delivery_date')
        notes         = request.form.get('notes', '')
        
        # Validation for date
        if order['order_date'] and delivery_date:
            try:
                if datetime.strptime(delivery_date, '%Y-%m-%d') < datetime.strptime(order['order_date'], '%Y-%m-%d'):
                    flash('Delivery date cannot be before order date.', 'danger')
                    db.close()
                    return redirect(url_for('edit_order', order_id=order_id))
            except ValueError:
                flash('Invalid date format.', 'danger')
                db.close()
                return redirect(url_for('edit_order', order_id=order_id))
                
        # Price update based on new dress type
        service = db.execute(
            "SELECT service_id, price FROM service WHERE service_name=?", (dress_type,)
        ).fetchone()
        
        amount = service['price'] if service else 0
        service_id = order['service_id']
        if service:
            service_id = service['service_id']

        # Handle Design Reference Image Upload
        design_ref_path = order['design_ref']
        design_file = request.files.get('design_ref')
        if design_file and design_file.filename:
            filename = secure_filename(design_file.filename)
            upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'design_refs')
            os.makedirs(upload_folder, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            save_name = f"{timestamp}_{filename}"
            design_file.save(os.path.join(upload_folder, save_name))
            design_ref_path = f"uploads/design_refs/{save_name}"

        try:
            db.execute(
                """UPDATE orders SET dress_type=?, fabric=?, delivery_date=?, notes=?, service_id=?, amount=?, design_ref=?, notes=notes||'\n(Updated)' 
                   WHERE order_id=? AND customer_id=? AND status IN ('Pending', 'Not Yet Accepted')""",
                (dress_type, fabric, delivery_date, notes, service_id, amount, design_ref_path, order_id, cid)
            )
            
            # Notify Tailor about the update
            db.execute(
                "INSERT INTO notification(tailor_id, customer_id, message) VALUES(?, ?, ?)",
                (order['tailor_id'], cid, f"Order #{order_id} has been updated by the customer.")
            )
            
            db.commit()
            flash('Order updated successfully!', 'success')
        except Exception as e:
            db.rollback()
            flash(f'Error updating order: {str(e)}', 'danger')
            db.close()
            return redirect(url_for('edit_order', order_id=order_id))

        db.close()
        return redirect(url_for('order_history'))

    db.close()
    return render_template('Edit_Order.html', order=order, name=session.get('name'))

@app.route('/customer/order/payment/<int:order_id>', methods=['POST'])
def process_payment(order_id):
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    
    method = request.form.get('payment_method')
    db = get_db()
    cid = session['user_id']
    
    order = db.execute("SELECT * FROM orders WHERE order_id=? AND customer_id=?", (order_id, cid)).fetchone()
    if not order or order['status'] != 'Completed':
        db.close()
        flash('Invalid order or status.', 'danger')
        return redirect(url_for('order_history'))
    
    if method == 'Online':
        # Simulate payment processing
        db.execute(
            "UPDATE orders SET status='Paid', payment_status='Paid', payment_method='Online' WHERE order_id=?",
            (order_id,)
        )
        # Notify Tailor
        db.execute(
            "INSERT INTO notification(customer_id, tailor_id, message) VALUES(?, ?, ?)",
            (cid, order['tailor_id'], f"Payment received for Order #{order_id} (Online).")
        )
        flash('Payment processed successfully! Your receipt is ready.', 'success')
    elif method == 'Offline':
        db.execute(
            "UPDATE orders SET payment_status='Pay at Shop', payment_method='Offline' WHERE order_id=?",
            (order_id,)
        )
        flash('Please visit the shop to pay. Details are displayed below.', 'info')
    
    db.commit()
    db.close()
    return redirect(url_for('order_history'))

@app.route('/customer/order/receipt/<int:order_id>')
def download_receipt(order_id):
    if session.get('role') not in ['customer', 'tailor', 'admin']:
        return redirect(url_for('login'))
    
    db = get_db()
    order = db.execute("""
        SELECT o.*, c.name AS customer_name, t.shop_name AS tailor_name, t.shop_address, t.contact_num AS tailor_phone,
               s.service_name
        FROM orders o
        JOIN customer c ON o.customer_id = c.customer_id
        JOIN tailor t ON o.tailor_id = t.tailor_id
        LEFT JOIN service s ON o.service_id = s.service_id
        WHERE o.order_id = ?
    """, (order_id,)).fetchone()
    
    if not order or order['payment_status'] != 'Paid':
        db.close()
        flash('Receipt not available.', 'danger')
        return redirect(url_for('order_history'))
    
    db.close()

    # Generate PDF Receipt
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_fill_color(26, 35, 64) # Navy
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_font("Arial", 'B', 24)
    pdf.set_text_color(200, 151, 58) # Gold
    pdf.cell(0, 15, "MY TAILOR - RECEIPT", ln=True, align='C')
    
    # Move past the navy bar (height 40)
    pdf.set_y(45)

    
    # Receipt Info
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(100, 10, f"Order ID: #{order['order_id']}")
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='R')
    pdf.ln(5)
    
    # Customer & Tailor Details
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(95, 8, "Customer Details", border='B')
    pdf.cell(10, 8, "")
    pdf.cell(95, 8, "Tailor Shop Details", border='B', ln=True)
    
    pdf.set_font("Arial", '', 10)
    pdf.cell(95, 8, f"Name: {order['customer_name']}")
    pdf.cell(10, 8, "")
    pdf.cell(95, 8, f"Shop: {order['tailor_name']}", ln=True)
    
    pdf.cell(95, 8, "")
    pdf.cell(10, 8, "")
    pdf.cell(95, 8, f"Address: {order['shop_address']}", ln=True)
    
    pdf.cell(95, 8, "")
    pdf.cell(10, 8, "")
    pdf.cell(95, 8, f"Contact: {order['tailor_phone']}", ln=True)
    pdf.ln(10)
    
    # Order Details Table
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(110, 10, "Service / Description", border=1, fill=True)
    pdf.cell(40, 10, "Payment Method", border=1, fill=True, align='C')
    pdf.cell(40, 10, "Amount (INR)", border=1, fill=True, align='C', ln=True)
    
    pdf.set_font("Arial", '', 10)
    pdf.cell(110, 10, f"{order['service_name'] or order['dress_type']} ({order['fabric']})", border=1)
    pdf.cell(40, 10, f"{order['payment_method']}", border=1, align='C')
    pdf.cell(40, 10, f"{order['amount']:.2f}", border=1, align='R', ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(150, 10, "TOTAL PAID", align='R')
    pdf.set_text_color(46, 125, 50) # Success Green
    pdf.cell(40, 10, f"INR {order['amount']:.2f}", align='R', ln=True)
    
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 10, "This is a computer-generated receipt. No signature required.", ln=True, align='C')
    pdf.cell(0, 10, "Thank you for using My Tailor!", ln=True, align='C')

    output = io.BytesIO()
    pdf_out = pdf.output(dest='S')
    if isinstance(pdf_out, str):
        output.write(pdf_out.encode('latin1'))
    else:
        output.write(pdf_out)
    output.seek(0)
    
    return send_file(output, download_name=f"Receipt_Order_{order_id}.pdf", as_attachment=True)

@app.route('/customer/order/rate/<int:order_id>', methods=['POST'])
def rate_order(order_id):
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    flash('Thank you! Your rating has been submitted.', 'success')
    return redirect(url_for('order_history'))

@app.route('/customer/measurements', methods=['GET', 'POST'])
def measurements():
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    db  = get_db()
    cid = session['user_id']

    if request.method == 'POST':
        fields = ['chest', 'waist', 'length', 'shoulder', 'hip', 'sleeve', 'neck', 'inseam']
        vals   = [request.form.get(f) for f in fields]
        
        # Validation
        for v in vals:
            if v and (float(v) < 1 or float(v) > 100):
                flash('Measurement values must be between 1 and 100 inches.', 'danger')
                return redirect(url_for('measurements'))

        exists = db.execute(
            "SELECT measurement_id FROM measurement WHERE customer_id=?", (cid,)
        ).fetchone()
        if exists:
            db.execute(
                """UPDATE measurement
                   SET chest=?, waist=?, length=?, shoulder=?,
                       hip=?, sleeve=?, neck=?, inseam=?,
                       updated_at=DATETIME('now')
                   WHERE customer_id=?""",
                (*vals, cid)
            )
        else:
            db.execute(
                """INSERT INTO measurement
                   (customer_id, chest, waist, length, shoulder, hip, sleeve, neck, inseam)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (cid, *vals)
            )
        db.commit()
        flash('Measurements saved!', 'success')
        db.close()
        return redirect(url_for('measurements'))

    meas = db.execute(
        "SELECT * FROM measurement WHERE customer_id=?", (cid,)
    ).fetchone()
    customer = db.execute(
        "SELECT gender FROM customer WHERE customer_id=?", (cid,)
    ).fetchone()
    db.close()
    return render_template('Measurements.html', meas=meas, name=session.get('name'), customer=customer)


@app.route('/customer/find-tailor')
def find_tailor():
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    db      = get_db()
    # Only show active tailors
    tailors = db.execute("SELECT * FROM tailor WHERE status='Active' ORDER BY rating DESC").fetchall()
    db.close()
    return render_template('Find_Tailor.html', tailors=tailors, name=session.get('name'))


@app.route('/customer/profile', methods=['GET', 'POST'])
def customer_profile():
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    db  = get_db()
    cid = session['user_id']

    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        phone   = request.form.get('phone', '').strip()
        city    = request.form.get('city', '').strip()
        address = request.form.get('address', '').strip()
        gender  = request.form.get('gender', 'Male')

        if phone and not is_valid_phone(phone):
            flash('Invalid phone number format (10 digits required).', 'danger')
            return redirect(url_for('customer_profile'))

        db.execute(
            "UPDATE customer SET name=?, contact_num=?, city=?, address=?, gender=? WHERE customer_id=?",
            (name, phone, city, address, gender, cid)
        )
        db.commit()
        session['name']   = name
        session['gender'] = gender
        flash('Profile updated!', 'success')

    customer = db.execute(
        "SELECT * FROM customer WHERE customer_id=?", (cid,)
    ).fetchone()
    db.close()
    return render_template('Profile.html', customer=customer, name=session.get('name'))


@app.route('/customer/change-password', methods=['POST'])
def change_password():
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    db       = get_db()
    cid      = session['user_id']
    current  = request.form.get('current_password', '')
    new_pass = request.form.get('new_password', '')

    if len(new_pass) < 6:
        flash('New password must be at least 6 characters.', 'danger')
        return redirect(url_for('customer_profile'))

    row      = db.execute(
        "SELECT password FROM customer WHERE customer_id=?", (cid,)
    ).fetchone()

    if not check_password_hash(row['password'], current):
        flash('Current password is incorrect.', 'danger')
    else:
        hashed_new = generate_password_hash(new_pass)
        db.execute("UPDATE customer SET password=? WHERE customer_id=?", (hashed_new, cid))
        db.execute("UPDATE login    SET password=? WHERE email=?",        (hashed_new, session['email']))
        db.commit()
        flash('Password updated successfully!', 'success')

    db.close()
    return redirect(url_for('customer_profile'))

@app.route('/customer/notification/read/<int:notification_id>', methods=['POST'])
def read_notification(notification_id):
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
        
    db = get_db()
    db.execute(
        "UPDATE notification SET is_read=1 WHERE notification_id=? AND customer_id=?",
        (notification_id, session['user_id'])
    )
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('customer_dashboard'))


@app.route('/tailor/notification/read/<int:notification_id>', methods=['POST'])
def tailor_read_notification(notification_id):
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
        
    db = get_db()
    db.execute(
        "UPDATE notification SET is_read=1 WHERE notification_id=? AND tailor_id=?",
        (notification_id, session['user_id'])
    )
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('tailor_dashboard'))


@app.route('/customer/style-recommendation', methods=['GET', 'POST'])
def style_recommendation():
    if session.get('role') != 'customer':
        return redirect(url_for('login'))
    
    db = get_db()
    cid = session['user_id']
    
    if request.method == 'POST':
        skin_tone = request.form.get('skin_tone')
        undertone = request.form.get('undertone')
        db.execute("UPDATE customer SET skin_tone=?, undertone=? WHERE customer_id=?", (skin_tone, undertone, cid))
        db.commit()
        flash('Preferences updated!', 'success')
        return redirect(url_for('style_recommendation'))
    
    customer = db.execute("SELECT skin_tone, undertone FROM customer WHERE customer_id=?", (cid,)).fetchone()
    
    # Recommendation Logic
    recommendations = None
    if customer['skin_tone'] and customer['undertone']:
        tone_map = {
            ('Fair', 'Cool'): {
                'colors': ['Soft Pink', 'Sky Blue', 'Lavender', 'Silver'],
                'fabrics': ['Silk', 'Chiffon'],
                'patterns': ['Delicate Florals']
            },
            ('Fair', 'Warm'): {
                'colors': ['Peach', 'Mint Green', 'Ivory', 'Gold'],
                'fabrics': ['Linen', 'Light Cotton'],
                'patterns': ['Fine Stripes']
            },
            ('Fair', 'Neutral'): {
                'colors': ['Dusty Rose', 'Sage Green', 'Champagne'],
                'fabrics': ['Suede', 'Soft Wool'],
                'patterns': ['Polka Dots']
            },
            ('Medium', 'Cool'): {
                'colors': ['Emerald Green', 'Ruby Red', 'Royal Blue'],
                'fabrics': ['Velvet', 'Satin'],
                'patterns': ['Geometric']
            },
            ('Medium', 'Warm'): {
                'colors': ['Mustard', 'Terracotta', 'Olive Green', 'Gold'],
                'fabrics': ['Brocade', 'Raw Silk'],
                'patterns': ['Paisley']
            },
            ('Medium', 'Neutral'): {
                'colors': ['Plum', 'Teal', 'Charcoal', 'Bronze'],
                'fabrics': ['Crepe', 'Twill'],
                'patterns': ['Houndstooth']
            },
            ('Dark', 'Cool'): {
                'colors': ['Bright Fuchsia', 'Electric Blue', 'Violet', 'Silver'],
                'fabrics': ['Organza', 'Metallic'],
                'patterns': ['Bold Abstract']
            },
            ('Dark', 'Warm'): {
                'colors': ['Orange', 'Sunshine Yellow', 'Deep Red', 'Copper'],
                'fabrics': ['Heavy Silk', 'Jacquard'],
                'patterns': ['Tribal Prints']
            },
            ('Dark', 'Neutral'): {
                'colors': ['White', 'Cobalt Blue', 'Forest Green', 'Pewter'],
                'fabrics': ['Georgette', 'Denim'],
                'patterns': ['Checkered']
            }
        }
        recommendations = tone_map.get((customer['skin_tone'], customer['undertone']))
    
    # Past Preferences
    past_orders = db.execute("SELECT dress_type, fabric, COUNT(*) as count FROM orders WHERE customer_id=? GROUP BY dress_type, fabric ORDER BY count DESC LIMIT 3", (cid,)).fetchall()
    
    db.close()
    return render_template('Style_Recommendation.html', customer=customer, recommendations=recommendations, past_orders=past_orders, name=session.get('name'))


# ═══════════════════════════════════════════
#  TAILOR ROUTES
# ═══════════════════════════════════════════

@app.route('/tailor/dashboard')
def tailor_dashboard():
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    db  = get_db()
    tailor = ensure_tailor_profile(db, session.get('email'), session.get('name'))
    if not tailor:
        db.close()
        flash('Tailor profile not found. Please login again.', 'danger')
        return redirect(url_for('login'))
    tid = tailor['tailor_id']
    session['user_id'] = tid
    session['name'] = tailor['shop_name']
    
    if tailor['status'] != 'Active':
        db.close()
        flash('Your tailor account is currently inactive. Please contact admin.', 'warning')
        return redirect(url_for('login'))
    
    # Calculate Tailor Stats
    today_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND DATE(order_date) = DATE('now')", (tid,)).fetchone()['c'] or 0
    pending_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status IN ('Pending', 'In Progress', 'Accepted')", (tid,)).fetchone()['c'] or 0
    completed_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status='Completed'", (tid,)).fetchone()['c'] or 0
    customers_count = db.execute("SELECT COUNT(DISTINCT customer_id) AS c FROM orders WHERE tailor_id=?", (tid,)).fetchone()['c'] or 0

    orders = db.execute("""
        SELECT o.*, c.name AS customer_name, s.service_name
        FROM orders o
        LEFT JOIN customer c ON o.customer_id = c.customer_id
        LEFT JOIN service  s ON o.service_id  = s.service_id
        WHERE o.tailor_id = ?
        ORDER BY o.order_date DESC
    """, (tid,)).fetchall()

    # Financial metrics removed for operational focus
    earnings = {'total': 0, 'today': 0, 'week': 0}

    # Get measurements of customers who ordered from this tailor
    recent_measurements = db.execute("""
        SELECT DISTINCT c.name, m.*
        FROM measurement m
        JOIN customer c ON m.customer_id = c.customer_id
        JOIN orders o ON c.customer_id = o.customer_id
        WHERE o.tailor_id = ?
        LIMIT 5
    """, (tid,)).fetchall()

    top_customers = db.execute("""
        SELECT c.name, COUNT(o.order_id) as order_count
        FROM customer c
        JOIN orders o ON c.customer_id = o.customer_id
        WHERE o.tailor_id = ?
        GROUP BY c.customer_id
        ORDER BY order_count DESC
        LIMIT 3
    """, (tid,)).fetchall()

    notifications = db.execute("SELECT * FROM notification WHERE tailor_id=? AND is_read=0 ORDER BY created_at DESC", (tid,)).fetchall()

    db.close()
    return render_template('Tailor_Dashboard.html', orders=orders,
                           tailor=tailor,
                           name=session.get('name'), 
                           recent_measurements=recent_measurements,
                           top_customers=top_customers,
                           notifications=notifications,
                           today_orders=today_orders, pending_orders=pending_orders, 
                           completed_orders=completed_orders, customers_count=customers_count)


@app.route('/tailor/monthly-report')
def tailor_monthly_report():
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    
    db = get_db()
    tid = session['user_id']
    
    # Operational Stats
    today_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND DATE(order_date) = DATE('now')", (tid,)).fetchone()['c'] or 0
    pending_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status IN ('Pending', 'In Progress', 'Accepted')", (tid,)).fetchone()['c'] or 0
    completed_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status='Completed'", (tid,)).fetchone()['c'] or 0
    dispatched_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status='Dispatched'", (tid,)).fetchone()['c'] or 0
    customers_count = db.execute("SELECT COUNT(DISTINCT customer_id) AS c FROM orders WHERE tailor_id=?", (tid,)).fetchone()['c'] or 0
    
    # Financial Stats
    total_income = db.execute("SELECT SUM(amount) FROM orders WHERE tailor_id=?", (tid,)).fetchone()[0] or 0
    total_expenses = db.execute("SELECT SUM(amount) FROM expense WHERE tailor_id=?", (tid,)).fetchone()[0] or 0
    net_revenue = total_income - total_expenses

    db.close()
    return render_template('Tailor_Monthly_Report.html', 
                           name=session.get('name'), 
                           today_orders=today_orders, 
                           pending_orders=pending_orders, 
                           completed_orders=completed_orders, 
                           dispatched_orders=dispatched_orders,
                           customers_count=customers_count,
                           total_income=total_income,
                           total_expenses=total_expenses,
                           net_revenue=net_revenue)

@app.route('/tailor/detailed-report')
def tailor_detailed_report():
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    
    db = get_db()
    tid = session['user_id']
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    date_filter = ""
    params = [tid]
    if start_date:
        date_filter += " AND order_date >= ?"
        params.append(start_date)
    if end_date:
        date_filter += " AND order_date <= ?"
        params.append(end_date)

    # Unified Query for Daily Metrics
    report_data = db.execute(f"""
        SELECT 
            d.date,
            SUM(d.total_orders) AS total_orders,
            SUM(d.completed_orders) AS completed_orders,
            SUM(d.pending_orders) AS pending_orders,
            SUM(d.dispatched_orders) AS dispatched_orders,
            SUM(d.total_customers) AS total_customers,
            SUM(d.income) AS income,
            SUM(d.expenses) AS expenses,
            SUM(d.income - d.expenses) AS revenue
        FROM (
            SELECT 
                order_date AS date,
                COUNT(*) AS total_orders,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed_orders,
                SUM(CASE WHEN status IN ('Pending', 'In Progress', 'Accepted') THEN 1 ELSE 0 END) AS pending_orders,
                SUM(CASE WHEN status = 'Dispatched' THEN 1 ELSE 0 END) AS dispatched_orders,
                COUNT(DISTINCT customer_id) AS total_customers,
                SUM(amount) AS income,
                0 AS expenses
            FROM orders
            WHERE tailor_id = ? {date_filter}
            GROUP BY order_date
            
            UNION ALL
            
            SELECT 
                DATE(date) AS date,
                0 AS total_orders,
                0 AS completed_orders,
                0 AS pending_orders,
                0 AS dispatched_orders,
                0 AS total_customers,
                0 AS income,
                SUM(amount) AS expenses
            FROM expense
            WHERE tailor_id = ? {date_filter.replace('order_date', 'date')}
            GROUP BY DATE(date)
        ) d
        GROUP BY d.date
        ORDER BY d.date DESC
    """, params + params).fetchall()

    # Calculate Totals
    totals = {
        'total_orders': sum(d['total_orders'] for d in report_data),
        'completed_orders': sum(d['completed_orders'] for d in report_data),
        'pending_orders': sum(d['pending_orders'] for d in report_data),
        'dispatched_orders': sum(d['dispatched_orders'] for d in report_data),
        'total_customers': sum(d['total_customers'] for d in report_data),
        'income': sum(d['income'] for d in report_data),
        'expenses': sum(d['expenses'] for d in report_data),
        'revenue': sum(d['revenue'] for d in report_data)
    }

    db.close()
    return render_template('Tailor_Detailed_Report.html', 
                           name=session.get('name'),
                           report_data=report_data, 
                           totals=totals,
                           start_date=start_date, 
                           end_date=end_date)

@app.route('/tailor/reports')
def tailor_reports():
    return redirect(url_for('tailor_monthly_report'))


@app.route('/tailor/monthly-report/pdf')
def tailor_monthly_report_pdf():
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    db  = get_db()
    tid = session['user_id']
    
    today_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND DATE(order_date) = DATE('now')", (tid,)).fetchone()['c'] or 0
    pending_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status IN ('Pending', 'In Progress', 'Accepted')", (tid,)).fetchone()['c'] or 0
    completed_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status='Completed'", (tid,)).fetchone()['c'] or 0
    customers_count = db.execute("SELECT COUNT(DISTINCT customer_id) AS c FROM orders WHERE tailor_id=?", (tid,)).fetchone()['c'] or 0
    dispatched_orders = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status='Dispatched'", (tid,)).fetchone()['c'] or 0
    
    # Financial metrics
    total_income = db.execute("SELECT SUM(amount) FROM orders WHERE tailor_id=?", (tid,)).fetchone()[0] or 0
    total_expenses = db.execute("SELECT SUM(amount) FROM expense WHERE tailor_id=?", (tid,)).fetchone()[0] or 0
    net_revenue = total_income - total_expenses
    
    total_orders = today_orders + pending_orders + completed_orders + dispatched_orders
    db.close()

    pdf = TailorPDFReport(session.get('name', 'Tailor Shop'), "Monthly Operational Report")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Section 1: Order Performance
    pdf.section_title("Order Performance Summary")
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Total Volume: {total_orders} Orders", ln=True)
    pdf.cell(0, 8, f"Completed: {completed_orders}", ln=True)
    pdf.cell(0, 8, f"Pending: {pending_orders}", ln=True)
    pdf.cell(0, 8, f"Dispatched: {dispatched_orders}", ln=True)
    pdf.ln(5)
    
    # Section 2: Financial Summary
    pdf.section_title("Financial Performance")
    fin_widths = [100, 80]
    pdf.create_table_header(["Category", "Amount (INR)"], fin_widths)
    pdf.set_font("Arial", '', 11)
    pdf.cell(fin_widths[0], 8, "Total Income", border=1)
    pdf.cell(fin_widths[1], 8, f"{total_income:,.2f}", border=1, align='R')
    pdf.ln()
    pdf.cell(fin_widths[0], 8, "Total Expenses", border=1)
    pdf.cell(fin_widths[1], 8, f"{total_expenses:,.2f}", border=1, align='R')
    pdf.ln()
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(fin_widths[0], 8, "Net Revenue", border=1)
    pdf.cell(fin_widths[1], 8, f"{net_revenue:,.2f}", border=1, align='R')
    pdf.ln(10)
    
    # Section 3: Insights
    pdf.section_title("Business Insights")
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 8, f"This month, the shop engaged with {customers_count} unique customers. "
                         f"The operational focus remains on fulfillment and quality management.")
    
    output = io.BytesIO()
    pdf_out = pdf.output(dest='S')
    if isinstance(pdf_out, str):
        output.write(pdf_out.encode('latin1'))
    else:
        output.write(pdf_out)
    output.seek(0)
    
    return send_file(output, download_name=f"Monthly_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf", as_attachment=True)



@app.route('/tailor/detailed-report/pdf')
def tailor_detailed_report_pdf():
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    db = get_db()
    tid = session['user_id']
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Re-use logic from detailed report
    date_filter = ""
    params = [tid]
    if start_date:
        date_filter += " AND order_date >= ?"
        params.append(start_date)
    if end_date:
        date_filter += " AND order_date <= ?"
        params.append(end_date)

    report_data = db.execute(f"""
        SELECT 
            d.date,
            SUM(d.total_orders) AS total_orders,
            SUM(d.completed_orders) AS completed_orders,
            SUM(d.pending_orders) AS pending_orders,
            SUM(d.dispatched_orders) AS dispatched_orders,
            SUM(d.total_customers) AS total_customers,
            SUM(d.income) AS income,
            SUM(d.expenses) AS expenses,
            SUM(d.income - d.expenses) AS revenue
        FROM (
            SELECT order_date AS date, COUNT(*) AS total_orders,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed_orders,
                SUM(CASE WHEN status IN ('Pending', 'In Progress', 'Accepted') THEN 1 ELSE 0 END) AS pending_orders,
                SUM(CASE WHEN status = 'Dispatched' THEN 1 ELSE 0 END) AS dispatched_orders,
                COUNT(DISTINCT customer_id) AS total_customers,
                SUM(amount) AS income, 0 AS expenses
            FROM orders WHERE tailor_id = ? {date_filter} GROUP BY order_date
            UNION ALL
            SELECT DATE(date) AS date, 0, 0, 0, 0, 0, 0, SUM(amount) AS expenses
            FROM expense WHERE tailor_id = ? {date_filter.replace('order_date', 'date')} GROUP BY DATE(date)
        ) d GROUP BY d.date ORDER BY d.date DESC
    """, params + params).fetchall()

    totals = {
        'orders': sum(d['total_orders'] for d in report_data),
        'income': sum(d['income'] for d in report_data),
        'expenses': sum(d['expenses'] for d in report_data),
        'revenue': sum(d['revenue'] for d in report_data)
    }
    db.close()

    pdf = TailorPDFReport(session.get('name', 'Tailor Shop'), "Detailed Performance Log")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Summary Section
    pdf.section_title("Summary of Selected Period")
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Total Orders: {totals['orders']}", ln=True)
    pdf.cell(0, 8, f"Total Income: INR {totals['income']:,.2f}", ln=True)
    pdf.cell(0, 8, f"Total Expenses: INR {totals['expenses']:,.2f}", ln=True)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, f"Net Revenue: INR {totals['revenue']:,.2f}", ln=True)
    pdf.ln(10)

    # Detailed Table
    pdf.section_title("Daily Activity Details")
    # Date, Orders, Comp, Pend, Cust, Inc, Exp
    col_widths = [25, 20, 20, 20, 25, 25, 25, 30]
    pdf.create_table_header(["Date", "Orders", "Comp", "Pend", "Cust", "Income", "Exp", "Revenue"], col_widths)
    pdf.set_font("Arial", '', 8)
    for row in report_data:
        pdf.cell(col_widths[0], 7, str(row['date']), border=1)
        pdf.cell(col_widths[1], 7, str(row['total_orders']), border=1, align='C')
        pdf.cell(col_widths[2], 7, str(row['completed_orders']), border=1, align='C')
        pdf.cell(col_widths[3], 7, str(row['pending_orders']), border=1, align='C')
        pdf.cell(col_widths[4], 7, str(row['total_customers']), border=1, align='C')
        pdf.cell(col_widths[5], 7, f"{row['income']:,.0f}", border=1, align='R')
        pdf.cell(col_widths[6], 7, f"{row['expenses']:,.0f}", border=1, align='R')
        pdf.cell(col_widths[7], 7, f"{row['revenue']:,.0f}", border=1, align='R')
        pdf.ln()

    output = io.BytesIO()
    pdf_out = pdf.output(dest='S')
    if isinstance(pdf_out, str):
        output.write(pdf_out.encode('latin1'))
    else:
        output.write(pdf_out)
    output.seek(0)
    return send_file(output, download_name=f"Detailed_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf", as_attachment=True)



@app.route('/tailor/order/<int:order_id>')
def tailor_order_detail(order_id):
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    db = get_db()
    tid = session['user_id']
    
    order = db.execute("""
        SELECT o.*, c.name AS customer_name, c.email AS customer_email, c.contact_num AS customer_phone,
               c.address AS customer_address, c.city AS customer_city,
               s.service_name
        FROM orders o
        LEFT JOIN customer c ON o.customer_id = c.customer_id
        LEFT JOIN service  s ON o.service_id  = s.service_id
        WHERE o.order_id = ? AND o.tailor_id = ?
    """, (order_id, tid)).fetchone()
    
    if not order:
        db.close()
        flash("Order not found.", "danger")
        return redirect(url_for('tailor_orders'))
    
    progress = db.execute("""
        SELECT * FROM order_progress 
        WHERE order_id = ? 
        ORDER BY timestamp DESC
    """, (order_id,)).fetchall()
    
    measurements = db.execute("""
        SELECT * FROM measurement 
        WHERE customer_id = ?
    """, (order['customer_id'],)).fetchone()

    alterations = db.execute("""
        SELECT * FROM alteration 
        WHERE order_id = ?
        ORDER BY created_at DESC
    """, (order_id,)).fetchall()
    
    db.close()
    meas_dict = dict(measurements) if measurements else {}
    return render_template('Tailor_Order_Detail.html', order=order, progress=progress, measurements=meas_dict, alterations=alterations, name=session.get('name'))

@app.route('/tailor/orders')
def tailor_orders():
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    db = get_db()
    tailor = db.execute("SELECT status FROM tailor WHERE tailor_id=?", (session['user_id'],)).fetchone()
    if not tailor or tailor['status'] != 'Active':
        db.close()
        flash('Your tailor account is currently inactive. Please contact admin.', 'warning')
        return redirect(url_for('login'))
        
    tid = session['user_id']
    q = request.args.get('q', '').strip()
    
    today_count = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND DATE(order_date) = DATE('now')", (tid,)).fetchone()['c'] or 0
    pending_count = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status='Pending'", (tid,)).fetchone()['c'] or 0
    in_progress_count = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status IN ('In Progress', 'Accepted')", (tid,)).fetchone()['c'] or 0
    completed_count = db.execute("SELECT COUNT(*) AS c FROM orders WHERE tailor_id=? AND status='Completed'", (tid,)).fetchone()['c'] or 0

    query = """
        SELECT o.*, c.name AS customer_name, s.service_name
        FROM orders o
        LEFT JOIN customer c ON o.customer_id = c.customer_id
        LEFT JOIN service  s ON o.service_id  = s.service_id
        WHERE o.tailor_id = ?
    """
    params = [tid]
    if q:
        query += " AND (c.name LIKE ? OR CAST(o.order_id AS TEXT) LIKE ?)"
        params.append(f"%{q}%")
        params.append(f"%{q}%")
        
    query += " ORDER BY o.order_date DESC"
    orders = db.execute(query, params).fetchall()
    
    progress_updates = db.execute("""
        SELECT * FROM order_progress 
        WHERE order_id IN (SELECT order_id FROM orders WHERE tailor_id=?)
        ORDER BY timestamp ASC
    """, (tid,)).fetchall()
    
    alterations = db.execute("""
        SELECT * FROM alteration 
        WHERE order_id IN (SELECT order_id FROM orders WHERE tailor_id=?)
        ORDER BY created_at DESC
    """, (tid,)).fetchall()
    
    progress_dict = {}
    for p in progress_updates:
        if p['order_id'] not in progress_dict:
            progress_dict[p['order_id']] = []
        progress_dict[p['order_id']].append(p)

    alt_dict = {}
    for a in alterations:
        if a['order_id'] not in alt_dict:
            alt_dict[a['order_id']] = []
        alt_dict[a['order_id']].append(a)

    db.close()
    return render_template('Tailor_Orders.html', orders=orders,
                           name=session.get('name'), q=q,
                           today_count=today_count, pending_count=pending_count,
                           in_progress_count=in_progress_count, completed_count=completed_count,
                           progress_dict=progress_dict, alt_dict=alt_dict)

@app.route('/tailor/order/alteration/add/<int:order_id>', methods=['POST'])
def add_alteration(order_id):
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
        
    issue = request.form.get('issue_description')
    media = request.files.get('media')
    
    media_path = None
    if media and media.filename:
        filename = secure_filename(media.filename)
        new_filename = f"alt_{order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'alterations')
        os.makedirs(upload_folder, exist_ok=True)
        media.save(os.path.join(upload_folder, new_filename))
        media_path = f"uploads/alterations/{new_filename}"
        
    db = get_db()
    db.execute("""
        INSERT INTO alteration (order_id, issue_description, media_path)
        VALUES (?, ?, ?)
    """, (order_id, issue, media_path))
    
    # Also add a notification for the customer
    order = db.execute("SELECT customer_id FROM orders WHERE order_id=?", (order_id,)).fetchone()
    if order:
        db.execute("INSERT INTO notification(customer_id, message) VALUES(?, ?)", 
                   (order['customer_id'], f"An alteration record has been created for your order #{order_id}."))
    
    db.commit()
    db.close()
    flash('Alteration record created successfully.', 'success')
    return redirect(request.referrer or url_for('tailor_orders'))

@app.route('/tailor/order/alteration/update/<int:alteration_id>', methods=['POST'])
def update_alteration(alteration_id):
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
        
    status = request.form.get('status')
    db = get_db()
    if status == 'Completed':
        db.execute("UPDATE alteration SET status=?, completed_at=CURRENT_TIMESTAMP WHERE alteration_id=?", (status, alteration_id))
    else:
        db.execute("UPDATE alteration SET status=? WHERE alteration_id=?", (status, alteration_id))
    db.commit()
    db.close()
    flash('Alteration status updated.', 'success')
    return redirect(request.referrer or url_for('tailor_orders'))


@app.route('/tailor/order/update/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    status = request.form.get('status')
    db     = get_db()
    
    # Get customer info for notification
    order = db.execute("SELECT customer_id FROM orders WHERE order_id=?", (order_id,)).fetchone()
    
    if status == 'Completed':
        db.execute(
            "UPDATE orders SET status=?, completed_date=DATE('now') WHERE order_id=? AND tailor_id=?",
            (status, order_id, session['user_id'])
        )
    else:
        db.execute(
            "UPDATE orders SET status=?, completed_date=NULL WHERE order_id=? AND tailor_id=?",
            (status, order_id, session['user_id'])
        )
    
    if db.total_changes > 0 and order:
        db.execute(
            "INSERT INTO notification(customer_id, message) VALUES(?, ?)",
            (order['customer_id'], f"Your order #{order_id} status has been updated to: {status}")
        )
        
    db.commit()
    db.close()
    return redirect(url_for('tailor_orders'))

@app.route('/tailor/order/confirm-payment/<int:order_id>', methods=['POST'])
def confirm_payment(order_id):
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    
    db = get_db()
    tid = session['user_id']
    
    order = db.execute("SELECT * FROM orders WHERE order_id=? AND tailor_id=?", (order_id, tid)).fetchone()
    if order and order['payment_status'] == 'Pay at Shop':
        db.execute(
            "UPDATE orders SET status='Paid', payment_status='Paid' WHERE order_id=?",
            (order_id,)
        )
        # Notify Customer
        db.execute(
            "INSERT INTO notification(customer_id, message) VALUES(?, ?)",
            (order['customer_id'], f"Your offline payment for Order #{order_id} has been confirmed.")
        )
        db.commit()
        flash('Payment confirmed successfully.', 'success')
    else:
        flash('Cannot confirm payment for this order.', 'danger')
        
    db.close()
    return redirect(request.referrer or url_for('tailor_orders'))

@app.route('/tailor/order/progress/<int:order_id>', methods=['POST'])
def add_order_progress(order_id):
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
        
    stage = request.form.get('stage')
    notes = request.form.get('notes', '')
    image = request.files.get('image')
    
    if not stage:
        flash('Stage is required.', 'danger')
        return redirect(url_for('tailor_orders'))
        
    image_path = None
    if image and image.filename:
        filename = secure_filename(image.filename)
        timestamp_str = datetime.now().strftime('%Y%m%d%H%M%S')
        new_filename = f"{order_id}_{timestamp_str}_{filename}"
        upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'progress')
        os.makedirs(upload_folder, exist_ok=True)
        save_path = os.path.join(upload_folder, new_filename)
        image.save(save_path)
        image_path = f"uploads/progress/{new_filename}"
        
    db = get_db()
    order = db.execute("SELECT customer_id FROM orders WHERE order_id=? AND tailor_id=?", (order_id, session['user_id'])).fetchone()
    if order:
        db.execute(
            "INSERT INTO order_progress (order_id, stage, image_path, notes) VALUES (?, ?, ?, ?)",
            (order_id, stage, image_path, notes)
        )
        customer_id = order['customer_id']
        message = f"New progress update ({stage}) added for your order #{order_id}."
        db.execute(
            "INSERT INTO notification (customer_id, message) VALUES (?, ?)",
            (customer_id, message)
        )
        db.commit()
        flash('Progress updated successfully!', 'success')
    else:
        flash('Order not found or unauthorized.', 'danger')
        
    db.close()
    return redirect(url_for('tailor_orders'))


@app.route('/tailor/order/cancel/<int:order_id>', methods=['POST'])
def tailor_cancel_order(order_id):
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
        
    reason = request.form.get('reason')
    if not reason:
        flash('Cancellation reason is required.', 'danger')
        return redirect(url_for('tailor_orders'))
        
    db = get_db()
    tid = session['user_id']
    order = db.execute("SELECT * FROM orders WHERE order_id=? AND tailor_id=?", (order_id, tid)).fetchone()
    if order and order['status'] in ['Accepted', 'In Progress', 'Pending']:
        db.execute(
            "UPDATE orders SET status=?, notes=coalesce(notes,'')||? WHERE order_id=?",
            ('Cancelled by Tailor', f'\n[Cancelled by Tailor] Reason: {reason}', order_id)
        )
        db.execute(
            "INSERT INTO order_progress (order_id, stage, notes) VALUES (?, ?, ?)",
            (order_id, 'Cancelled by Tailor', reason)
        )
        db.execute(
            "INSERT INTO notification (customer_id, message) VALUES (?, ?)",
            (order['customer_id'], f"Your order #{order_id} was cancelled by the tailor. Reason: {reason}")
        )
        db.commit()
        flash(f'Order #{order_id} has been cancelled.', 'success')
    else:
        flash('Cannot cancel this order.', 'danger')
        
    db.close()
    return redirect(url_for('tailor_orders'))


@app.route('/tailor/order/reassign/<int:order_id>', methods=['POST'])
def tailor_reassign_order(order_id):
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
        
    reason = request.form.get('reason')
    if not reason:
        flash('Reassignment reason is required.', 'danger')
        return redirect(url_for('tailor_orders'))
        
    db = get_db()
    tid = session['user_id']
    order = db.execute("SELECT * FROM orders WHERE order_id=? AND tailor_id=?", (order_id, tid)).fetchone()
    if order and order['status'] in ['Accepted', 'In Progress', 'Pending']:
        customer_info = db.execute("SELECT city FROM customer WHERE customer_id=?", (order['customer_id'],)).fetchone()
        cust_city = customer_info['city'] if customer_info and customer_info['city'] else ''
        
        # 1. Search for available tailors in the same city
        new_tailor = None
        if cust_city:
            new_tailor = db.execute("SELECT tailor_id FROM tailor WHERE status='Active' AND tailor_id != ? AND shop_address LIKE ?", (tid, f"%{cust_city}%")).fetchone()
            
        # 2. Expand search if not found
        if not new_tailor:
            new_tailor = db.execute("SELECT tailor_id FROM tailor WHERE status='Active' AND tailor_id != ?", (tid,)).fetchone()
            
        if new_tailor:
            new_tid = new_tailor['tailor_id']
            db.execute("UPDATE orders SET tailor_id=?, status=?, notes=coalesce(notes,'')||? WHERE order_id=?",
                (new_tid, 'Pending', f'\n[Auto Reassigned] Transferred to new tailor. Prev reason: {reason}', order_id))
            db.execute("INSERT INTO order_progress (order_id, stage, notes) VALUES (?, ?, ?)",
                (order_id, 'Auto Reassigned', f"Reassigned to another tailor. Previous reason: {reason}"))
            db.execute("INSERT INTO notification (customer_id, message) VALUES (?, ?)",
                (order['customer_id'], f"Your order #{order_id} has been automatically reassigned to another available tailor."))
            flash(f'Order #{order_id} has been automatically assigned to another tailor.', 'success')
        else:
            db.execute(
                "UPDATE orders SET tailor_id=NULL, status=?, notes=coalesce(notes,'')||? WHERE order_id=?",
                ('Waiting for Tailor Assignment', f'\n[Pending Reassignment] Removed from Tailor. Reason: {reason}', order_id)
            )
            db.execute("INSERT INTO order_progress (order_id, stage, notes) VALUES (?, ?, ?)",
                (order_id, 'Waiting for Tailor Assignment', reason))
            db.execute("INSERT INTO notification (customer_id, message) VALUES (?, ?)",
                (order['customer_id'], f"We are finding a new tailor for your order #{order_id}."))
            flash(f'Order #{order_id} is now waiting for tailor assignment (Job Pool).', 'success')
        db.commit()
    else:
        flash('Cannot reassign this order.', 'danger')
        
    db.close()
    return redirect(url_for('tailor_orders'))


@app.route('/tailor/customers')
def tailor_customers():
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    db  = get_db()
    tid = session['user_id']
    
    # Calculate Stats
    total_cust = db.execute("SELECT COUNT(DISTINCT customer_id) AS c FROM orders WHERE tailor_id=?", (tid,)).fetchone()['c'] or 0
    repeat_cust = db.execute("""
        SELECT COUNT(*) FROM (
            SELECT customer_id FROM orders WHERE tailor_id=? GROUP BY customer_id HAVING COUNT(order_id) > 1
        )
    """, (tid,)).fetchone()[0] or 0
    avg_rating = db.execute("SELECT AVG(stars) FROM rating WHERE tailor_id=?", (tid,)).fetchone()[0] or 0.0

    customers = db.execute("""
        SELECT c.*, 
               COUNT(o.order_id) AS order_count, 
               (SELECT AVG(stars) FROM rating r WHERE r.customer_id = c.customer_id AND r.tailor_id = ?) AS avg_rating
        FROM customer c
        JOIN orders o ON c.customer_id = o.customer_id
        WHERE o.tailor_id = ?
        GROUP BY c.customer_id
    """, (tid, tid)).fetchall()
    
    # Get measurements for these customers
    measurements = db.execute("""
        SELECT DISTINCT c.name, m.*
        FROM measurement m
        JOIN customer c ON m.customer_id = c.customer_id
        WHERE c.customer_id IN (SELECT DISTINCT customer_id FROM orders WHERE tailor_id = ?)
    """, (tid,)).fetchall()

    db.close()
    return render_template('Tailor_Customers.html', customers=customers,
                           total_cust=total_cust, repeat_cust=repeat_cust,
                           avg_rating=round(avg_rating, 1), measurements=measurements,
                           name=session.get('name'))


@app.route('/tailor/profile', methods=['GET', 'POST'])
def tailor_profile():
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    db  = get_db()
    tailor = ensure_tailor_profile(db, session.get('email'), session.get('name'))
    if not tailor:
        db.close()
        flash('Tailor profile not found. Please login again.', 'danger')
        return redirect(url_for('login'))
    tid = tailor['tailor_id']
    session['user_id'] = tid

    if request.method == 'POST':
        shop_name  = request.form.get('shop_name', '').strip()
        phone      = request.form.get('phone', '').strip()
        location   = request.form.get('location', '').strip()
        speciality = request.form.get('speciality', '').strip()
        experience = request.form.get('experience', 0)

        if phone and not is_valid_phone(phone):
            flash('Invalid phone number format (10 digits required).', 'danger')
            return redirect(url_for('tailor_profile'))

        db.execute(
            """UPDATE tailor SET shop_name=?, contact_num=?, shop_address=?,
               speciality=?, experience=? WHERE tailor_id=?""",
            (shop_name, phone, location, speciality, experience, tid)
        )
        db.commit()
        session['name'] = shop_name
        flash('Shop profile updated!', 'success')

    tailor_row = db.execute("SELECT * FROM tailor WHERE tailor_id=?", (tid,)).fetchone()
    tailor = tailor_row or tailor
    db.close()
    return render_template('Tailor_Profile.html', tailor=tailor, name=session.get('name'))


@app.route('/tailor/change-password', methods=['POST'])
def tailor_change_password():
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    db       = get_db()
    tailor   = ensure_tailor_profile(db, session.get('email'), session.get('name'))
    if not tailor:
        db.close()
        flash('Tailor profile not found. Please login again.', 'danger')
        return redirect(url_for('login'))
    tid      = tailor['tailor_id']
    current  = request.form.get('current_password', '')
    new_pass = request.form.get('new_password', '')

    if len(new_pass) < 6:
        flash('New password must be at least 6 characters.', 'danger')
        return redirect(url_for('tailor_profile'))

    row      = db.execute("SELECT password FROM tailor WHERE tailor_id=?", (tid,)).fetchone()
    stored_password = row['password'] if row else tailor['password']
    if not check_password_hash(stored_password, current):
        flash('Current password is incorrect.', 'danger')
    else:
        hashed_new = generate_password_hash(new_pass)
        if row:
            db.execute("UPDATE tailor SET password=? WHERE tailor_id=?", (hashed_new, tid))
        db.execute("UPDATE login SET password=? WHERE email=?", (hashed_new, session['email']))
        db.commit()
        flash('Password updated successfully!', 'success')
    db.close()
    return redirect(url_for('tailor_profile'))


# ═══════════════════════════════════════════
#  ADMIN ROUTES
# ═══════════════════════════════════════════

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    db = get_db()

    # Calculate Stats
    stats = {
        'customers' : db.execute("SELECT COUNT(*) AS c FROM customer").fetchone()['c'],
        'tailors'   : db.execute("SELECT COUNT(*) AS c FROM tailor").fetchone()['c'],
        'orders'    : db.execute("SELECT COUNT(*) AS c FROM orders").fetchone()['c'],
        'completed' : db.execute("SELECT COUNT(*) AS c FROM orders WHERE status='Completed'").fetchone()['c'] or 0,
        'complaints': db.execute("SELECT COUNT(*) AS c FROM complaint WHERE status='Open'").fetchone()['c'],
        'pending'   : db.execute("SELECT COUNT(*) AS c FROM orders WHERE status IN ('Pending', 'In Progress', 'Accepted')").fetchone()['c'],
        'avg_rating': round(db.execute("SELECT AVG(stars) FROM rating").fetchone()[0] or 0.0, 1),
        'growth'    : 0
    }

    # Growth calculation (Simple: % increase in orders this month vs last month)
    curr_month = db.execute("SELECT COUNT(*) FROM orders WHERE strftime('%Y-%m', order_date) = strftime('%Y-%m', 'now')").fetchone()[0]
    last_month = db.execute("SELECT COUNT(*) FROM orders WHERE strftime('%Y-%m', order_date) = strftime('%Y-%m', 'now', '-1 month')").fetchone()[0]
    if last_month > 0:
        stats['growth'] = round(((curr_month - last_month) / last_month) * 100, 1)
    elif curr_month > 0:
        stats['growth'] = 100

    recent_orders = db.execute("""
        SELECT o.*, c.name AS customer_name, t.shop_name, s.service_name
        FROM orders o
        LEFT JOIN customer c ON o.customer_id = c.customer_id
        LEFT JOIN tailor   t ON o.tailor_id   = t.tailor_id
        LEFT JOIN service  s ON o.service_id  = s.service_id
        ORDER BY o.order_date DESC
        LIMIT 10
    """).fetchall()

    recent_users = db.execute("""
        SELECT customer_id AS id, name, email, 'Customer' AS role, date AS joined_date, 1 AS is_active, 'Active' as status
        FROM customer
        UNION ALL
        SELECT tailor_id AS id, shop_name AS name, email, 'Tailor' AS role, join_date AS joined_date, 
               (CASE WHEN status='Active' THEN 1 ELSE 0 END) AS is_active, status
        FROM tailor
        ORDER BY joined_date DESC
        LIMIT 10
    """).fetchall()

    db.close()
    return render_template('Admin_Dashboard.html', stats=stats,
                           recent_orders=recent_orders, recent_users=recent_users,
                           name=session.get('name'))


@app.route('/admin/customers')
def manage_customers():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    db        = get_db()
    customers = db.execute("SELECT * FROM customer ORDER BY date DESC").fetchall()
    
    stats = {
        'total' : len(customers),
        'active': len(customers), # Simplified, could be checked against login table if we had an 'active' flag
        'inactive': 0
    }
    
    db.close()
    return render_template('manage_customers.html', customers=customers,
                            stats=stats, name=session.get('name'))


@app.route('/admin/customers/delete/<customer_id>', methods=['POST'])
def delete_customer(customer_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    db  = get_db()
    row = db.execute(
        "SELECT email FROM customer WHERE customer_id=?", (customer_id,)
    ).fetchone()
    if row:
        db.execute("DELETE FROM customer WHERE customer_id=?", (customer_id,))
        db.execute("DELETE FROM login    WHERE email=?",        (row['email'],))
        db.commit()
        flash('Customer deleted.', 'success')
    else:
        flash('Customer not found.', 'warning')
    db.close()
    return redirect(url_for('manage_customers'))


@app.route('/admin/tailor/activate/<int:tailor_id>', methods=['POST'])
def admin_activate_tailor(tailor_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    db = get_db()
    db.execute("UPDATE tailor SET status='Active' WHERE tailor_id=?", (tailor_id,))
    db.commit()
    db.close()
    flash('Tailor account activated successfully.', 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/customers/add', methods=['POST'])
def admin_add_customer():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    name     = request.form.get('name', '').strip()
    email    = request.form.get('email', '').strip()
    phone    = request.form.get('phone', '').strip()
    address  = request.form.get('address', '').strip()
    password = request.form.get('password', '123456').strip() # Default if not provided

    if not name or not is_valid_email(email) or not is_valid_phone(phone):
        flash('Invalid input data. Please check Name, Email, and Phone.', 'danger')
        return redirect(url_for('manage_customers'))

    db = get_db()
    try:
        existing = db.execute("SELECT email FROM login WHERE email=?", (email,)).fetchone()
        if existing:
            flash('Email already registered.', 'warning')
            return redirect(url_for('manage_customers'))

        hashed_pass = generate_password_hash(password)
        cursor = db.execute(
            "INSERT INTO login(email, password, role) VALUES(?, ?, 'customer')",
            (email, hashed_pass)
        )
        login_id = cursor.lastrowid
        db.execute(
            """INSERT INTO customer(customer_id, name, email, password,
               contact_num, city, address) VALUES(?,?,?,?,?,?,?)""",
            (login_id, name, email, hashed_pass, phone, '', address)
        )
        db.commit()
        flash('Customer added successfully.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('manage_customers'))


@app.route('/admin/tailors')
def manage_tailors():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    db      = get_db()
    tailors = db.execute("SELECT * FROM tailor ORDER BY join_date DESC").fetchall()
    
    stats = {
        'total': len(tailors),
        'avg_rating': round(db.execute("SELECT AVG(rating) FROM tailor").fetchone()[0] or 0.0, 1),
        'orders': db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    }
    
    db.close()
    return render_template('manage_tailors.html', tailors=tailors,
                           stats=stats, name=session.get('name'))


@app.route('/admin/tailors/delete/<tailor_id>', methods=['POST'])
def delete_tailor(tailor_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    db  = get_db()
    row = db.execute(
        "SELECT email FROM tailor WHERE tailor_id=?", (tailor_id,)
    ).fetchone()
    if row:
        db.execute("DELETE FROM tailor WHERE tailor_id=?", (tailor_id,))
        db.execute("DELETE FROM login  WHERE email=?",     (row['email'],))
        db.commit()
        flash('Tailor deleted.', 'success')
    else:
        flash('Tailor not found.', 'warning')
    db.close()
    return redirect(url_for('manage_tailors'))


@app.route('/admin/tailors/add', methods=['POST'])
def admin_add_tailor():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    shop_name       = request.form.get('shop_name', '').strip()
    email           = request.form.get('email', '').strip()
    phone           = request.form.get('phone', '').strip()
    location        = request.form.get('location', '').strip()
    speciality      = request.form.get('speciality', 'All Types').strip()
    password        = request.form.get('password', '123456').strip()
    gender_category = request.form.get('gender_category', 'Both').strip()

    if not shop_name or not is_valid_email(email) or not is_valid_phone(phone):
        flash('Invalid input data. Please check Shop Name, Email, and Phone.', 'danger')
        return redirect(url_for('manage_tailors'))

    db = get_db()
    try:
        existing = db.execute("SELECT email FROM login WHERE email=?", (email,)).fetchone()
        if existing:
            flash('Email already registered.', 'warning')
            return redirect(url_for('manage_tailors'))

        hashed_pass = generate_password_hash(password)
        cursor = db.execute(
            "INSERT INTO login(email, password, role) VALUES(?, ?, 'tailor')",
            (email, hashed_pass)
        )
        login_id = cursor.lastrowid
        db.execute(
            """INSERT INTO tailor(tailor_id, name, shop_name, email, password,
               contact_num, shop_address, speciality, experience, gender_category, status)
               VALUES(?,?,?,?,?,?,?,?,?,?,'Active')""",
            (login_id, shop_name, shop_name, email, hashed_pass, phone, location, speciality, 0, gender_category)
        )
        db.commit()
        flash('Tailor added successfully.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('manage_tailors'))


@app.route('/admin/orders')
def manage_orders():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    db = get_db()
    orders = db.execute("""
        SELECT o.*, c.name AS customer_name, t.shop_name, s.service_name
        FROM orders o
        LEFT JOIN customer c ON o.customer_id = c.customer_id
        LEFT JOIN tailor   t ON o.tailor_id   = t.tailor_id
        LEFT JOIN service  s ON o.service_id  = s.service_id
        ORDER BY o.order_date DESC
    """).fetchall()
    
    stats = {
        'total': len(orders),
        'pending': db.execute("SELECT COUNT(*) FROM orders WHERE status='Pending'").fetchone()[0],
        'in_progress': db.execute("SELECT COUNT(*) FROM orders WHERE status IN ('In Progress', 'Accepted')").fetchone()[0],
        'completed': db.execute("SELECT COUNT(*) FROM orders WHERE status='Completed'").fetchone()[0],
        'waiting': db.execute("SELECT COUNT(*) FROM orders WHERE status='Waiting for Tailor Assignment'").fetchone()[0]
    }
    
    tailors = db.execute("SELECT tailor_id, name, shop_name FROM tailor WHERE status='Active'").fetchall()
    
    db.close()
    return render_template('manage_orders.html', orders=orders,
                           stats=stats, tailors=tailors, name=session.get('name'))


@app.route('/admin/orders/assign/<int:order_id>', methods=['POST'])
def admin_assign_order(order_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    new_tailor_id = request.form.get('tailor_id')
    if not new_tailor_id:
        flash('Tailor selection is required.', 'danger')
        return redirect(url_for('manage_orders'))
        
    db = get_db()
    tailor = db.execute("SELECT name FROM tailor WHERE tailor_id=?", (new_tailor_id,)).fetchone()
    if tailor:
        db.execute("UPDATE orders SET tailor_id=?, status='Pending', notes=coalesce(notes,'')||? WHERE order_id=?",
                   (new_tailor_id, f'\n[Admin Assigned] Assigned to {tailor["name"]}.', order_id))
        order = db.execute("SELECT customer_id FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if order:
            db.execute("INSERT INTO notification (customer_id, message) VALUES (?, ?)",
                       (order['customer_id'], f"Your order #{order_id} has been manually assigned to a new tailor by Admin."))
        db.commit()
        flash('Order assigned successfully.', 'success')
    else:
        flash('Invalid Tailor selected.', 'danger')
        
    db.close()
    return redirect(url_for('manage_orders'))


@app.route('/admin/orders/update/<int:order_id>', methods=['POST'])
def admin_update_order(order_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    status = request.form.get('status')
    db     = get_db()
    db.execute("UPDATE orders SET status=? WHERE order_id=?", (status, order_id))
    db.commit()
    db.close()
    return redirect(url_for('manage_orders'))


@app.route('/admin/reports')
def reports():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    tailor_id = request.args.get('tailor_id', type=int)
    db = get_db()
    
    # Filter clauses
    where_c = " WHERE tailor_id = ?" if tailor_id else ""
    where_and = " AND tailor_id = ?" if tailor_id else ""
    params = (tailor_id,) if tailor_id else ()
    
    # KPI Stats for Report
    stats = {
        'orders': db.execute("SELECT COUNT(*) FROM orders" + where_c, params).fetchone()[0],
        'avg_rating': round(db.execute("SELECT AVG(stars) FROM rating" + where_c, params).fetchone()[0] or 0.0, 1),
        'growth'    : 0,
        'completed': db.execute("SELECT COUNT(*) FROM orders WHERE status='Completed'" + where_and, params).fetchone()[0],
        'pending': db.execute("SELECT COUNT(*) FROM orders WHERE status='Pending'" + where_and, params).fetchone()[0]
    }
    
    # Growth Calculation
    curr_month_str = datetime.now().strftime('%Y-%m')
    curr_month = db.execute("SELECT COUNT(*) FROM orders WHERE strftime('%Y-%m', order_date) = ?" + where_and, (curr_month_str,) + params).fetchone()[0]
    last_month = db.execute("SELECT COUNT(*) FROM orders WHERE strftime('%Y-%m', order_date) = strftime('%Y-%m', 'now', '-1 month')" + where_and, params).fetchone()[0]
    
    if last_month > 0:
        stats['growth'] = round(((curr_month - last_month) / last_month) * 100, 1)
    elif curr_month > 0:
        stats['growth'] = 100.0
    else:
        stats['growth'] = 0.0

    # New Registrations
    new_regs = {
        'customers': db.execute("SELECT COUNT(*) FROM customer WHERE strftime('%Y-%m', date) = ?", (curr_month_str,)).fetchone()[0],
        'tailors': db.execute("SELECT COUNT(*) FROM tailor WHERE strftime('%Y-%m', join_date) = ?", (curr_month_str,)).fetchone()[0]
    }

    # Status Distribution
    total_orders = stats['orders'] or 1
    status_data = db.execute(f"""
        SELECT status, COUNT(*) as count
        FROM orders
        {where_c}
        GROUP BY status
    """, params).fetchall()
    
    status_list = []
    for row in status_data:
        status_list.append({
            'status': row['status'],
            'count': row['count'],
            'percentage': round((row['count'] / total_orders) * 100, 1)
        })

    # Status Distribution for Charts
    status_dist = {
        'labels': [r['status'] for r in status_list],
        'counts': [r['count'] for r in status_list]
    }

    # Monthly Orders for Chart
    monthly = db.execute(f"""
        SELECT strftime('%Y-%m', order_date) AS month,
               COUNT(*) AS total_orders
        FROM orders
        {where_c}
        GROUP BY month
        ORDER BY month ASC
        LIMIT 12
    """, params).fetchall()

    # Top Tailors (by Order Count)
    top_tailors = db.execute("""
        SELECT t.shop_name, IFNULL(AVG(r.stars), 0) as avg_rating,
               COUNT(o.order_id) AS orders
        FROM tailor t
        LEFT JOIN orders o ON t.tailor_id = o.tailor_id
        LEFT JOIN rating r ON t.tailor_id = r.tailor_id
        GROUP BY t.tailor_id
        ORDER BY orders DESC
        LIMIT 5
    """).fetchall()

    # Top Dress Types
    top_dresses = db.execute(f"""
        SELECT dress_type, COUNT(*) as count 
        FROM orders 
        {where_c}
        GROUP BY dress_type 
        ORDER BY count DESC 
        LIMIT 5
    """, params).fetchall()

    # Recent Orders
    recent_orders = db.execute(f"""
        SELECT o.*, c.name as customer_name, t.shop_name
        FROM orders o
        JOIN customer c ON o.customer_id = c.customer_id
        JOIN tailor t ON o.tailor_id = t.tailor_id
        {where_c}
        ORDER BY o.order_date DESC
        LIMIT 10
    """, params).fetchall()

    # Platform Insights
    insights = {
        'total_customers': db.execute("SELECT COUNT(*) FROM customer").fetchone()[0],
        'total_tailors': db.execute("SELECT COUNT(*) FROM tailor").fetchone()[0],
        'total_services': db.execute("SELECT COUNT(*) FROM service").fetchone()[0],
        'total_reviews': db.execute("SELECT COUNT(*) FROM rating").fetchone()[0]
    }

    all_tailors = db.execute("SELECT tailor_id, shop_name FROM tailor ORDER BY shop_name").fetchall()

    db.close()
    return render_template('Reports.html', stats=stats, status_list=status_list,
                           status_dist=status_dist, new_regs=new_regs, 
                           monthly=monthly, top_tailors=top_tailors, 
                           top_dresses=top_dresses, recent_orders=recent_orders,
                           insights=insights, all_tailors=all_tailors, 
                           selected_tailor=tailor_id, name=session.get('name'))


@app.route('/admin/reports/pdf')
def admin_reports_pdf():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    db = get_db()
    
    # 1. Fetch Data
    admin_name = session.get('name', 'Administrator')
    report_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # KPI Stats
    stats = {
        'orders': db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        'avg_rating': round(db.execute("SELECT AVG(stars) FROM rating").fetchone()[0] or 0.0, 1),
        'completed': db.execute("SELECT COUNT(*) FROM orders WHERE status='Completed'").fetchone()[0],
    }
    
    # Status Distribution
    total_orders = stats['orders'] or 1
    status_data = db.execute("""
        SELECT status, COUNT(*) as count 
        FROM orders 
        GROUP BY status
    """).fetchall()
    
    status_list = []
    for row in status_data:
        status_list.append({
            'status': row['status'],
            'count': row['count'],
            'percentage': round((row['count'] / total_orders) * 100, 1)
        })

    # Top Tailors
    top_tailors = db.execute("""
        SELECT t.shop_name, COUNT(o.order_id) as total_orders
        FROM tailor t
        LEFT JOIN orders o ON t.tailor_id = o.tailor_id
        WHERE o.status='Completed'
        GROUP BY t.tailor_id
        ORDER BY total_orders DESC
        LIMIT 5
    """).fetchall()

    # Detailed Orders
    detailed_orders = db.execute("""
        SELECT o.order_id, c.name as customer_name, t.shop_name, o.dress_type, o.status, o.order_date
        FROM orders o
        JOIN customer c ON o.customer_id = c.customer_id
        JOIN tailor t ON o.tailor_id = t.tailor_id
        ORDER BY o.order_date DESC
        LIMIT 30
    """).fetchall()

    db.close()

    # 2. PDF Generation
    class PDFReport(FPDF):
        def header(self):
            # Platform Header
            self.set_fill_color(26, 35, 64) # Navy
            self.rect(0, 0, 210, 40, 'F')
            
            self.set_font("Arial", 'B', 24)
            self.set_text_color(200, 151, 58) # Gold
            self.cell(0, 10, "MY TAILOR", ln=True, align='L')
            
            self.set_font("Arial", 'B', 12)
            self.set_text_color(255, 255, 255)
            self.cell(0, 10, "Business Analytics & Performance Report", ln=True, align='L')
            
            self.set_y(10)
            self.set_font("Arial", '', 10)
            self.set_text_color(255, 255, 255)
            self.cell(0, 5, f"Admin: {admin_name}", ln=True, align='R')
            self.cell(0, 5, f"Generated: {report_date}", ln=True, align='R')
            
            # Reset cursor to below the navy bar (height 40)
            self.set_y(50)


        def footer(self):
            self.set_y(-15)
            self.set_font("Arial", 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f"Page {self.page_no()} | Confidential Business Document | My Tailor Platform", align='C')

        def section_title(self, title):
            self.set_font("Arial", 'B', 14)
            self.set_text_color(26, 35, 64)
            self.set_draw_color(200, 151, 58)
            self.cell(0, 10, title, ln=True)
            self.line(self.get_x(), self.get_y() - 2, self.get_x() + 190, self.get_y() - 2)
            self.ln(3)

        def create_table_header(self, columns, widths):
            self.set_font("Arial", 'B', 10)
            self.set_fill_color(240, 240, 240)
            self.set_text_color(26, 35, 64)
            for i in range(len(columns)):
                self.cell(widths[i], 8, columns[i], border=1, align='C', fill=True)
            self.ln()

    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- Section 1: KPI Summary ---
    pdf.section_title("Key Performance Indicators (KPIs)")
    kpi_widths = [70, 50, 70]
    pdf.create_table_header(["Metric", "Current Value", "Performance Remarks"], kpi_widths)
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(0, 0, 0)
    
    kpis = [
        ["Total Orders", str(stats['orders']), f"{stats['orders']} transactions processed"],
        ["Average Rating", f"{stats['avg_rating']} / 5.0", "Excellent quality" if stats['avg_rating'] >= 4 else "Room for improvement"]
    ]
    for row in kpis:
        pdf.cell(kpi_widths[0], 8, row[0], border=1)
        pdf.cell(kpi_widths[1], 8, row[1], border=1, align='R')
        pdf.cell(kpi_widths[2], 8, row[2], border=1)
        pdf.ln()
    pdf.ln(10)

    # --- Section 2: Order Status Distribution ---
    pdf.section_title("Order Status Distribution")
    status_widths = [70, 60, 60]
    pdf.create_table_header(["Status", "Orders", "Percentage"], status_widths)
    pdf.set_font("Arial", '', 10)
    for row in status_list:
        pdf.cell(status_widths[0], 8, row['status'], border=1)
        pdf.cell(status_widths[1], 8, str(row['count']), border=1, align='C')
        pdf.cell(status_widths[2], 8, f"{row['percentage']}%", border=1, align='C')
        pdf.ln()
    pdf.ln(10)

    # --- Section 3: Top Performance ---
    pdf.section_title("Top Performing Tailors / Shops")
    tailor_widths = [100, 60, 30]
    pdf.create_table_header(["Tailor / Shop Name", "Completed Orders", "Rank"], tailor_widths)
    pdf.set_font("Arial", '', 10)
    for i, row in enumerate(top_tailors):
        pdf.cell(tailor_widths[0], 8, row['shop_name'], border=1)
        pdf.cell(tailor_widths[1], 8, str(row['total_orders']), border=1, align='C')
        pdf.cell(tailor_widths[2], 8, f"#{i+1}", border=1, align='C')
        pdf.ln()
    pdf.ln(10)

    # --- Section 4: Detailed Order Log ---
    pdf.add_page()
    pdf.section_title("Detailed Order Activity Log")
    order_widths = [20, 40, 45, 40, 45]
    pdf.create_table_header(["ID", "Customer", "Tailor/Shop", "Dress Type", "Status"], order_widths)
    pdf.set_font("Arial", '', 8)
    for row in detailed_orders:
        pdf.cell(order_widths[0], 7, str(row['order_id']), border=1, align='C')
        pdf.cell(order_widths[1], 7, row['customer_name'][:20], border=1)
        pdf.cell(order_widths[2], 7, row['shop_name'][:22], border=1)
        pdf.cell(order_widths[3], 7, row['dress_type'][:20], border=1)
        pdf.cell(order_widths[4], 7, row['status'], border=1)
        pdf.ln()

    # Output to Memory Buffer
    output = io.BytesIO()
    # fpdf2 returns bytes directly from output(). dest='S' is deprecated.
    pdf_out = pdf.output(dest='S')
    if isinstance(pdf_out, str): # Fallback for older fpdf versions
        output.write(pdf_out.encode('latin1'))
    else:
        output.write(pdf_out)
    output.seek(0)
    
    return send_file(output, download_name=f"Admin_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf", as_attachment=True)


# ─────────────────────────────────────────
#  ADMIN PROFILE
# ─────────────────────────────────────────
@app.route('/admin/profile', methods=['GET', 'POST'])
def admin_profile():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    db  = get_db()
    aid = session['user_id']
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        db.execute("UPDATE admin SET name=? WHERE admin_id=?", (name, aid))
        db.commit()
        session['name'] = name
        flash('Profile updated!', 'success')
    admin = db.execute("SELECT * FROM admin WHERE admin_id=?", (aid,)).fetchone()
    db.close()
    return render_template('Admin_Profile.html', admin=admin, name=session.get('name'))


@app.route('/admin/change-password', methods=['POST'])
def admin_change_password():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    db       = get_db()
    aid      = session['user_id']
    current  = request.form.get('current_password', '')
    new_pass = request.form.get('new_password', '')

    if len(new_pass) < 6:
        flash('New password must be at least 6 characters.', 'danger')
        return redirect(url_for('admin_profile'))

    row      = db.execute("SELECT password FROM admin WHERE admin_id=?", (aid,)).fetchone()
    if not check_password_hash(row['password'], current):
        flash('Current password is incorrect.', 'danger')
    else:
        hashed_new = generate_password_hash(new_pass)
        db.execute("UPDATE admin SET password=? WHERE admin_id=?", (hashed_new, aid))
        db.execute("UPDATE login SET password=? WHERE email=?", (hashed_new, session['email']))
        db.commit()
        flash('Password updated successfully!', 'success')
    db.close()
    return redirect(url_for('admin_profile'))

@app.route('/tailor/job_pool')
def tailor_job_pool():
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    db = get_db()
    available_orders = db.execute("""
        SELECT o.*, c.name AS customer_name, c.city 
        FROM orders o
        JOIN customer c ON o.customer_id = c.customer_id
        WHERE o.status = 'Waiting for Tailor Assignment'
        ORDER BY o.order_date DESC
    """).fetchall()
    db.close()
    return render_template('Tailor_Job_Pool.html', orders=available_orders, name=session.get('name'))

@app.route('/tailor/job_pool/accept/<int:order_id>', methods=['POST'])
def tailor_accept_job(order_id):
    if session.get('role') != 'tailor':
        return redirect(url_for('login'))
    db = get_db()
    tid = session['user_id']
    order = db.execute("SELECT * FROM orders WHERE order_id=? AND status='Waiting for Tailor Assignment'", (order_id,)).fetchone()
    if order:
        db.execute("UPDATE orders SET tailor_id=?, status='Pending', notes=coalesce(notes,'')||? WHERE order_id=?",
                   (tid, '\n[Job Pool] Order accepted by a new tailor.', order_id))
        db.execute("INSERT INTO notification (customer_id, message) VALUES (?, ?)",
                   (order['customer_id'], f"Good news! Your order #{order_id} has been accepted by a new tailor."))
        db.commit()
        flash('You have successfully accepted the order!', 'success')
    else:
        flash('Order is no longer available.', 'danger')
    db.close()
    return redirect(url_for('tailor_orders'))

# ─────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
