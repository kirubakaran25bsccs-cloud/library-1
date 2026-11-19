# Library Management System

A web application for managing a college library: books, members, issuing and returning, and fines.
Built with **Python (Flask)**, **SQLite** and plain HTML/CSS, with Chart.js for the dashboard chart.

## How to run in VS Code

1. Install Python 3.9 or newer from python.org (tick "Add Python to PATH").
2. In VS Code choose **File > Open Folder** and open this folder.
3. Open the terminal (**Terminal > New Terminal**) and run:

```
python -m venv venv
venv\Scripts\activate          (Windows)
source venv/bin/activate       (Mac / Linux)
pip install -r requirements.txt
python app.py
```

4. Open http://127.0.0.1:5000 in your browser.
5. Sign in with **admin / admin123**.

The database file `library.db` is created automatically on first run with sample books and members.
To reset everything, stop the app, delete `library.db`, and run `python app.py` again.
(Internet is needed only for the Google Fonts and the Chart.js chart.)

## Features

- Librarian login with hashed password and session handling
- Dashboard: totals, books on loan, overdue count, fines collected, category chart, overdue list, recent activity
- Books: add, edit, delete, search by title/author/ISBN, filter by category
- Members: add, edit, delete, search
- Issue and return: 14-day loan, fine of Rs. 5 per late day, maximum 3 books per member
- Loan list with tabs: on loan, overdue, returned, all
- Download all loans as a CSV report

## Business rules

| Rule | Where |
|---|---|
| Loan period 14 days | `LOAN_DAYS` in app.py |
| Fine Rs. 5 per day late | `FINE_PER_DAY` in app.py |
| Max 3 books per member | `issue_new()` in app.py |
| Cannot delete a book or member with an active loan | `book_delete()`, `member_delete()` |
| Cannot issue a book with no copies left | `issue_new()` |

## Project structure

```
library-management-system/
  app.py            routes, database, business logic
  requirements.txt
  library.db        created on first run
  static/style.css
  templates/        base, login, dashboard, books, members, issues and form pages
```

## Database tables

- **users** (id, username, password_hash)
- **books** (id, title, author, isbn, category, total_copies, available_copies)
- **members** (id, name, email, phone, department, joined_on)
- **issues** (id, book_id, member_id, issued_on, due_on, returned_on, fine)

## Ideas to extend it (for viva or extra marks)

- Student login and a "my books" page
- Email reminders before the due date
- Book reservation queue
- Barcode / QR scanning for issue and return
