-- ============================================================
--  MY TAILOR — Complete Database Schema + Seed Data
--  Database: SQLite
-- ============================================================

PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────
--  LOGIN  (shared auth for all roles)
-- ─────────────────────────────────────────
CREATE TABLE login (
    login_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    email     TEXT    NOT NULL UNIQUE,
    password  TEXT    NOT NULL,          -- store hashed (bcrypt) in production
    role      TEXT    NOT NULL CHECK(role IN ('customer','tailor','admin'))
);

-- ─────────────────────────────────────────
--  ADMIN
-- ─────────────────────────────────────────
CREATE TABLE admin (
    admin_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    email     TEXT NOT NULL UNIQUE,
    password  TEXT NOT NULL
);

-- ─────────────────────────────────────────
--  CUSTOMER
-- ─────────────────────────────────────────
CREATE TABLE customer (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL,
    contact_num TEXT,
    city        TEXT,
    address     TEXT,
    date        DATE DEFAULT (DATE('now'))
);

-- ─────────────────────────────────────────
--  TAILOR  (fixed: added name, shop_name, speciality, experience)
-- ─────────────────────────────────────────
CREATE TABLE tailor (
    tailor_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,          -- tailor owner's name
    shop_name    TEXT NOT NULL,          -- shop display name
    email        TEXT NOT NULL UNIQUE,
    password     TEXT NOT NULL,
    contact_num  TEXT,
    shop_address TEXT,
    speciality   TEXT,                   -- Mens/Womens/Alterations etc.
    experience   INTEGER DEFAULT 0,      -- years
    rating       REAL    DEFAULT 0.0,    -- auto-updated from rating table
    join_date    DATE    DEFAULT (DATE('now'))
);

-- ─────────────────────────────────────────
--  SERVICE
-- ─────────────────────────────────────────
CREATE TABLE service (
    service_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL,
    price        REAL NOT NULL
);

-- ─────────────────────────────────────────
--  ORDERS  (fixed: added gender, dress_type, fabric, notes, design_ref)
-- ─────────────────────────────────────────
CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id   INTEGER NOT NULL,
    tailor_id     INTEGER NOT NULL,
    service_id    INTEGER,
    gender        TEXT CHECK(gender IN ('Male','Female','Kids')),
    dress_type    TEXT,
    fabric        TEXT,
    order_date    DATE NOT NULL DEFAULT (DATE('now')),
    delivery_date DATE,
    amount        REAL DEFAULT 0,
    status        TEXT DEFAULT 'Pending'
                  CHECK(status IN ('Pending','In Progress','Completed','Cancelled','Rejected')),
    notes         TEXT,
    design_ref    TEXT,                  -- file path or URL for design reference image
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    FOREIGN KEY (tailor_id)   REFERENCES tailor(tailor_id),
    FOREIGN KEY (service_id)  REFERENCES service(service_id)
);

-- ─────────────────────────────────────────
--  MEASUREMENT  (fixed: replaced single description with proper fields)
-- ─────────────────────────────────────────
CREATE TABLE measurement (
    measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id    INTEGER NOT NULL UNIQUE, -- one record per customer
    chest          REAL,
    waist          REAL,
    length         REAL,
    shoulder       REAL,
    hip            REAL,
    sleeve         REAL,
    neck           REAL,
    inseam         REAL,
    updated_at     DATETIME DEFAULT (DATETIME('now'))
);

-- ─────────────────────────────────────────
--  COMPLAINT  (fixed: added subject column)
-- ─────────────────────────────────────────
CREATE TABLE complaint (
    complaint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  INTEGER NOT NULL,
    tailor_id    INTEGER,
    admin_id     INTEGER,
    subject      TEXT NOT NULL,
    description  TEXT NOT NULL,
    date         DATE DEFAULT (DATE('now')),
    status       TEXT DEFAULT 'Open'
                 CHECK(status IN ('Open','In Review','Resolved','Closed')),
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    FOREIGN KEY (tailor_id)   REFERENCES tailor(tailor_id),
    FOREIGN KEY (admin_id)    REFERENCES admin(admin_id)
);

-- ─────────────────────────────────────────
--  RATING  (new: customer rates tailor after order completion)
-- ─────────────────────────────────────────
CREATE TABLE rating (
    rating_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL UNIQUE, -- one rating per order only
    customer_id INTEGER NOT NULL,
    tailor_id   INTEGER NOT NULL,
    stars       INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
    review      TEXT,
    date        DATE DEFAULT (DATE('now')),
    FOREIGN KEY (order_id)    REFERENCES orders(order_id),
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    FOREIGN KEY (tailor_id)   REFERENCES tailor(tailor_id)
);

-- ============================================================
--  SEED DATA
-- ============================================================

INSERT INTO login(email,password,role) VALUES
  ('admin@mytailor.com','admin123','admin'),
  ('rahul@gmail.com','pass123','customer'),
  ('priya@gmail.com','pass123','customer'),
  ('amit@gmail.com','pass123','customer'),
  ('sunita@gmail.com','pass123','customer'),
  ('elite@gmail.com','tailor123','tailor'),
  ('stylestitch@gmail.com','tailor123','tailor'),
  ('fashioncraft@gmail.com','tailor123','tailor');

INSERT INTO admin VALUES (1,'Admin User','admin@mytailor.com','admin123');

INSERT INTO customer(customer_id, name, email, password, contact_num, city, address, date) VALUES
  (1,'Rahul Kulkarni','rahul@gmail.com','pass123','9800000001','Nashik','Nashik, MH','2025-03-01'),
  (2,'Priya Sharma','priya@gmail.com','pass123','9800000002','Nashik','Nashik, MH','2025-03-10'),
  (3,'Amit Shah','amit@gmail.com','pass123','9800000003','Nashik','Nashik, MH','2025-03-15'),
  (4,'Sunita Patil','sunita@gmail.com','pass123','9800000004','Nashik','Nashik, MH','2025-03-20');

INSERT INTO tailor(tailor_id, name, shop_name, email, password, contact_num, shop_address, speciality, experience, rating, join_date) VALUES
  (1,'Ravi Joshi','Elite Tailors','elite@gmail.com','tailor123','9800100001','MG Road, Nashik','Mens Clothing',8,4.9,'2025-02-15'),
  (2,'Meena Desai','Style Stitch','stylestitch@gmail.com','tailor123','9800100002','College Road, Nashik','Womens Clothing',5,4.7,'2025-01-20'),
  (3,'Suresh More','Fashion Craft','fashioncraft@gmail.com','tailor123','9800100003','Indira Nagar, Nashik','Alterations',10,4.8,'2025-01-10');

INSERT INTO service(service_name,price) VALUES
  ('Shirt',450), ('Suit',1200), ('Salwar',600),
  ('Saree Blouse',350), ('Trouser',400), ('Kurti',500), ('Alteration',150);

INSERT INTO orders(customer_id,tailor_id,service_id,gender,dress_type,fabric,order_date,delivery_date,amount,status,notes) VALUES
  (1,1,1,'Male','Shirt','Cotton','2025-04-01','2025-04-07',450,'Pending','White formal shirt'),
  (3,1,2,'Male','Suit','Wool','2025-03-30','2025-04-06',1200,'In Progress','Navy blue suit'),
  (2,2,3,'Female','Salwar','Silk','2025-03-28','2025-04-03',600,'Completed','Red salwar kameez'),
  (4,3,7,'Female','Alteration','N/A','2025-03-25','2025-03-28',150,'Completed','Blouse alteration');

INSERT INTO measurement(customer_id,chest,waist,length,shoulder,hip,sleeve,neck,inseam) VALUES
  (1,40,34,28,18,38,26,15,28),
  (2,36,30,26,16,36,24,13,26);

INSERT INTO complaint(customer_id,tailor_id,admin_id,subject,description,status) VALUES
  (1,1,1,'Late Delivery','My order was delayed by 3 days with no update.','Open'),
  (2,2,1,'Poor Stitching','The stitching quality was not as expected.','Resolved');

INSERT INTO rating(order_id,customer_id,tailor_id,stars,review) VALUES
  (3,2,2,5,'Excellent work! Very happy with the salwar.'),
  (4,4,3,4,'Good alteration, delivered on time.');
