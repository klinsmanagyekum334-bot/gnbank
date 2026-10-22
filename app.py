import os
import uuid
import mysql.connector
from datetime import datetime, timezone
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g, jsonify
)

app = Flask(__name__)
app.secret_key = "canteen-secret-2026-change-me"

# ============================================================
# CONFIG & UPLOADS
# ============================================================
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
ALLOWED_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================================
# MYSQL CONFIG
# ============================================================
DB_CONFIG = {
    "host": "localhost",
    "user": "canteen_user",
    "password": "Klinsman@ophyser1", 
    "database": "canteen_db"
}

MANAGER_PASSWORD = "0987654321"
MASTER_PASSWORD  = "Klinsman@ophyser1"

CLASS_OPTIONS = [
    "Creche", "Nursery", "KG 1", "KG 2", 
    "Class 1", "Class 2", "Class 3", "Class 4", 
    "Class 5", "Class 6", 
    "ALL (Canteen Collector)", 
    "MASTER"
]

STUDENT_CLASSES = [
    "Creche", "Nursery", "KG 1", "KG 2", 
    "Class 1", "Class 2", "Class 3", "Class 4", 
    "Class 5", "Class 6"
]

# ============================================================
# DATABASE HELPERS
# ============================================================
def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(**DB_CONFIG)
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def save_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTS:
        return None
    
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file_storage.save(filepath)
    
    return url_for('static', filename=f'uploads/{filename}')

def get_today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ============================================================
# AUTH & DECORATORS
# ============================================================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def manager_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in") or session.get("role") not in ["MANAGER", "MASTER"]:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def canteen_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        role = session.get("role", "")
        if role in ["MANAGER", "MASTER"] or "Canteen" in role or "ALL" in role:
            return f(*args, **kwargs)
        return redirect(url_for("login"))
    return wrapper

def teacher_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        role = session.get("role", "")
        if role in ["MANAGER", "MASTER"] or role in STUDENT_CLASSES:
            return f(*args, **kwargs)
        return redirect(url_for("login"))
    return wrapper


# ============================================================
# PUBLIC ROUTES
# ============================================================
@app.route("/")
def index():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT `key`, `value` FROM site_content")
    rows = cursor.fetchall()
    site = {r["key"]: r["value"] for r in rows}
    cursor.close()
    return render_template("index.html", site=site)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        class_name = request.form.get("class_name", "").strip()
        phone = request.form.get("phone", "").strip()
        
        if not all([full_name, username, password, confirm_password, class_name, phone]):
            flash("All fields are required.", "error")
            return redirect(url_for("signup"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("signup"))

        image_url = ""
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename:
                image_url = save_upload(file)

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (full_name, username, password, role, phone, image, is_approved) VALUES (%s, %s, %s, %s, %s, %s, 0)",
                (full_name, username, password, class_name, phone, image_url)
            )
            db.commit()
            flash("Signup submitted! Pending manager approval.", "success")
            return redirect(url_for("index"))
        except mysql.connector.IntegrityError:
            flash("Username already exists.", "error")
            return redirect(url_for("signup"))
        finally:
            cursor.close()
    
    return render_template("signup.html", classes=CLASS_OPTIONS)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        if password == MASTER_PASSWORD:
            session["logged_in"] = True
            session["username"] = username or "master"
            session["role"] = "MASTER"
            return redirect(url_for("manager_pending"))

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()

        if user:
            if not user["is_approved"]:
                error = "Your account is pending approval."
            else:
                session["logged_in"] = True
                session["username"] = user["username"]
                session["role"] = user["role"]
                session["full_name"] = user["full_name"]
                
                if user["role"] in ["MANAGER", "MASTER"]:
                    return redirect(url_for("manager_pending"))
                elif "Canteen" in user["role"] or "ALL" in user["role"]:
                    return redirect(url_for("canteen_page"))
                elif user["role"] in STUDENT_CLASSES:
                    return redirect(url_for("teacher_page"))
                else:
                    return redirect(url_for("index"))
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    error = None
    if request.method == "POST":
        old_pass = request.form.get("old_password", "")
        new_pass = request.form.get("new_password", "")
        confirm_pass = request.form.get("confirm_password", "")

        if new_pass != confirm_pass:
            error = "New passwords do not match."
        else:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (session["username"],))
            user = cursor.fetchone()
            
            if user and user["password"] == old_pass:
                cursor.execute("UPDATE users SET password = %s WHERE id = %s", (new_pass, user["id"]))
                db.commit()
                cursor.close()
                flash("Password updated successfully!", "success")
                if session["role"] in ["MANAGER", "MASTER"]:
                    return redirect(url_for("manager_pending"))
                elif session["role"] in STUDENT_CLASSES:
                    return redirect(url_for("teacher_page"))
                else:
                    return redirect(url_for("canteen_page"))
            else:
                cursor.close()
                error = "Incorrect old password."

    return render_template("change_password.html", error=error)


# ============================================================
# MANAGER ROUTES
# ============================================================
@app.context_processor
def inject_pending():
    if session.get("role") in ["MANAGER", "MASTER"]:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_approved = 0")
        count = cursor.fetchone()[0]
        cursor.close()
        return dict(pending_count=count)
    return dict(pending_count=0)

@app.route("/manager")
@manager_required
def manager_home():
    return redirect(url_for("manager_pending"))

@app.route("/manager/pending")
@manager_required
def manager_pending():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE is_approved = 0")
    pending = cursor.fetchall()
    cursor.close()
    return render_template("manager_pending.html", pending=pending)

@app.route("/manager/staff")
@manager_required
def manager_staff():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE is_approved = 1 AND role != 'MANAGER'")
    staff = cursor.fetchall()
    cursor.close()
    return render_template("manager_staff.html", staff=staff)

@app.route("/manager/pending/approve", methods=["POST"])
@manager_required
def manager_approve():
    user_id = request.form.get("user_id")
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE users SET full_name=%s, username=%s, role=%s, phone=%s, is_approved=1 WHERE id=%s",
        (request.form.get("full_name"), request.form.get("username"), request.form.get("class_name"), request.form.get("phone"), user_id)
    )
    db.commit()
    cursor.close()
    flash("User approved successfully.")
    return redirect(url_for("manager_pending"))

@app.route("/manager/pending/delete", methods=["POST"])
@manager_required
def manager_delete():
    user_id = request.form.get("user_id")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()
    cursor.close()
    flash("Signup request deleted.")
    return redirect(url_for("manager_pending"))

@app.route("/manager/home", methods=["GET", "POST"])
@manager_required
def manager_edit_home():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    if request.method == "POST":
        updates = {
            "welcome_title": request.form.get("welcome_title", "").strip(),
            "welcome_brand": request.form.get("welcome_brand", "").strip(),
            "welcome_text":  request.form.get("welcome_text", "").strip(),
        }
        
        for k, v in updates.items():
            cursor.execute("UPDATE site_content SET `value`=%s WHERE `key`=%s", (v, k))

        uploaded_image = save_upload(request.files.get("welcome_image_file"))
        if uploaded_image:
            cursor.execute("UPDATE site_content SET `value`=%s WHERE `key`=%s", (uploaded_image, "welcome_image"))
            
        if request.form.get("remove_image") == "on":
            cursor.execute("UPDATE site_content SET `value`='' WHERE `key`='welcome_image'")

        db.commit()
        cursor.close()
        flash("Home page updated.")
        return redirect(url_for("manager_edit_home"))

    cursor.execute("SELECT `key`, `value` FROM site_content")
    rows = cursor.fetchall()
    site = {r["key"]: r["value"] for r in rows}
    cursor.close()
    return render_template("manager_home.html", site=site)


# ============================================================
# CANTEEN ROUTES
# ============================================================
@app.route("/canteen")
@canteen_required
def canteen_page():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    today = get_today_str()
    
    cursor.execute("SELECT * FROM students ORDER BY student_id")
    student_rows = cursor.fetchall()
    
    cursor.execute("SELECT student_id, amount FROM collections WHERE collection_date = %s", (today,))
    collections = cursor.fetchall()
    today_dict = {c["student_id"]: c["amount"] for c in collections}
    
    today_total = sum(today_dict.values())
    
    cursor.execute("SELECT student_id, SUM(amount) as total FROM collections GROUP BY student_id")
    totals_rows = cursor.fetchall()
    totals_dict = {t["student_id"]: t["total"] for t in totals_rows}
    
    student_list = []
    for s in student_rows:
        sid = s["student_id"]
        student_list.append({
            "id": sid,
            "name": s["name"],
            "class_name": s["class_name"],
            "gender": s["gender"],
            "guardian_phone": s["guardian_phone"],
            "residence": s["residence"],
            "picture": s["picture"],
            "today_amount": today_dict.get(sid, ""),
            "lifetime_total": totals_dict.get(sid, 0.0)
        })
        
    cursor.close()
    return render_template(
        "canteen_collector.html",
        students=student_list,
        current_date=today,
        current_time=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        class_options=STUDENT_CLASSES,
        today_total=today_total
    )

@app.route("/canteen/save", methods=["POST"])
@canteen_required
def canteen_save():
    db = get_db()
    cursor = db.cursor()
    today = get_today_str()
    current_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
    
    saved_count = 0
    for key, value in request.form.items():
        if key.startswith("amount_") and value.strip():
            student_id = key.replace("amount_", "")
            try:
                amount = float(value)
                
                cursor.execute(
                    "SELECT id FROM collections WHERE collection_date=%s AND student_id=%s", 
                    (today, student_id)
                )
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute("UPDATE collections SET amount=%s, collection_time=%s WHERE id=%s", (amount, current_time, existing[0]))
                else:
                    cursor.execute(
                        "INSERT INTO collections (collection_date, collection_time, student_id, amount) VALUES (%s, %s, %s, %s)",
                        (today, current_time, student_id, amount)
                    )
                saved_count += 1
            except ValueError:
                pass 
                
    db.commit()
    cursor.close()
    flash(f"Saved {saved_count} entries for {today}.", "success")
    return redirect(url_for("canteen_page"))

@app.route("/canteen/add-student", methods=["POST"])
@canteen_required
def canteen_add_student():
    db = get_db()
    cursor = db.cursor()
    name = request.form.get("name", "").strip()
    class_name = request.form.get("class_name", "").strip()
    gender = request.form.get("gender", "").strip()
    phone = request.form.get("guardian_phone", "").strip()
    residence = request.form.get("residence", "").strip()
    
    if not name or not class_name or not gender:
        flash("Name, Class, and Gender are required.", "error")
        return redirect(url_for("canteen_page"))

    picture_url = ""
    if 'picture' in request.files:
        file = request.files['picture']
        if file and file.filename:
            picture_url = save_upload(file)

    cursor.execute("SELECT student_id FROM students ORDER BY student_id DESC LIMIT 1")
    last_student = cursor.fetchone()
    
    if last_student:
        try:
            last_num = int(last_student[0].replace("GW", ""))
            new_id = f"GW{last_num + 1:03d}"
        except ValueError:
            cursor.execute('SELECT COUNT(*) FROM students')
            new_id = f"GW{cursor.fetchone()[0] + 1:03d}"
    else:
        new_id = "GW001"

    try:
        cursor.execute(
            "INSERT INTO students (student_id, name, class_name, gender, guardian_phone, residence, picture) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (new_id, name, class_name, gender, phone, residence, picture_url)
        )
        db.commit()
        flash(f"Student {name} added successfully. Code: {new_id}", "success")
    except Exception as e:
        flash(f"Error adding student: {str(e)}", "error")
    finally:
        cursor.close()
        
    return redirect(url_for("canteen_page"))

@app.route("/canteen/view")
@canteen_required
def canteen_view_student():
    student_id = request.args.get("student_id")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
    student = cursor.fetchone()
    
    if not student:
        cursor.close()
        flash("Student not found.", "error")
        return redirect(url_for("canteen_page"))
        
    cursor.execute(
        "SELECT * FROM collections WHERE student_id = %s ORDER BY collection_date DESC, collection_time DESC", 
        (student_id,)
    )
    records = cursor.fetchall()
    cursor.close()
    
    total_paid = sum(r["amount"] for r in records)
    
    return render_template(
        "student_view.html", 
        student=student, 
        records=records, 
        total_paid=total_paid,
        back_url=url_for('canteen_page')
    )

@app.route("/canteen/delete-student", methods=["POST"])
@canteen_required
def canteen_delete_student():
    student_id = request.form.get("student_id")
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM collections WHERE student_id=%s", (student_id,))
    has_collections = cursor.fetchone()[0]
    
    if has_collections > 0:
        flash("Cannot delete student because they have existing payment records.", "error")
    else:
        cursor.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
        db.commit()
        flash("Student deleted successfully.", "success")
        
    cursor.close()
    return redirect(url_for("canteen_page"))


# ============================================================
# TEACHER ROUTES
# ============================================================
@app.route("/teacher")
@teacher_required
def teacher_page():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    today = get_today_str()
    teacher_class = session.get("role")
    teacher_name = session.get("full_name")
    
    cursor.execute("SELECT * FROM students WHERE class_name = %s ORDER BY student_id", (teacher_class,))
    student_rows = cursor.fetchall()
    cursor.close()
    
    student_list = []
    for s in student_rows:
        student_list.append({
            "id": s["student_id"],
            "name": s["name"],
            "class_name": s["class_name"],
            "gender": s["gender"],
            "residence": s["residence"],
            "picture": s["picture"]
        })
        
    return render_template(
        "teacher_dashboard.html",
        students=student_list,
        current_date=today,
        current_time=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        teacher_class=teacher_class,
        teacher_name=teacher_name
    )

@app.route("/teacher/search-students")
@teacher_required
def teacher_search_students():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
        
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT name, class_name FROM students WHERE name LIKE %s LIMIT 5", (f"%{q}%",))
    rows = cursor.fetchall()
    cursor.close()
    return jsonify([{"name": r["name"], "class_name": r["class_name"]} for r in rows])

@app.route("/teacher/add-student", methods=["POST"])
@teacher_required
def teacher_add_student():
    db = get_db()
    cursor = db.cursor()
    name = request.form.get("name", "").strip()
    gender = request.form.get("gender", "").strip()
    phone = request.form.get("guardian_phone", "").strip()
    residence = request.form.get("residence", "").strip()
    teacher_class = session.get("role")
    
    if not name or not gender:
        flash("Name and Gender are required.", "error")
        return redirect(url_for("teacher_page"))

    cursor.execute("SELECT * FROM students WHERE name = %s AND class_name = %s", (name, teacher_class))
    existing = cursor.fetchone()
    if existing:
        cursor.close()
        flash(f"Student '{name}' already exists in {teacher_class}.", "error")
        return redirect(url_for("teacher_page"))

    picture_url = ""
    if 'picture' in request.files:
        file = request.files['picture']
        if file and file.filename:
            picture_url = save_upload(file)

    cursor.execute("SELECT student_id FROM students ORDER BY student_id DESC LIMIT 1")
    last_student = cursor.fetchone()
    
    if last_student:
        try:
            last_num = int(last_student[0].replace("GW", ""))
            new_id = f"GW{last_num + 1:03d}"
        except ValueError:
            cursor.execute('SELECT COUNT(*) FROM students')
            new_id = f"GW{cursor.fetchone()[0] + 1:03d}"
    else:
        new_id = "GW001"

    try:
        cursor.execute(
            "INSERT INTO students (student_id, name, class_name, gender, guardian_phone, residence, picture) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (new_id, name, teacher_class, gender, phone, residence, picture_url)
        )
        db.commit()
        flash(f"Student {name} added successfully. Code: {new_id}", "success")
    except Exception as e:
        flash(f"Error adding student: {str(e)}", "error")
    finally:
        cursor.close()
        
    return redirect(url_for("teacher_page"))

@app.route("/teacher/view")
@teacher_required
def teacher_view_student():
    student_id = request.args.get("student_id")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    teacher_class = session.get("role")
    
    cursor.execute("SELECT * FROM students WHERE student_id = %s AND class_name = %s", (student_id, teacher_class))
    student = cursor.fetchone()
    cursor.close()
    
    if not student:
        flash("Student not found in your class.", "error")
        return redirect(url_for("teacher_page"))
        
    return render_template(
        "student_view.html", 
        student=student, 
        records=[],
        total_paid=None,
        back_url=url_for('teacher_page'),
        is_teacher=True
    )

@app.route("/teacher/edit-student", methods=["POST"])
@teacher_required
def teacher_edit_student():
    student_id = request.form.get("student_id")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    teacher_class = session.get("role")
    
    cursor.execute("SELECT * FROM students WHERE student_id = %s AND class_name = %s", (student_id, teacher_class))
    student = cursor.fetchone()
    
    if not student:
        cursor.close()
        flash("Unauthorized.", "error")
        return redirect(url_for("teacher_page"))

    name = request.form.get("name", "").strip()
    gender = request.form.get("gender", "").strip()
    phone = request.form.get("guardian_phone", "").strip()
    residence = request.form.get("residence", "").strip()

    picture_url = student["picture"]
    if 'picture' in request.files:
        file = request.files['picture']
        if file and file.filename:
            picture_url = save_upload(file)

    cursor.execute(
        "UPDATE students SET name=%s, gender=%s, guardian_phone=%s, residence=%s, picture=%s WHERE student_id=%s",
        (name, gender, phone, residence, picture_url, student_id)
    )
    db.commit()
    cursor.close()
    flash("Student details updated.", "success")
    
    return redirect(url_for("teacher_view_student") + f"?student_id={student_id}")


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)
