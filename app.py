import json
import random
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, flash

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"

# --------------------------------------------------------------------------
# Firebase Initialization
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
SERVICE_ACCOUNT_FILE = BASE_DIR / "serviceAccountKey.json"

cred = credentials.Certificate(str(SERVICE_ACCOUNT_FILE))
firebase_admin.initialize_app(cred)

db = firestore.client()
USERS_COLLECTION = db.collection("users")


# --------------------------------------------------------------------------
# User Storage Helpers (Firestore)
# --------------------------------------------------------------------------
def generate_account_number():
    """Generate a unique 10-digit account number that no existing user has."""
    while True:
        num = str(random.randint(1000000000, 9999999999))
        query = USERS_COLLECTION.where("account.account_number", "==", num).limit(1).stream()
        if not any(query):
            return num


def load_user(email):
    """Fetch a single user document by email (used as document ID)."""
    doc = USERS_COLLECTION.document(email).get()
    if doc.exists:
        return doc.to_dict()
    return None


def load_users():
    """Fetch all users as a dictionary {email: user_dict}."""
    result = {}
    for doc in USERS_COLLECTION.stream():
        result[doc.id] = doc.to_dict()
    return result


def save_user(email, user_data):
    """Save (create or overwrite) a single user document."""
    USERS_COLLECTION.document(email).set(user_data)


def delete_user(email):
    """Remove a user document."""
    USERS_COLLECTION.document(email).delete()


def init_users():
    """Create default admin and demo users if the collection is empty."""
    if not any(USERS_COLLECTION.limit(1).stream()):
        today = datetime.now().strftime("%Y-%m-%d")

        save_user("admin@gnbank.com", {
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
        })

        save_user("demo@gnbank.com", {
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
        })

        print("Created default users in Firebase: admin@gnbank.com / demo@gnbank.com")


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

        user = load_user(email)

        if user and user.get("password") == password:
            session["user"] = {
                "email": email,
                "full_name": user["full_name"],
                "role": user["role"]
            }
            if user["role"] == "admin":
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

    user_email = session["user"]["email"]
    user_data = load_user(user_email)

    if not user_data:
        session.clear()
        return redirect(url_for("login"))

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

    user_email = session["user"]["email"]
    user_data = load_user(user_email)

    if not user_data:
        session.clear()
        return redirect(url_for("login"))

    return render_template("account_info.html", user=user_data, email=user_email)


# --------------------------------------------------------------------------
# Send Money
# --------------------------------------------------------------------------
@app.route("/send_money")
def send_money():
    if not session.get("user"):
        return redirect(url_for("login"))
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin"))

    user_email = session["user"]["email"]
    user_data = load_user(user_email)

    if not user_data:
        session.clear()
        return redirect(url_for("login"))

    return render_template("send_money.html", user=user_data, email=user_email)


@app.route("/send_money/confirm", methods=["POST"])
def send_money_confirm():
    if not session.get("user"):
        return redirect(url_for("login"))
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin"))

    user_email = session["user"]["email"]
    user = load_user(user_email)

    if not user:
        session.clear()
        return redirect(url_for("login"))

    action = request.form.get("action", "Send Money").strip()
    service = request.form.get("service", "").strip()
    recipient_name = request.form.get("recipient_name", "").strip()
    recipient_account = request.form.get("recipient_account", "").strip()
    recipient_email = request.form.get("email", "").strip()
    amount_str = request.form.get("amount", "0").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    source_account = user["account"].get("account_number", "")

    # --- Validation ---
    if not action or action not in ["Make Payments", "Send Money"]:
        flash("Please select an action type.", "error")
        return redirect(url_for("send_money"))

    if not service:
        flash("Please select a bank or service.", "error")
        return redirect(url_for("send_money"))

    if not recipient_name:
        flash("Recipient name is required.", "error")
        return redirect(url_for("send_money"))

    if not recipient_account:
        flash("Recipient account number is required.", "error")
        return redirect(url_for("send_money"))

    # Same-account check
    if recipient_account == source_account:
        flash("You cannot send money to your own account number.", "error")
        return redirect(url_for("send_money"))

    if not recipient_email or "@" not in recipient_email:
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("send_money"))

    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("send_money"))

    if not password:
        flash("Password is required to authorise this transfer.", "error")
        return redirect(url_for("send_money"))

    # --- Amount validation ---
    try:
        amount = float(amount_str)
    except (ValueError, TypeError):
        flash("Invalid amount. Please enter a valid number.", "error")
        return redirect(url_for("send_money"))

    if amount <= 0:
        flash("Amount must be greater than zero.", "error")
        return redirect(url_for("send_money"))

    if amount < 1.00:
        flash("Minimum transfer amount is $1.00.", "error")
        return redirect(url_for("send_money"))

    # --- Balance check ---
    current = float(user["account"].get("balance", "0"))
    if amount > current:
        flash(f"Insufficient balance. Your available balance is ${current:,.2f}.", "error")
        return redirect(url_for("send_money"))

    # --- Process transaction ---
    new_balance = current - amount
    user["account"]["balance"] = f"{new_balance:.2f}"

    tx_id = f"GNB{random.randint(100000000, 999999999)}"

    tx = {
        "id": tx_id,
        "type": "debit",
        "amount": f"{amount:.2f}",
        "description": f"{action} to {recipient_name} via {service}",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "balance_after": f"{new_balance:.2f}",
        "action": action,
        "service": service,
        "recipient_name": recipient_name,
        "recipient_account": recipient_account,
        "email": recipient_email,
        "reference": tx_id
    }

    user.setdefault("transactions", []).insert(0, tx)
    save_user(user_email, user)

    session["last_receipt"] = tx_id
    return redirect(url_for("send_money_receipt"))


@app.route("/send_money/receipt")
def send_money_receipt():
    if not session.get("user"):
        return redirect(url_for("login"))
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin"))

    user_email = session["user"]["email"]
    user = load_user(user_email)

    if not user:
        session.clear()
        return redirect(url_for("login"))

    ref_id = session.get("last_receipt")
    if not ref_id:
        return redirect(url_for("send_money"))

    transactions = user.get("transactions", [])
    tx = next((t for t in transactions if t.get("id") == ref_id), None)

    if not tx:
        return redirect(url_for("send_money"))

    return render_template("receipt.html", user=user, email=user_email, tx=tx)


# --------------------------------------------------------------------------
# Cards
# --------------------------------------------------------------------------
@app.route("/cards")
def cards():
    if not session.get("user"):
        return redirect(url_for("login"))
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin"))

    user_email = session["user"]["email"]
    user_data = load_user(user_email)

    if not user_data:
        session.clear()
        return redirect(url_for("login"))

    return render_template("cards.html", user=user_data, email=user_email)


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------
@app.route("/history")
def history():
    if not session.get("user"):
        return redirect(url_for("login"))
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin"))

    user_email = session["user"]["email"]
    user_data = load_user(user_email)

    if not user_data:
        session.clear()
        return redirect(url_for("login"))

    transactions = user_data.get("transactions", [])
    return render_template(
        "history.html",
        user=user_data,
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

    if load_user(email):
        flash(f"User {email} already exists.", "error")
        return redirect(url_for("admin"))

    today = datetime.now().strftime("%Y-%m-%d")
    account_number = request.form.get("account_number", "").strip() or generate_account_number()
    opening_balance = request.form.get("balance", "0.00").strip() or "0.00"

    new_user = {
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

    try:
        if float(opening_balance) > 0:
            new_user["transactions"].insert(0, {
                "id": str(random.randint(100000, 999999)),
                "type": "credit",
                "amount": f"{float(opening_balance):.2f}",
                "description": "Opening balance",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "balance_after": f"{float(opening_balance):.2f}"
            })
    except ValueError:
        pass

    save_user(email, new_user)
    flash(f"Account created for {full_name}. Account Number: {account_number}", "success")
    return redirect(url_for("admin"))


@app.route("/admin/user")
def admin_user_view():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.args.get("email", "").strip().lower()
    user = load_user(email)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    return render_template(
        "admin_user.html",
        email=email,
        user=user,
        current_admin=session["user"]["email"]
    )


@app.route("/admin/user/update", methods=["POST"])
def admin_user_update():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    original_email = request.form.get("original_email", "").strip().lower()
    user = load_user(original_email)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

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
        if load_user(new_email):
            flash(f"Cannot change email — {new_email} already exists.", "error")
            return redirect(url_for("admin_user_view", email=original_email))
        # Save under new email, delete old
        user["account"]["email"] = new_email
        save_user(new_email, user)
        delete_user(original_email)
        final_email = new_email
    else:
        save_user(original_email, user)

    if original_email == session["user"]["email"] and final_email != original_email:
        session["user"]["email"] = final_email

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

    delete_user(email)
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

    user = load_user(email)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid amount.", "error")
        return redirect(url_for("admin_user_view", email=email))

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
    save_user(email, user)

    flash(f"Credited GHS {amount:.2f} to {user['full_name']}.", "success")
    return redirect(url_for("admin_user_view", email=email))


@app.route("/admin/balance/debit", methods=["POST"])
def admin_balance_debit():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.form.get("email", "").strip().lower()
    amount_str = request.form.get("amount", "0").strip()
    note = request.form.get("note", "").strip() or "Debit from admin"

    user = load_user(email)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid amount.", "error")
        return redirect(url_for("admin_user_view", email=email))

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
    save_user(email, user)

    flash(f"Debited GHS {amount:.2f} from {user['full_name']}.", "success")
    return redirect(url_for("admin_user_view", email=email))


@app.route("/admin/balance/edit", methods=["POST"])
def admin_balance_edit():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.form.get("email", "").strip().lower()
    new_balance_str = request.form.get("new_balance", "0").strip()

    user = load_user(email)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    try:
        new_balance = float(new_balance_str)
        if new_balance < 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid balance.", "error")
        return redirect(url_for("admin_user_view", email=email))

    user["account"]["balance"] = f"{new_balance:.2f}"
    user["transactions"] = []
    save_user(email, user)

    flash(f"Balance set to GHS {new_balance:.2f}. Transaction history cleared.", "success")
    return redirect(url_for("admin_user_view", email=email))


@app.route("/admin/balance/delete", methods=["POST"])
def admin_balance_delete():
    if not session.get("user") or session["user"]["role"] != "admin":
        return redirect(url_for("login"))

    email = request.form.get("email", "").strip().lower()
    user = load_user(email)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin"))

    user["account"]["balance"] = "0.00"
    user["transactions"] = []
    save_user(email, user)

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
