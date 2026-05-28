PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- CUSTOMER TABLE MIGRATION
ALTER TABLE customer RENAME TO customer_old;
CREATE TABLE customer (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL,
    contact_num TEXT CHECK(contact_num IS NULL OR (contact_num GLOB '[0-9]*' AND LENGTH(contact_num) BETWEEN 10 AND 12)),
    city        TEXT,
    address     TEXT,
    date        DATE DEFAULT (DATE('now'))
);
INSERT INTO customer SELECT * FROM customer_old;
DROP TABLE customer_old;

-- TAILOR TABLE MIGRATION
ALTER TABLE tailor RENAME TO tailor_old;
CREATE TABLE tailor (
    tailor_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    shop_name    TEXT NOT NULL,
    email        TEXT NOT NULL UNIQUE,
    password     TEXT NOT NULL,
    contact_num  TEXT CHECK(contact_num IS NULL OR (contact_num GLOB '[0-9]*' AND LENGTH(contact_num) BETWEEN 10 AND 12)),
    shop_address TEXT,
    speciality   TEXT,
    experience   INTEGER DEFAULT 0,
    rating       REAL    DEFAULT 0.0,
    join_date    DATE    DEFAULT (DATE('now'))
);
INSERT INTO tailor SELECT * FROM tailor_old;
DROP TABLE tailor_old;

COMMIT;
PRAGMA foreign_keys=ON;
