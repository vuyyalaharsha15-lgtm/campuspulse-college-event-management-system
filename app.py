from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from flask import send_file

from reportlab.lib.colors import navy, gold, grey
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import inch
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

from datetime import date
import random
import json

app = Flask(__name__)
app.secret_key = "campuspulse_secret"


# 🔌 MySQL Connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Harsha@2009",   # Workbench password (usually empty in local system)
        database="campuspulse_db"
    )


# 🏠 Home Page
@app.route("/")
def home():
    return render_template("index.html")


# 🧾 REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form.get("full_name")
        email = request.form.get("email")
        student_id = request.form.get("student_id")
        department = request.form.get("department")
        phone = request.form.get("phone")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO students 
        (full_name, email, student_id, department, phone, password)
        VALUES (%s, %s, %s, %s, %s, %s)
        """

        values = (full_name, email, student_id, department, phone, password)

        cursor.execute(sql, values)
        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# 🔐 LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM students WHERE email=%s AND password=%s",
            (email, password)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]

            return redirect(url_for("student_dashboard"))
        else:
            return "Invalid Credentials ❌"

    return render_template("login.html")


# 🎓 STUDENT DASHBOARD
@app.route("/student_dashboard")
def student_dashboard():

    if "user_id" in session:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM students WHERE id=%s",
            (session["user_id"],)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        return render_template("student_dashboard.html", user=user)

    return redirect(url_for("login"))


# 🚪 LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/events")
def events():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM events ORDER BY event_date ASC")
    events = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("events.html", events=events)

# 📋 MY EVENTS
@app.route("/my_events")
def my_events():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT events.id,
               events.title,
               events.description,
               events.category,
               events.venue,
               events.event_date,
               events.event_time
        FROM registrations
        INNER JOIN events
        ON registrations.event_id = events.id
        WHERE registrations.student_id = %s
        ORDER BY events.event_date ASC
    """, (session["user_id"],))

    registered_events = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("my_events.html", events=registered_events)
# Register event 
@app.route("/register_event/<int:event_id>")
def register_event(event_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    student_id = session["user_id"]

    # already registered check
    cursor.execute("""
        SELECT 1 FROM registrations
        WHERE student_id=%s AND event_id=%s
    """, (student_id, event_id))

    if cursor.fetchone():
        return redirect(url_for("my_events"))

    # get fee
    cursor.execute("SELECT fee FROM events WHERE id=%s", (event_id,))
    event = cursor.fetchone()

    cursor.close()
    conn.close()

    if not event:
        return "Event not found"

    # FREE EVENT → direct registration
    if float(event["fee"]) == 0:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO registrations(student_id, event_id)
            VALUES(%s,%s)
        """, (student_id, event_id))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for("my_events"))

    # PAID → go to QR page ONLY
    return redirect(url_for("payment_page", event_id=event_id))

# payments page 
@app.route("/payment/<int:event_id>")
def payment_page(event_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM events WHERE id=%s", (event_id,))
    event = cursor.fetchone()

    cursor.close()
    conn.close()

    if not event:
        return "Event not found"

    return render_template(
        "payment.html",
        event=event
    )
# create payment 
@app.route("/create_payment/<int:event_id>")
def create_payment(event_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    student_id = session["user_id"]

    # prevent duplicate
    cursor.execute("""
        SELECT 1 FROM payments
        WHERE student_id=%s AND event_id=%s
    """, (student_id, event_id))

    if cursor.fetchone():
        return redirect(url_for("my_events"))

    cursor.execute("SELECT fee FROM events WHERE id=%s", (event_id,))
    event = cursor.fetchone()

    if not event:
        return "Event not found"

    import random
    txn = "TXN" + str(random.randint(100000, 999999))

    cursor.execute("""
        INSERT INTO payments
        (student_id, event_id, amount, payment_status, transaction_id, verified)
        VALUES (%s,%s,%s,'Pending',%s,0)
    """, (
        student_id,
        event_id,
        event["fee"],
        txn
    ))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("my_payments"))


@app.route("/payment_pending/<int:event_id>")
def payment_pending(event_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    student_id = session["user_id"]

    # prevent duplicate payment
    cursor.execute("""
        SELECT 1 FROM payments
        WHERE student_id=%s AND event_id=%s
    """, (student_id, event_id))

    if cursor.fetchone():
        cursor.close()
        conn.close()
        return redirect(url_for("my_events"))

    cursor.execute("SELECT fee FROM events WHERE id=%s", (event_id,))
    event = cursor.fetchone()

    amount = float(event[0]) if event else 0

    import random
    txn = "TXN" + str(random.randint(100000, 999999))

    cursor.execute("""
        INSERT INTO payments
        (student_id, event_id, amount, payment_status, transaction_id, verified)
        VALUES (%s,%s,%s,'Pending',%s,0)
    """, (student_id, event_id, amount, txn))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("my_payments"))
@app.route("/payment_success/<int:payment_id>")
def payment_success(payment_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get payment details
    cursor.execute("""
        SELECT student_id, event_id
        FROM payments
        WHERE id=%s
    """, (payment_id,))

    payment = cursor.fetchone()

    if not payment:
        cursor.close()
        conn.close()
        return "Payment not found"

    # Update payment as successful and verified
    cursor.execute("""
        UPDATE payments
        SET payment_status='Success',
            verified=1
        WHERE id=%s
    """, (payment_id,))

    # Check if already registered
    cursor.execute("""
        SELECT id
        FROM registrations
        WHERE student_id=%s
        AND event_id=%s
    """, (
        payment["student_id"],
        payment["event_id"]
    ))

    registration = cursor.fetchone()

    # Register student if not already registered
    if not registration:
        cursor.execute("""
            INSERT INTO registrations (student_id, event_id)
            VALUES (%s, %s)
        """, (
            payment["student_id"],
            payment["event_id"]
        ))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("my_payments"))

@app.route("/approve_payment/<int:payment_id>")
def approve_payment(payment_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get payment details
    cursor.execute("""
        SELECT student_id, event_id
        FROM payments
        WHERE id=%s
    """, (payment_id,))

    payment = cursor.fetchone()

    if not payment:
        cursor.close()
        conn.close()
        return "Payment not found"

    # Update payment status
    cursor.execute("""
        UPDATE payments
        SET payment_status='Success',
            verified=1
        WHERE id=%s
    """, (payment_id,))

    # Prevent duplicate registration
    cursor.execute("""
        SELECT *
        FROM registrations
        WHERE student_id=%s
        AND event_id=%s
    """, (
        payment["student_id"],
        payment["event_id"]
    ))

    exists = cursor.fetchone()

    if not exists:

        cursor.execute("""
            INSERT INTO registrations(student_id,event_id)
            VALUES(%s,%s)
        """, (
            payment["student_id"],
            payment["event_id"]
        ))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("transactions"))



@app.route("/payment_verified/<int:event_id>")
def payment_verified(event_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    student_id = session["user_id"]

    cursor.execute("""
        SELECT 1 FROM payments
        WHERE student_id=%s AND event_id=%s AND payment_status='Success'
    """, (student_id, event_id))

    if not cursor.fetchone():
        return "Payment not verified"

    cursor.execute("""
        SELECT 1 FROM registrations
        WHERE student_id=%s AND event_id=%s
    """, (student_id, event_id))

    if cursor.fetchone():
        return redirect(url_for("my_events"))

    cursor.execute("""
        INSERT INTO registrations (student_id, event_id)
        VALUES (%s,%s)
    """, (student_id, event_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("my_events"))

@app.route("/my_payments")
def my_payments():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            payments.id,
            payments.transaction_id,
            payments.amount,
            payments.payment_status,
            payments.payment_date,
            payments.verified,
            events.title
        FROM payments
        JOIN events ON payments.event_id = events.id
        WHERE payments.student_id = %s
        ORDER BY payments.payment_date DESC
    """, (session["user_id"],))

    payments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("my_payments.html", payments=payments)
# ===========================
# ADMIN LOGIN
# ===========================

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM admins WHERE email=%s AND password=%s",
            (email, password)
        )

        admin = cursor.fetchone()

        cursor.close()
        conn.close()

        if admin:

            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["username"]

            return redirect(url_for("admin_dashboard"))

        else:

            return "Invalid Admin Credentials ❌"

    return render_template("admin_login.html")

@app.route("/admin_dashboard")
def admin_dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Dashboard stats
    cursor.execute("SELECT COUNT(*) AS total FROM students")
    total_students = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM events")
    total_events = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM registrations")
    total_registrations = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM certificates")
    total_certificates = cursor.fetchone()["total"]

    cursor.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_students=total_students,
        total_events=total_events,
        total_registrations=total_registrations,
        total_certificates=total_certificates
    )

@app.route("/transactions")
def transactions():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT payments.*,
               students.full_name,
               students.student_id,
               events.title
        FROM payments
        JOIN students ON payments.student_id = students.id
        JOIN events ON payments.event_id = events.id
        ORDER BY payments.id DESC
    """)

    payments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("transactions.html", payments=payments)

@app.route("/admin_payments")
def admin_payments():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT payments.*,
               students.full_name,
               events.title
        FROM payments
        JOIN students ON payments.student_id = students.id
        JOIN events ON payments.event_id = events.id
        ORDER BY payments.id DESC
    """)

    payments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin_payments.html", payments=payments)

# ==========================================
# REPORTS DASHBOARD
# ==========================================
import json

@app.route("/reports")
def reports():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ========= CARDS =========

    cursor.execute("SELECT COUNT(*) total FROM students")
    total_students = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) total FROM events")
    total_events = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) total FROM registrations")
    total_registrations = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) total FROM certificates")
    total_certificates = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) total FROM payments")
    total_payments = cursor.fetchone()["total"]

    # ========= SUCCESS PAYMENTS =========

    cursor.execute("""
        SELECT COUNT(*) total
        FROM payments
        WHERE payment_status='Success'
    """)
    success_payments = cursor.fetchone()["total"]

    # ========= PENDING PAYMENTS =========

    cursor.execute("""
        SELECT COUNT(*) total
        FROM payments
        WHERE payment_status='Pending'
    """)
    pending_payments = cursor.fetchone()["total"]

    # ========= REVENUE =========

    cursor.execute("""
        SELECT IFNULL(SUM(amount),0) revenue
        FROM payments
        WHERE payment_status='Success'
    """)
    revenue = cursor.fetchone()["revenue"]

    # ========= ATTENDANCE =========

    cursor.execute("""
        SELECT COUNT(*) total
        FROM attendance
        WHERE status='Present'
    """)
    present = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) total
        FROM attendance
        WHERE status='Absent'
    """)
    absent = cursor.fetchone()["total"]

    # ========= EVENT REPORT =========

    cursor.execute("""
        SELECT
            events.title,
            COUNT(registrations.id) AS registrations,
            IFNULL(SUM(payments.amount),0) AS revenue

        FROM events

        LEFT JOIN registrations
        ON events.id=registrations.event_id

        LEFT JOIN payments
        ON events.id=payments.event_id
        AND payments.payment_status='Success'

        GROUP BY events.id

        ORDER BY events.event_date DESC
    """)

    event_reports = cursor.fetchall()
    # ========= RECENT PAYMENTS =========

    cursor.execute("""
    SELECT
    students.full_name,
    events.title,
    payments.amount,
    payments.payment_status,
    payments.payment_date

   FROM payments

   JOIN students
    ON students.id = payments.student_id

    JOIN events
    ON events.id = payments.event_id

    ORDER BY payments.payment_date DESC

    LIMIT 10
    """)

    recent_payments = cursor.fetchall()


    # ========= RECENT EVENTS =========

    cursor.execute("""
    SELECT
        title,
        category,
        event_date,
        status

    FROM events

    ORDER BY event_date DESC

    LIMIT 10
    """)

    recent_events = cursor.fetchall()


    # ========= PAYMENT CHART =========

    payment_labels = ["Success", "Pending"]

    payment_values = [
        success_payments,
        pending_payments
    ]


    # ========= EVENT CHART =========

    event_labels = []
    event_values = []

    for row in event_reports:
        event_labels.append(row["title"])
        event_values.append(row["registrations"])

    cursor.close()
    conn.close()

    overview_labels = [
    "Students",
    "Events",
    "Registrations",
    "Certificates"
     ]

    overview_values = [
    total_students,
    total_events,
    total_registrations,
    total_certificates
    ]

    return render_template(
        "reports.html",

        total_students=total_students,
        total_events=total_events,
        total_registrations=total_registrations,
        total_certificates=total_certificates,
        total_payments=total_payments,

        success_payments=success_payments,
        pending_payments=pending_payments,

        present=present,
        absent=absent,

        revenue=revenue,
        total_revenue=revenue,

        event_reports=event_reports,

        recent_payments=recent_payments,
        recent_events=recent_events,

        payment_labels=json.dumps(payment_labels),
        payment_values=json.dumps(payment_values),

        event_labels=json.dumps(event_labels),
        event_values=json.dumps(event_values),

        overview_labels=json.dumps(overview_labels),
        overview_values=json.dumps(overview_values)

    )    

# ===========================
# ADD EVENT
# ===========================

@app.route("/add_event", methods=["GET", "POST"])
def add_event():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":

        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")
        venue = request.form.get("venue")
        event_date = request.form.get("event_date")
        event_time = request.form.get("event_time")
        coordinator_id = request.form.get("coordinator_id")
        max_participants = request.form.get("max_participants")

        # NEW
        fee = request.form.get("fee")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO events
            (
                title,
                description,
                category,
                venue,
                event_date,
                event_time,
                coordinator_id,
                max_participants,
                fee
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            title,
            description,
            category,
            venue,
            event_date,
            event_time,
            coordinator_id,
            max_participants,
            fee
        ))

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("admin_dashboard"))

    return render_template("add_event.html")

# ===========================
# MANAGE EVENTS
# ===========================

@app.route("/manage_events")
def manage_events():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM events
        ORDER BY event_date ASC
    """)

    events = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "manage_events.html",
        events=events
    )
# ===========================
# EDIT EVENT
# ===========================

@app.route("/edit_event/<int:event_id>", methods=["GET", "POST"])
def edit_event(event_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":

        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")
        venue = request.form.get("venue")
        event_date = request.form.get("event_date")
        event_time = request.form.get("event_time")
        max_participants = request.form.get("max_participants")
        status = request.form.get("status")

        cursor.execute("""
            UPDATE events
            SET
                title=%s,
                description=%s,
                category=%s,
                venue=%s,
                event_date=%s,
                event_time=%s,
                max_participants=%s,
                status=%s
            WHERE id=%s
        """,
        (
            title,
            description,
            category,
            venue,
            event_date,
            event_time,
            max_participants,
            status,
            event_id
        ))

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("manage_events"))

    cursor.execute(
        "SELECT * FROM events WHERE id=%s",
        (event_id,)
    )

    event = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "edit_event.html",
        event=event
    )

# # ===========================
# DELETE EVENT
# ===========================
@app.route("/delete_event/<int:event_id>")
def delete_event(event_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Attendance
        cursor.execute("DELETE FROM attendance WHERE event_id=%s", (event_id,))

        # 2. Certificates
        cursor.execute("DELETE FROM certificates WHERE event_id=%s", (event_id,))

        # 3. Feedback
        cursor.execute("DELETE FROM feedback WHERE event_id=%s", (event_id,))

        # 4. Payments
        cursor.execute("DELETE FROM payments WHERE event_id=%s", (event_id,))

        # 5. Registrations
        cursor.execute("DELETE FROM registrations WHERE event_id=%s", (event_id,))

        # 6. Delete Event
        cursor.execute("DELETE FROM events WHERE id=%s", (event_id,))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return f"Error: {str(e)}"

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("manage_events"))
# ===========================
# VIEW STUDENTS
# ===========================
@app.route("/students", methods=["GET"])
def view_students():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    search = request.args.get("search")

    if search:
        cursor.execute("""
            SELECT * FROM students
            WHERE full_name LIKE %s
               OR department LIKE %s
               OR student_id LIKE %s
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        cursor.execute("SELECT * FROM students")

    students = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("students.html", students=students)

# ===========================
# REGISTRATIONS MANAGEMENT
# ===========================

@app.route("/registrations", methods=["GET"])
def registrations():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    search = request.args.get("search")

    if search:

        cursor.execute("""
            SELECT
                registrations.id,
                students.full_name,
                students.student_id,
                events.title,
                events.category,
                events.event_date
            FROM registrations
            INNER JOIN students
                ON registrations.student_id = students.id
            INNER JOIN events
                ON registrations.event_id = events.id
            WHERE students.full_name LIKE %s
               OR students.student_id LIKE %s
               OR events.title LIKE %s
            ORDER BY events.event_date ASC
        """,
        (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ))

    else:

        cursor.execute("""
            SELECT
                registrations.id,
                students.full_name,
                students.student_id,
                events.title,
                events.category,
                events.event_date
            FROM registrations
            INNER JOIN students
                ON registrations.student_id = students.id
            INNER JOIN events
                ON registrations.event_id = events.id
            ORDER BY events.event_date ASC
        """)

    registrations = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "registrations.html",
        registrations=registrations
    )

# ===========================
# DELETE REGISTRATION
# ===========================

@app.route("/delete_registration/<int:registration_id>")
def delete_registration(registration_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM registrations WHERE id=%s",
        (registration_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("registrations"))

# ===========================
# CERTIFICATES
# ===========================

@app.route("/certificates")
def certificates():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            certificates.id,
            students.full_name,
            students.student_id,
            events.title,
            certificates.certificate_no,
            certificates.issue_date
        FROM certificates
        JOIN students
            ON certificates.student_id = students.id
        JOIN events
            ON certificates.event_id = events.id
        ORDER BY certificates.issue_date DESC
    """)

    certificates = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "certificates.html",
        certificates=certificates
    )
# ===========================
# ATTENDANCE
# ===========================
@app.route("/attendance")
def attendance():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            registrations.student_id,
            students.full_name,
            students.student_id AS roll_no,
            events.id AS event_id,
            events.title,
            COALESCE(attendance.status, 'Not Marked') AS status
        FROM registrations
        JOIN students
            ON registrations.student_id = students.id
        JOIN events
            ON registrations.event_id = events.id
        LEFT JOIN attendance
            ON attendance.student_id = registrations.student_id
            AND attendance.event_id = registrations.event_id
        ORDER BY events.title
    """)

    attendance = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "attendance.html",
        attendance=attendance
    )
# ===========================
# MARK ATTENDANCE
# ===========================

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    student_id = request.form["student_id"]
    event_id = request.form["event_id"]
    status = request.form["status"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM attendance
        WHERE student_id=%s
        AND event_id=%s
    """, (student_id, event_id))

    existing = cursor.fetchone()

    if existing:

        cursor.execute("""
            UPDATE attendance
            SET status=%s
            WHERE student_id=%s
            AND event_id=%s
        """, (status, student_id, event_id))

    else:

        cursor.execute("""
            INSERT INTO attendance
            (student_id,event_id,status)
            VALUES(%s,%s,%s)
        """, (student_id, event_id, status))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("attendance"))

# ===========================
# GENERATE CERTIFICATE
# ===========================
@app.route("/generate_certificate/<int:student_id>/<int:event_id>")
def generate_certificate(student_id, event_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Check attendance FIRST (IMPORTANT)
    cursor.execute("""
        SELECT status
        FROM attendance
        WHERE student_id=%s AND event_id=%s
    """, (student_id, event_id))

    attendance = cursor.fetchone()

    # 🔥 THIS IS STEP 3 FIX (VERY IMPORTANT)
    if attendance is None or attendance["status"] != "Present":
        cursor.close()
        conn.close()
        return "❌ Cannot generate certificate for Absent student"

    # 2. Check duplicate certificate
    cursor.execute("""
        SELECT *
        FROM certificates
        WHERE student_id=%s AND event_id=%s
    """, (student_id, event_id))

    existing = cursor.fetchone()

    if existing:
        cursor.close()
        conn.close()
        return redirect(url_for("certificates"))

    # 3. Generate certificate
    import random
    from datetime import date

    certificate_no = "CP-" + str(random.randint(100000, 999999))

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO certificates
        (student_id, event_id, certificate_no, issue_date)
        VALUES (%s, %s, %s, %s)
    """, (
        student_id,
        event_id,
        certificate_no,
        date.today()
    ))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("certificates"))

# ===========================
# MY CERTIFICATES
# ===========================
@app.route("/my_certificates")
def my_certificates():

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            certificates.student_id,
            certificates.event_id,
            certificates.certificate_no,
            certificates.issue_date,
            events.title
        FROM certificates
        JOIN events ON certificates.event_id = events.id
        WHERE certificates.student_id = %s
    """, (session["user_id"],))

    certificates = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("my_certificates.html", certificates=certificates)
   # PDF GENERATE ROUTE  
@app.route("/download_certificate/<int:student_id>/<int:event_id>")
def download_certificate(student_id, event_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            certificates.certificate_no,
            certificates.issue_date,
            students.full_name,
            events.title
        FROM certificates
        JOIN students
            ON certificates.student_id = students.id
        JOIN events
            ON certificates.event_id = events.id
        WHERE certificates.student_id=%s
        AND certificates.event_id=%s
    """, (student_id, event_id))

    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return "Certificate not found"

    # ==========================
# PDF CANVAS
# ==========================

    file_path = f"certificate_{student_id}_{event_id}.pdf"

    c = canvas.Canvas(file_path, pagesize=A4)

    width, height = A4

    blue = HexColor("#0B3D91")
    yellow = HexColor("#F4B400")
    light = HexColor("#FFFDF7")
    dark = HexColor("#1B1B1B")

    # ==========================
    # Background
    # ==========================

    c.setFillColor(light)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # ==========================
    # Double Border
    # ==========================

    c.setStrokeColor(yellow)
    c.setLineWidth(7)
    c.rect(18, 18, width-36, height-36)

    c.setStrokeColor(blue)
    c.setLineWidth(2)
    c.rect(28, 28, width-56, height-56)

    # ==========================
    # Decorative Top Lines
    # ==========================

    c.setStrokeColor(yellow)
    c.setLineWidth(4)
    c.line(40, height-40, width-40, height-40)

    c.setStrokeColor(blue)
    c.setLineWidth(2)
    c.line(40, height-48, width-40, height-48)

    # ==========================
    # Logo
    # ==========================

    logo_path = os.path.join(app.root_path, "static", "images", "logo.png")

    if os.path.isfile(logo_path):

        c.drawImage(
            logo_path,
            width/2-70,
            height-170,
            width=140,
            height=140,
            preserveAspectRatio=True,
            mask='auto'
        )

    # ==========================
    # Watermark
    # ==========================

    if os.path.isfile(logo_path):

        c.saveState()

        try:
            c.setFillAlpha(0.06)
        except:
            pass

        c.translate(width/2, height/2)
        c.rotate(30)

        c.drawImage(
            logo_path,
            -170,
            -170,
            width=340,
            height=340,
            preserveAspectRatio=True,
            mask='auto'
        )

        c.restoreState()

    # ==========================
    # Title
    # ==========================

    c.setFillColor(blue)

    c.setFont("Helvetica-Bold", 36)

    c.drawCentredString(
        width/2,
        height-210,
        "CERTIFICATE"
    )

    c.setFillColor(yellow)

    c.setFont("Helvetica", 22)

    c.drawCentredString(
        width/2,
        height-240,
        "OF PARTICIPATION"
    )

    # ==========================
    # Body
    # ==========================

    c.setFillColor(dark)

    c.setFont("Helvetica", 18)

    c.drawCentredString(
        width/2,
        height-300,
        "This is to certify that"
    )

    c.setStrokeColor(yellow)
    c.line(120, height-330, width-120, height-330)

    c.setFillColor(blue)

    c.setFont("Helvetica-Bold", 28)

    c.drawCentredString(
        width/2,
        height-360,
        data["full_name"]
    )

    c.setFillColor(dark)

    c.setFont("Helvetica", 18)

    c.drawCentredString(
        width/2,
        height-410,
        "has successfully participated in"
    )

    c.setFillColor(blue)

    c.setFont("Helvetica-Bold", 24)

    c.drawCentredString(
        width/2,
        height-445,
        data["title"]
    )

    c.setFillColor(dark)

    c.setFont("Helvetica", 16)

    c.drawCentredString(
        width/2,
        height-480,
        "organized by CampusPulse."
    )

    # ==========================
    # Certificate Details
    # ==========================

    c.setStrokeColor(blue)
    c.line(120, height-520, width-120, height-520)

    c.setFillColor(blue)

    c.setFont("Helvetica-Bold", 15)

    c.drawString(95, height-555, "Certificate No.")

    c.drawString(335, height-555, "Issue Date")

    c.setFont("Helvetica", 15)

    c.drawString(
        95,
        height-580,
        data["certificate_no"]
    )

    c.drawString(
        335,
        height-580,
        str(data["issue_date"])
    )
    
        # ==========================
    # QR Code
    # ==========================

    verify_text = f"""
CampusPulse Certificate

Student : {data['full_name']}
Event : {data['title']}
Certificate : {data['certificate_no']}
Issue Date : {data['issue_date']}
"""

    img = qrcode.make(verify_text)

    qr_path = "qr_temp.png"

    img.save(qr_path)

    c.drawImage(
        qr_path,
        width-145,
        170,
        width=80,
        height=80
    )

    c.setFillColor(blue)
    c.setFont("Helvetica",9)

    c.drawCentredString(
        width-105,
        160,
        "Scan to Verify"
    )

    # ==========================
    # Gold Seal
    # ==========================

    c.setFillColor(yellow)

    c.circle(
        width/2,
        165,
        35,
        fill=1
    )

    c.setFillColor(blue)

    c.setFont("Helvetica-Bold",18)

    c.drawCentredString(
        width/2,
        160,
        "★"
    )

    c.setFont("Helvetica-Bold",9)

    c.drawCentredString(
        width/2,
        142,
        "CAMPUSPULSE"
    )

    # ==========================
    # Signature Lines
    # ==========================

    c.setStrokeColor(blue)

    c.line(80,110,220,110)
    c.line(width-220,110,width-80,110)

    c.setFont("Helvetica-Bold",12)

    c.drawCentredString(
        150,
        95,
        "Coordinator"
    )

    c.drawCentredString(
        width-150,
        95,
        "Principal"
    )

    c.setFont("Helvetica-Oblique",10)

    c.drawCentredString(
        150,
        125,
        "________________"
    )

    c.drawCentredString(
        width-150,
        125,
        "________________"
    )

    # ==========================
    # Footer
    # ==========================

    # ==========================
# Footer
# ==========================

    c.setStrokeColor(yellow)
    c.setLineWidth(2)

    # Footer line
    c.line(50, 65, width-50, 65)

    c.setFillColor(blue)

    # First line
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(
        width/2,
        48,
        "CampusPulse - Smart Event Management System"
    )

    # Second line
    c.setFont("Helvetica", 8)
    c.drawCentredString(
        width/2,
        34,
        "This certificate is computer generated and officially issued by CampusPulse."
    )
    # ==========================
    # SAVE PDF
    # ==========================

    c.save()

    if os.path.exists(qr_path):
        os.remove(qr_path)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"{data['full_name']}_Certificate.pdf"
    )

if __name__ == "__main__":
    app.run(debug=True)
