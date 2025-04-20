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
        return redirect(url_for("auth.dashboard"))
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
    """Unified dashboard that adapts based on the user's role."""
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if user_data and "password" in user_data:
        del user_data["password"]

    # Determine the user’s role (admin, maintenance, or user)
    role = user_data.get("role", "user")

    # Fetch issues based on role
    if role == "admin":
        # Admin sees all issues
        issues = list(mongo.db.issues.find())
        # Also fetch maintenance users so we can assign issues to them
        maintenance_users = list(mongo.db.users.find({"role": "maintenance"}))
    elif role == "maintenance":
        # Maintenance sees only issues assigned to them
        issues = list(mongo.db.issues.find({"assigned_to": session["user"]}))
        maintenance_users = []
    else:
        # Regular user sees only their own reports
        issues = list(mongo.db.issues.find({"reporter_email": session["user"]}))
        maintenance_users = []

    # Pass issues (and maintenance_users if admin) to the dashboard
    return render_template("dashboard.html",
                           user=user_data,
                           issues=issues,
                           maintenance_users=maintenance_users)

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
