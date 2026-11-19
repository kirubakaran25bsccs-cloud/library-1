"""
Library Management System
Flask + SQLite college project.

Run:  python app.py
Open: http://127.0.0.1:5000
Login: admin / admin123
"""
import csv
import io
import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, Response, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "library.db")

LOAN_DAYS = 14          # how long a book can be kept
FINE_PER_DAY = 5        # fine in Rs. per late day

app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-submission"


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    isbn TEXT UNIQUE,
    category TEXT NOT NULL DEFAULT 'General',
    total_copies INTEGER NOT NULL DEFAULT 1,
    available_copies INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    department TEXT,
    joined_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id),
    member_id INTEGER NOT NULL REFERENCES members(id),
    issued_on TEXT NOT NULL,
    due_on TEXT NOT NULL,
    returned_on TEXT,
    fine INTEGER NOT NULL DEFAULT 0
);
"""

SEED_BOOKS = [
    ("Introduction to Algorithms", "Thomas H. Cormen", "9780262046305", "Computer Science", 4),
    ("Clean Code", "Robert C. Martin", "9780132350884", "Computer Science", 3),
    ("Database System Concepts", "Abraham Silberschatz", "9780078022159", "Computer Science", 3),
    ("Operating System Concepts", "Abraham Silberschatz", "9781119800361", "Computer Science", 2),
    ("Computer Networking: A Top-Down Approach", "James Kurose", "9780136681557", "Computer Science", 2),
    ("Engineering Mathematics", "K. A. Stroud", "9781352010275", "Mathematics", 5),
    ("Higher Engineering Mathematics", "B. S. Grewal", "9788174091550", "Mathematics", 4),
    ("Concepts of Physics", "H. C. Verma", "9788177091878", "Physics", 3),
    ("Wings of Fire", "A. P. J. Abdul Kalam", "9788173711466", "Biography", 3),
    ("The Discovery of India", "Jawaharlal Nehru", "9780143031031", "History", 2),
    ("Malgudi Days", "R. K. Narayan", "9788185986173", "Fiction", 3),
    ("Atomic Habits", "James Clear", "9781847941831", "Self Help", 2),
]

SEED_MEMBERS = [
    ("Aarav Kumar", "aarav@college.edu", "9876543210", "CSE"),
    ("Priya Sharma", "priya@college.edu", "9876501234", "ECE"),
    ("Karthik R", "karthik@college.edu", "9843012345", "MECH"),
    ("Divya Lakshmi", "divya@college.edu", "9790012345", "IT"),
]


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                   ("admin", generate_password_hash("admin123")))
        for title, author, isbn, cat, n in SEED_BOOKS:
            db.execute(
                "INSERT INTO books (title, author, isbn, category, total_copies, available_copies)"
                " VALUES (?,?,?,?,?,?)", (title, author, isbn, cat, n, n))
        for name, email, phone, dept in SEED_MEMBERS:
            db.execute(
                "INSERT INTO members (name, email, phone, department, joined_on) VALUES (?,?,?,?,?)",
                (name, email, phone, dept, date.today().isoformat()))
    db.commit()
    db.close()


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user"] = user["username"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") else url_for("dashboard"))
        flash("Wrong username or password. Try again.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You are signed out.", "info")
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def today_str():
    return date.today().isoformat()


def calc_fine(due_on, returned_on=None):
    """Fine = late days * FINE_PER_DAY. Uses today's date if not yet returned."""
    due = datetime.strptime(due_on, "%Y-%m-%d").date()
    end = datetime.strptime(returned_on, "%Y-%m-%d").date() if returned_on else date.today()
    late_days = (end - due).days
    return max(0, late_days) * FINE_PER_DAY


@app.template_filter("pretty_date")
def pretty_date(value):
    if not value:
        return "-"
    return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")


@app.context_processor
def inject_globals():
    return {"FINE_PER_DAY": FINE_PER_DAY, "LOAN_DAYS": LOAN_DAYS, "today": today_str()}


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    stats = {
        "titles": db.execute("SELECT COUNT(*) FROM books").fetchone()[0],
        "copies": db.execute("SELECT COALESCE(SUM(total_copies),0) FROM books").fetchone()[0],
        "members": db.execute("SELECT COUNT(*) FROM members").fetchone()[0],
        "on_loan": db.execute("SELECT COUNT(*) FROM issues WHERE returned_on IS NULL").fetchone()[0],
        "overdue": db.execute(
            "SELECT COUNT(*) FROM issues WHERE returned_on IS NULL AND due_on < ?",
            (today_str(),)).fetchone()[0],
        "fines": db.execute("SELECT COALESCE(SUM(fine),0) FROM issues").fetchone()[0],
    }
    categories = db.execute(
        "SELECT category, SUM(total_copies) AS n FROM books GROUP BY category ORDER BY n DESC"
    ).fetchall()
    overdue_rows = db.execute(
        """SELECT i.id, i.due_on, b.title, m.name FROM issues i
           JOIN books b ON b.id = i.book_id JOIN members m ON m.id = i.member_id
           WHERE i.returned_on IS NULL AND i.due_on < ? ORDER BY i.due_on LIMIT 6""",
        (today_str(),)).fetchall()
    overdue = [dict(r, fine=calc_fine(r["due_on"])) for r in overdue_rows]
    recent = db.execute(
        """SELECT i.issued_on, i.returned_on, b.title, m.name FROM issues i
           JOIN books b ON b.id = i.book_id JOIN members m ON m.id = i.member_id
           ORDER BY i.id DESC LIMIT 6""").fetchall()
    return render_template(
        "dashboard.html", stats=stats, overdue=overdue, recent=recent,
        chart_labels=[c["category"] for c in categories],
        chart_values=[c["n"] for c in categories])


# --------------------------------------------------------------------------
# Books
# --------------------------------------------------------------------------
@app.route("/books")
@login_required
def books():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sql, params = "SELECT * FROM books WHERE 1=1", []
    if q:
        sql += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
        params += [f"%{q}%"] * 3
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY title"
    db = get_db()
    rows = db.execute(sql, params).fetchall()
    cats = [r[0] for r in db.execute("SELECT DISTINCT category FROM books ORDER BY category")]
    return render_template("books.html", books=rows, q=q, category=category, categories=cats)


def read_book_form():
    f = request.form
    try:
        copies = int(f.get("total_copies", "1"))
    except ValueError:
        copies = 0
    data = {
        "title": f.get("title", "").strip(),
        "author": f.get("author", "").strip(),
        "isbn": f.get("isbn", "").strip() or None,
        "category": f.get("category", "").strip() or "General",
        "total_copies": copies,
    }
    error = None
    if not data["title"] or not data["author"]:
        error = "Title and author are required."
    elif copies < 1:
        error = "Copies must be a whole number of 1 or more."
    return data, error


@app.route("/books/add", methods=["GET", "POST"])
@login_required
def book_add():
    if request.method == "POST":
        data, error = read_book_form()
        if error:
            flash(error, "error")
            return render_template("book_form.html", book=data, mode="add")
        try:
            get_db().execute(
                "INSERT INTO books (title, author, isbn, category, total_copies, available_copies)"
                " VALUES (?,?,?,?,?,?)",
                (data["title"], data["author"], data["isbn"], data["category"],
                 data["total_copies"], data["total_copies"]))
            get_db().commit()
        except sqlite3.IntegrityError:
            flash("A book with this ISBN already exists.", "error")
            return render_template("book_form.html", book=data, mode="add")
        flash(f"Added \"{data['title']}\".", "success")
        return redirect(url_for("books"))
    return render_template("book_form.html", book={}, mode="add")


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@login_required
def book_edit(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not book:
        flash("Book not found.", "error")
        return redirect(url_for("books"))
    if request.method == "POST":
        data, error = read_book_form()
        on_loan = book["total_copies"] - book["available_copies"]
        if not error and data["total_copies"] < on_loan:
            error = f"{on_loan} copies are on loan, so total copies cannot be less than {on_loan}."
        if error:
            flash(error, "error")
            return render_template("book_form.html", book=dict(data, id=book_id), mode="edit")
        try:
            db.execute(
                "UPDATE books SET title=?, author=?, isbn=?, category=?, total_copies=?,"
                " available_copies=? WHERE id=?",
                (data["title"], data["author"], data["isbn"], data["category"],
                 data["total_copies"], data["total_copies"] - on_loan, book_id))
            db.commit()
        except sqlite3.IntegrityError:
            flash("A book with this ISBN already exists.", "error")
            return render_template("book_form.html", book=dict(data, id=book_id), mode="edit")
        flash("Book updated.", "success")
        return redirect(url_for("books"))
    return render_template("book_form.html", book=book, mode="edit")


@app.route("/books/<int:book_id>/delete", methods=["POST"])
@login_required
def book_delete(book_id):
    db = get_db()
    active = db.execute("SELECT COUNT(*) FROM issues WHERE book_id=? AND returned_on IS NULL",
                        (book_id,)).fetchone()[0]
    if active:
        flash("This book is on loan. Return it before deleting.", "error")
    else:
        db.execute("DELETE FROM issues WHERE book_id=?", (book_id,))
        db.execute("DELETE FROM books WHERE id=?", (book_id,))
        db.commit()
        flash("Book deleted.", "success")
    return redirect(url_for("books"))


# --------------------------------------------------------------------------
# Members
# --------------------------------------------------------------------------
@app.route("/members")
@login_required
def members():
    q = request.args.get("q", "").strip()
    sql = """SELECT m.*, (SELECT COUNT(*) FROM issues i
                          WHERE i.member_id = m.id AND i.returned_on IS NULL) AS on_loan
             FROM members m"""
    params = []
    if q:
        sql += " WHERE m.name LIKE ? OR m.email LIKE ? OR m.department LIKE ?"
        params = [f"%{q}%"] * 3
    sql += " ORDER BY m.name"
    return render_template("members.html", members=get_db().execute(sql, params).fetchall(), q=q)


def read_member_form():
    f = request.form
    data = {
        "name": f.get("name", "").strip(),
        "email": f.get("email", "").strip().lower(),
        "phone": f.get("phone", "").strip(),
        "department": f.get("department", "").strip(),
    }
    error = None
    if not data["name"] or not data["email"]:
        error = "Name and email are required."
    elif "@" not in data["email"]:
        error = "Enter a valid email address."
    elif data["phone"] and not data["phone"].replace("+", "").replace(" ", "").isdigit():
        error = "Phone number can contain digits only."
    return data, error


@app.route("/members/add", methods=["GET", "POST"])
@login_required
def member_add():
    if request.method == "POST":
        data, error = read_member_form()
        if not error:
            try:
                get_db().execute(
                    "INSERT INTO members (name, email, phone, department, joined_on) VALUES (?,?,?,?,?)",
                    (data["name"], data["email"], data["phone"], data["department"], today_str()))
                get_db().commit()
                flash(f"Added member {data['name']}.", "success")
                return redirect(url_for("members"))
            except sqlite3.IntegrityError:
                error = "A member with this email already exists."
        flash(error, "error")
        return render_template("member_form.html", member=data, mode="add")
    return render_template("member_form.html", member={}, mode="add")


@app.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
@login_required
def member_edit(member_id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
    if not member:
        flash("Member not found.", "error")
        return redirect(url_for("members"))
    if request.method == "POST":
        data, error = read_member_form()
        if not error:
            try:
                db.execute("UPDATE members SET name=?, email=?, phone=?, department=? WHERE id=?",
                           (data["name"], data["email"], data["phone"], data["department"], member_id))
                db.commit()
                flash("Member updated.", "success")
                return redirect(url_for("members"))
            except sqlite3.IntegrityError:
                error = "A member with this email already exists."
        flash(error, "error")
        return render_template("member_form.html", member=dict(data, id=member_id), mode="edit")
    return render_template("member_form.html", member=member, mode="edit")


@app.route("/members/<int:member_id>/delete", methods=["POST"])
@login_required
def member_delete(member_id):
    db = get_db()
    active = db.execute("SELECT COUNT(*) FROM issues WHERE member_id=? AND returned_on IS NULL",
                        (member_id,)).fetchone()[0]
    if active:
        flash("This member still has books on loan. Collect them first.", "error")
    else:
        db.execute("DELETE FROM issues WHERE member_id=?", (member_id,))
        db.execute("DELETE FROM members WHERE id=?", (member_id,))
        db.commit()
        flash("Member deleted.", "success")
    return redirect(url_for("members"))


# --------------------------------------------------------------------------
# Issue / Return
# --------------------------------------------------------------------------
@app.route("/issues")
@login_required
def issues():
    status = request.args.get("status", "active")
    sql = """SELECT i.*, b.title, m.name FROM issues i
             JOIN books b ON b.id = i.book_id JOIN members m ON m.id = i.member_id"""
    params = []
    if status == "active":
        sql += " WHERE i.returned_on IS NULL"
    elif status == "overdue":
        sql += " WHERE i.returned_on IS NULL AND i.due_on < ?"
        params.append(today_str())
    elif status == "returned":
        sql += " WHERE i.returned_on IS NOT NULL"
    sql += " ORDER BY i.id DESC"
    rows = []
    for r in get_db().execute(sql, params).fetchall():
        r = dict(r)
        r["overdue"] = r["returned_on"] is None and r["due_on"] < today_str()
        r["current_fine"] = r["fine"] if r["returned_on"] else calc_fine(r["due_on"])
        rows.append(r)
    return render_template("issues.html", issues=rows, status=status)


@app.route("/issues/new", methods=["GET", "POST"])
@login_required
def issue_new():
    db = get_db()
    if request.method == "POST":
        try:
            book_id = int(request.form.get("book_id", ""))
            member_id = int(request.form.get("member_id", ""))
        except ValueError:
            flash("Pick a book and a member.", "error")
            return redirect(url_for("issue_new"))
        book = db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        if not book or book["available_copies"] < 1:
            flash("No copies of this book are available right now.", "error")
            return redirect(url_for("issue_new"))
        dup = db.execute(
            "SELECT 1 FROM issues WHERE book_id=? AND member_id=? AND returned_on IS NULL",
            (book_id, member_id)).fetchone()
        if dup:
            flash("This member already has this book.", "error")
            return redirect(url_for("issue_new"))
        count = db.execute("SELECT COUNT(*) FROM issues WHERE member_id=? AND returned_on IS NULL",
                           (member_id,)).fetchone()[0]
        if count >= 3:
            flash("A member can borrow at most 3 books at a time.", "error")
            return redirect(url_for("issue_new"))
        due = (date.today() + timedelta(days=LOAN_DAYS)).isoformat()
        db.execute("INSERT INTO issues (book_id, member_id, issued_on, due_on) VALUES (?,?,?,?)",
                   (book_id, member_id, today_str(), due))
        db.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id=?", (book_id,))
        db.commit()
        flash(f"Issued \"{book['title']}\". Due on {pretty_date(due)}.", "success")
        return redirect(url_for("issues"))
    books_available = db.execute(
        "SELECT id, title, author, available_copies FROM books WHERE available_copies > 0 ORDER BY title"
    ).fetchall()
    members_all = db.execute("SELECT id, name, department FROM members ORDER BY name").fetchall()
    return render_template("issue_form.html", books=books_available, members=members_all)


@app.route("/issues/<int:issue_id>/return", methods=["POST"])
@login_required
def issue_return(issue_id):
    db = get_db()
    issue = db.execute("SELECT * FROM issues WHERE id=? AND returned_on IS NULL", (issue_id,)).fetchone()
    if not issue:
        flash("This loan was already closed.", "error")
        return redirect(url_for("issues"))
    fine = calc_fine(issue["due_on"])
    db.execute("UPDATE issues SET returned_on=?, fine=? WHERE id=?", (today_str(), fine, issue_id))
    db.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id=?", (issue["book_id"],))
    db.commit()
    flash(f"Book returned. Fine collected: Rs. {fine}." if fine else "Book returned. No fine.", "success")
    return redirect(url_for("issues"))


@app.route("/export/issues.csv")
@login_required
def export_issues():
    rows = get_db().execute(
        """SELECT i.id, b.title, m.name, i.issued_on, i.due_on, i.returned_on, i.fine
           FROM issues i JOIN books b ON b.id=i.book_id JOIN members m ON m.id=i.member_id
           ORDER BY i.id""").fetchall()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Issue ID", "Book", "Member", "Issued on", "Due on", "Returned on", "Fine (Rs.)"])
    for r in rows:
        writer.writerow(list(r))
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=issue_report.csv"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
