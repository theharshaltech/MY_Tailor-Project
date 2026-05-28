PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- Recreate orders
CREATE TABLE orders_new (
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
    design_ref    TEXT, 
    completed_date DATE,
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    FOREIGN KEY (tailor_id)   REFERENCES tailor(tailor_id),
    FOREIGN KEY (service_id)  REFERENCES service(service_id)
);
INSERT INTO orders_new SELECT * FROM orders;
DROP TABLE orders;
ALTER TABLE orders_new RENAME TO orders;

-- Recreate complaint
CREATE TABLE complaint_new (
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
INSERT INTO complaint_new SELECT * FROM complaint;
DROP TABLE complaint;
ALTER TABLE complaint_new RENAME TO complaint;

-- Recreate rating
CREATE TABLE rating_new (
    rating_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    tailor_id   INTEGER NOT NULL,
    stars       INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
    review      TEXT,
    date        DATE DEFAULT (DATE('now')),
    FOREIGN KEY (order_id)    REFERENCES orders(order_id),
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    FOREIGN KEY (tailor_id)   REFERENCES tailor(tailor_id)
);
INSERT INTO rating_new SELECT * FROM rating;
DROP TABLE rating;
ALTER TABLE rating_new RENAME TO rating;

COMMIT;
PRAGMA foreign_keys = ON;
