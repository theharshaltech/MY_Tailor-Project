# My Tailor — Flask Backend

## Folder Structure
```
My_Tailor/
├── Backend/
│   ├── app.py           ← Flask app (run this)
│   ├── requirements.txt
│   └── README.md
├── Database/
│   └── my_tailor        ← SQLite database
├── FrontEnd/
│   ├── index.html
│   ├── Login.html
│   └── ... (all HTML pages)
└── Images/
```

## Setup & Run

### Step 1 — Install Flask
Open terminal in the `Backend` folder and run:
```
pip install -r requirements.txt
```

### Step 2 — Run the app
```
python app.py
```

### Step 3 — Open in browser
```
http://127.0.0.1:5000
```

---

## Login Credentials (for testing)

| Role     | Email                    | Password   |
|----------|--------------------------|------------|
| Admin    | admin@mytailor.com       | admin123   |
| Customer | rahul@gmail.com          | pass123    |
| Customer | priya@gmail.com          | pass123    |
| Tailor   | elite@gmail.com          | tailor123  |
| Tailor   | stylestitch@gmail.com    | tailor123  |

---

## All Routes

| URL                          | Method   | Description                  |
|------------------------------|----------|------------------------------|
| /                            | GET      | Home page                    |
| /Login                       | GET/POST | Login                        |
| /Logout                      | GET      | Logout                       |
| /Registration                | GET/POST | Register new user            |
| /customer/dashboard          | GET      | Customer dashboard           |
| /customer/place-order        | GET/POST | Place a new order            |
| /customer/order-history      | GET      | View all orders              |
| /customer/order/cancel/<id>  | POST     | Cancel a pending order       |
| /customer/measurements       | GET/POST | View/save measurements       |
| /customer/find-tailor        | GET      | Browse tailors               |
| /customer/profile            | GET/POST | View/edit profile            |
| /customer/change-password    | POST     | Change password              |
| /tailor/dashboard            | GET      | Tailor dashboard             |
| /tailor/orders               | GET      | View assigned orders         |
| /tailor/order/update/<id>    | POST     | Accept/reject/complete order |
| /tailor/customers            | GET      | View tailor's customers      |
| /tailor/earnings             | GET      | View earnings summary        |
| /admin/dashboard             | GET      | Admin dashboard              |
| /admin/customers             | GET      | Manage all customers         |
| /admin/customers/delete/<id> | POST     | Delete a customer            |
| /admin/tailors               | GET      | Manage all tailors           |
| /admin/tailors/delete/<id>   | POST     | Delete a tailor              |
| /admin/orders                | GET      | Manage all orders            |
| /admin/orders/update/<id>    | POST     | Update order status          |
| /admin/reports               | GET      | Reports & analytics          |
| /api/tailors                 | GET      | JSON list of tailors         |
| /api/services                | GET      | JSON list of services        |
| /api/orders/<customer_id>    | GET      | JSON orders for a customer   |
