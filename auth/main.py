from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route("/")
def root():
    """Root route: If already logged in, go to dashboard; otherwise show auth page."""
    if "user" in session:
        return redirect(url_for("auth.dashboard"))
    return render_template('auth.html')

@auth_bp.route("/login", methods=["POST"])
def login():
    """Process user login: check email/password, store session."""
    email = request.form.get("email")
    password = request.form.get("password")

    mongo = current_app.mongo
    user = mongo.db.users.find_one({"email": email})

    if user and check_password_hash(user["password"], password):
        session["user"] = email  # Store email
        session["role"] = user.get("role", "user")  # Store role as well
        return redirect(url_for("main.home"))
    else:
        flash("Invalid email or password", "danger")
        return redirect(url_for("auth.root"))

@auth_bp.route("/register", methods=["POST"])
def register():
    """Handle new user registration, including role assignment."""
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    role = request.form.get("role")  # user/admin/maintenance

    mongo = current_app.mongo

    # Check if email already exists
    if mongo.db.users.find_one({"email": email}):
        flash("Email already exists. Please choose another.", "danger")
        return redirect(url_for("auth.root"))

    hashed_password = generate_password_hash(password)
    user_data = {
        "name": name,
        "email": email,
        "password": hashed_password,
        "role": role  # store the role in the DB
    }

    mongo.db.users.insert_one(user_data)
    flash("Registration successful! Please log in.", "success")
    return redirect(url_for("auth.root"))


@auth_bp.route("/dashboard")
def dashboard():
    # 1. Ensure user is logged in
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    # 2. Load & sanitize user
    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if not user_data:
        flash("User not found", "danger")
        return redirect(url_for("auth.root"))
    user_data.pop("password", None)

    # 3. Fetch issues based on role
    role = user_data.get("role", "user")
    if role == "admin":
        issues = list(mongo.db.issues.find())
        maintenance_users = list(mongo.db.users.find({"role": "maintenance"}))
    elif role == "maintenance":
        issues = list(mongo.db.issues.find({"assigned_to": session["user"]}))
        maintenance_users = []
    else:
        issues = list(mongo.db.issues.find({"reporter_email": session["user"]}))
        maintenance_users = []


    # ── ADD NORMALIZATION HERE ──
    for i in issues:
        # convert Mongo ObjectId to string
        i["_id"] = str(i["_id"])
        # guarantee there's always a dict at issue.location
        i["location"] = i.get("location", {})
    # ─────────────────────────────
    # 4. Choose the correct template
    template_map = {
        "admin":       "admin_dashboard.html",
        "maintenance": "maintenance_dashboard.html",
        "user":        "user_dashboard.html"
    }
    template_name = template_map.get(role, "user_dashboard.html")

    # 5. Render it
    return render_template(
        template_name,
        user=user_data,
        issues=issues,
        maintenance_users=maintenance_users
    )


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    user_email = session.get("email") or session.get("user")
    if user_email:
        current_app.mongo.db.users.update_one(
            {"email": user_email}, {"$set": {"logged_in": False}}
        )
    session.clear()

    print(f"[LOGOUT] {request.method} logout triggered by {user_email or 'Unknown'}")

    if request.method == "GET":
        flash("Logged out successfully", "info")
        return redirect(url_for("auth.root"))

    return ("", 204)



@auth_bp.route("/status")
def status():
    """Check MongoDB connection status."""
    mongo = current_app.mongo
    try:
        mongo.cx.server_info()
        return "MongoDB connection is healthy."
    except Exception as e:
        return f"MongoDB connection error: {str(e)}"
