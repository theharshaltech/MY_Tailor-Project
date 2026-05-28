import sqlite3
import os
from werkzeug.security import generate_password_hash

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Looking at app.py: BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# My_Tailor_google _COPY updated\My_Tailor_google _COPY alternative\My_Tailor\Backend\Backend\app.py
# So the database is 3 levels up from app.py path?
# Wait, line 16: BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# If app.py is in Backend\Backend, then:
# 1 up: Backend
# 2 up: My_Tailor
# 3 up: My_Tailor_google _COPY alternative
# Then Database\my_tailor.db
# Let's verify the path.

DB_PATH = r"y:\My_Tailor_google _COPY updated\My_Tailor_google _COPY alternative\My_Tailor\Database\my_tailor.db"

def seed():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
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
        
        # Check if already exists
        exists = conn.execute("SELECT 1 FROM login WHERE email=?", (email,)).fetchone()
        if exists:
            print(f"Skipping {shop}, already exists.")
            continue
            
        pass_hash = generate_password_hash("password123")
        
        try:
            # Insert into login
            cur = conn.execute("INSERT INTO login(email, password, role) VALUES(?,?, 'tailor')", (email, pass_hash))
            tid = cur.lastrowid
            
            # Insert into tailor
            conn.execute("""
                INSERT INTO tailor(tailor_id, name, shop_name, email, password, shop_address, speciality, gender_category, status, rating)
                VALUES(?,?,?,?,?,?,'All Types',?,'Active', 4.5)
            """, (tid, name, shop, email, pass_hash, loc, gen))
            print(f"Added {shop} in {loc}")
        except Exception as e:
            print(f"Error adding {shop}: {e}")
            
    conn.commit()
    conn.close()
    print("Seeding completed.")

if __name__ == "__main__":
    seed()
