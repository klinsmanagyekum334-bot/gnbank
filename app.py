import json
import random
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"

USERS_FILE = Path(__file__).resolve().parent / "users.json"


# --------------------------------------------------------------------------
# User Storage Helpers
# --------------------------------------------------------------------------
def generate_account_number(users):
    """Generate a unique 10-digit account number."""
    while True:
        num = str(random.randint(1000000000, 9999999999))
        exists = any(u.get("account", {}).get("account_number") == num for u in users.values())
        if not exists:
            return num


def load_users():
    if USERS_FILE.exists():
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def init_users():
    if not USERS_FILE.exists():
        today = datetime.now().strftime("%Y-%m-%d")
        default_users = {
            "admin@gnbank.com": {
                "password": "admin1234",
                "full_name": "System Administrator",
                "role": "admin",
                "created_by_admin": False,
                "account": {
                    "account_number": "0000000001",
                    "account_type": "Administrative",
                    "account_status": "Active",
                    "branch": "Head Office",
                    "balance": "0.00",
                    "currency": "GHS",
                    "date_opened": today,
                    "phone": "030221199",
                    "ghana_card": "N/A",
                    "address": "Head Office, Accra",
                    "email": "admin@gnbank.com"
                },
                "transactions": []
            },
            "demo@gnbank.com": {
                "password": "demo1234",
                "full_name": "Demo Customer",
                "role": "customer",
                "created_by_admin": False,
                "account": {
                    "account_number": "1234567890",
                    "account_type": "Savings Account",
                    "account_status": "Active",
                    "branch": "Accra Main Branch",
                    "balance": "1500.00",
                    "currency": "GHS",
                    "date_opened": today,
                    "phone": "0244000000",
                    "ghana_card": "GHA-000000000-0",
                    "address": "12 Ring Road, Accra",
                    "email": "demo@gnbank.com"
                },
                "transactions": []
            }
        }
        save_users(default_users)
        print("Created default users: admin@gnbank.com / demo@gnbank.com")


# --------------------------------------------------------------------------
# Public Routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/support")
def support():
    return render_template("support.html")


# --------------------------------------------------------------------------
# Sign Up + Verify
# --------------------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        code = str(random.randint(100000, 999999))
        session['verification_code'] = code
        session['signup_data'] = {
            'full_name': request.form.get('full_name'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone')
        }
        return redirect(url_for('verify'))
    return render_template("signup.html")


@app.route("/verify", methods=["GET", "POST"])
def verify():
    if 'verification_code' not in session:
        return redirect(url_for('signup'))

    error = None
    success = False
    user_name = session.get('signup_data', {}).get('full_name', 'Customer')

    if request.method == "POST":
        entered_code = request.form.get('code', '').strip()
        if entered_code == session.get('verification_code'):
            success = True
            session.pop('verification_code', None)
            session.pop('signup_data', None)
        else:
            error = "Invalid verification code. Please try again."

    return render_template("verify.html", error=error, success=success, user_name=user_name)


# --------------------------------------------------------------------------
# Login / Logout
# --------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        if session["user"]["role"] == "admin":
            return redirect(url_for("admin"))
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        users = load_users()

        if email in users and users[email]["password"] == password:
            session["user"] = {
                "email": email,
                "full_name": users[email]["full_name"],
                "role": users[email]["role"]
            }
            if users[email]["role"] == "admin":
                return redirect(url_for("admin"))
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid email or password. Please try again."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Customer Dashboard
# --------------------------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return redirect(url_for("login"))
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin"))

    users = load_users()
    user_email = session["user"]["email"]

    if user_email not in users:
        session.clear()
        return redirect(url_for("login"))

    user_data = users[user_email]
    return render_template("dashboard.html", user=user_data, email=user_email)


# --------------------------------------------------------------------------
# Account Info
# --------------------------------------------------------------------------
@app.route("/account_info")
def account_info():
    if not session.get("user"):
        return redirect(url_for("login"))
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin"))

    users = load_users()
    user_email = session["user"]["email"]

    if user_email not in users:
        session.clear()
        return redirect(url_for("login"))

    return render_template("account_info.html", user=users[user_email], email=user_email)


# --------------------------------------------------------------------------
# Send Money
# --------------------------------------------------------------------------
@app.route("/send_money")
def send_money():
    if not session.get("user"):
        return redirect(url_for("login"))
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin"))

    users = load_users()
    user_email = session["user"]["email"]

    if user_email not in users:
        session.clear()
        return redirect(url_for("login"))

    return render_template("send_money.html", user=users[user_email], email=user_email)


# --------------------------------------------------------------------------
# Cards
# --------------------------------------------------------------------------
@app.route("/cards")
def cards():
    if not session.get("user"):
        return redirect(url_for("login"))
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin"))

    users = load_users()
    user_email = session["user"]["email"]

    if user_email not in users:
        session.clear()
        return redirect(url_for("login"))

    return render_template("cards.html", user=users[user_email], email=user_email)


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------
@app.route("/history")
def history():
    if not session.get("user"):
        return redirect(url_for("login"))
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin"))

    users = load_users()
    user_email = session["user"]["email"]

    if user_email not in users:
        session.clear()
        return redirect(url_for("login"))

    transactions = users[user_email].get("transactions", [])
    return render_template(
        "history.html",
        user=users[user_email],
        email=user_email,
        transactions=transactions
    )


# --------------------------------------------------------------------------
# Admin Panel
# --------------------------------------------------------------------------
@app.route("/admin")
def admin():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))
    users = load_users()
    return render_template("admin.html", users=users, current_admin=session["user"]["email"])


@app.route("/admin/create_user", methods=["POST"])
def admin_create_user():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    full_name = request.form.get("full_name", "").strip()

    if not email or not password or not full_name:
        flash("Name, email and password are required.", "error")
        return redirect(url_for("admin"))

    users = load_users()
    if email in users:
        flash(f"User {email} already exists.", "error")
        return redirect(url_for("admin"))

    today = datetime.now().strftime("%Y-%m-%d")
    account_number = request.form.get("account_number", "").strip() or generate_account_number(users)
    opening_balance = request.form.get("balance", "0.00").strip() or "0.00"

    users[email] = {
        "password": password,
        "full_name": full_name,
        "role": "customer",
        "created_by_admin": True,
        "account": {
            "account_number": account_number,
            "account_type": request.form.get("account_type", "Savings Account"),
            "account_status": "Active",
            "branch": request.form.get("branch", "Accra Main Branch"),
            "balance": opening_balance,
            "currency": "GHS",
            "date_opened": today,
            "phone": request.form.get("phone", ""),
            "ghana_card": request.form.get("ghana_card", ""),
            "address": request.form.get("address", ""),
            "email": email
        },
        "transactions": []
    }

    # If opening balance > 0, record as first credit
    try:
        if float(opening_balance) > 0:
            users[email]["transactions"].insert(0, {
                "id": str(random.randint(100000, 999999)),
                "type": "credit",
                "amount": f"{float(opening_balance):.2f}",
                "description": "Opening balance",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "balance_after": f"{float(opening_balance):.2f}"
            })
    except ValueError:
        pass

    save_users(users)
    flash(f"Account created for {full_name}. Account Number: {account_number}", "success")
    return redirect(url_for("admin"))


@app.route("/admin/user")
def admin_user_view():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.args.get("email", "").strip().lower()
    users = load_users()

    if email not in users:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    return render_template(
        "admin_user.html",
        email=email,
        user=users[email],
        current_admin=session["user"]["email"]
    )


@app.route("/admin/user/update", methods=["POST"])
def admin_user_update():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    original_email = request.form.get("original_email", "").strip().lower()
    users = load_users()

    if original_email not in users:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    user = users[original_email]

    new_email = request.form.get("email", "").strip().lower()
    new_password = request.form.get("password", "").strip()
    new_name = request.form.get("full_name", "").strip()

    account = user.get("account", {})
    account["account_number"] = request.form.get("account_number", account.get("account_number", ""))
    account["account_type"] = request.form.get("account_type", account.get("account_type", ""))
    account["account_status"] = request.form.get("account_status", account.get("account_status", ""))
    account["branch"] = request.form.get("branch", account.get("branch", ""))
    account["phone"] = request.form.get("phone", account.get("phone", ""))
    account["ghana_card"] = request.form.get("ghana_card", account.get("ghana_card", ""))
    account["address"] = request.form.get("address", account.get("address", ""))

    user["account"] = account

    if new_name:
        user["full_name"] = new_name
    if new_password:
        user["password"] = new_password

    final_email = original_email
    if new_email and new_email != original_email:
        if new_email in users:
            flash(f"Cannot change email — {new_email} already exists.", "error")
            return redirect(url_for("admin_user_view", email=original_email))
        users[new_email] = users.pop(original_email)
        final_email = new_email
        users[final_email]["account"]["email"] = new_email

    if original_email == session["user"]["email"] and final_email != original_email:
        session["user"]["email"] = final_email

    save_users(users)
    flash(f"Changes saved for {final_email}.", "success")
    return redirect(url_for("admin_user_view", email=final_email))


@app.route("/admin/user/delete", methods=["POST"])
def admin_user_delete():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.form.get("email", "").strip().lower()

    if email == "admin@gnbank.com":
        flash("The main administrator account cannot be deleted.", "error")
        return redirect(url_for("admin"))

    if email == session["user"]["email"]:
        flash("You cannot delete your own account while logged in.", "error")
        return redirect(url_for("admin"))

    users = load_users()
    users.pop(email, None)
    save_users(users)
    flash(f"Account {email} has been deleted.", "success")
    return redirect(url_for("admin"))


# --------------------------------------------------------------------------
# Admin — Balance Actions
# --------------------------------------------------------------------------
@app.route("/admin/balance/credit", methods=["POST"])
def admin_balance_credit():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.form.get("email", "").strip().lower()
    amount_str = request.form.get("amount", "0").strip()
    note = request.form.get("note", "").strip() or "Credit from admin"

    users = load_users()
    if email not in users:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid amount.", "error")
        return redirect(url_for("admin_user_view", email=email))

    user = users[email]
    current = float(user["account"].get("balance", "0"))
    new_balance = current + amount
    user["account"]["balance"] = f"{new_balance:.2f}"

    tx = {
        "id": str(random.randint(100000, 999999)),
        "type": "credit",
        "amount": f"{amount:.2f}",
        "description": note,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "balance_after": f"{new_balance:.2f}"
    }
    user.setdefault("transactions", []).insert(0, tx)
    users[email] = user
    save_users(users)

    flash(f"Credited GHS {amount:.2f} to {user['full_name']}.", "success")
    return redirect(url_for("admin_user_view", email=email))


@app.route("/admin/balance/debit", methods=["POST"])
def admin_balance_debit():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.form.get("email", "").strip().lower()
    amount_str = request.form.get("amount", "0").strip()
    note = request.form.get("note", "").strip() or "Debit from admin"

    users = load_users()
    if email not in users:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid amount.", "error")
        return redirect(url_for("admin_user_view", email=email))

    user = users[email]
    current = float(user["account"].get("balance", "0"))

    if amount > current:
        flash("Debit amount exceeds current balance.", "error")
        return redirect(url_for("admin_user_view", email=email))

    new_balance = current - amount
    user["account"]["balance"] = f"{new_balance:.2f}"

    tx = {
        "id": str(random.randint(100000, 999999)),
        "type": "debit",
        "amount": f"{amount:.2f}",
        "description": note,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "balance_after": f"{new_balance:.2f}"
    }
    user.setdefault("transactions", []).insert(0, tx)
    users[email] = user
    save_users(users)

    flash(f"Debited GHS {amount:.2f} from {user['full_name']}.", "success")
    return redirect(url_for("admin_user_view", email=email))


@app.route("/admin/balance/edit", methods=["POST"])
def admin_balance_edit():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.form.get("email", "").strip().lower()
    new_balance_str = request.form.get("new_balance", "0").strip()

    users = load_users()
    if email not in users:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    try:
        new_balance = float(new_balance_str)
        if new_balance < 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid balance.", "error")
        return redirect(url_for("admin_user_view", email=email))

    user = users[email]
    user["account"]["balance"] = f"{new_balance:.2f}"
    user["transactions"] = []   # Wipe history after edit
    users[email] = user
    save_users(users)

    flash(f"Balance set to GHS {new_balance:.2f}. Transaction history cleared.", "success")
    return redirect(url_for("admin_user_view", email=email))


@app.route("/admin/balance/delete", methods=["POST"])
def admin_balance_delete():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.form.get("email", "").strip().lower()
    users = load_users()

    if email not in users:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    user = users[email]
    user["account"]["balance"] = "0.00"
    user["transactions"] = []   # Wipe history too
    users[email] = user
    save_users(users)

    flash(f"Balance deleted for {user['full_name']}. History cleared.", "success")
    return redirect(url_for("admin_user_view", email=email))


# --------------------------------------------------------------------------
# Base (template preview)
# --------------------------------------------------------------------------
@app.route("/base")
def base():
    return render_template("base.html")


# --------------------------------------------------------------------------
# Start
# --------------------------------------------------------------------------
if __name__ == "__main__":
    init_users()
    app.run(debug=True)