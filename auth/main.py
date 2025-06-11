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
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if not user_data:
        flash("User not found", "danger")
        return redirect(url_for("auth.logout"))

    user_data.pop("password", None)
    role = user_data.get("role", "user")

    # Calculate problem reports count for the current user
    problem_reports_count = 0
    
    if role == "admin":
        # For admins: count of all pending problem reports
        try:
            problem_reports_count = mongo.db.issue_problems.count_documents({"status": "pending"})
        except Exception as e:
            current_app.logger.error(f"Error counting admin problem reports: {e}")
            problem_reports_count = 0
    else:
        # For reporters: count of problems with their reports that need action
        try:
            user_reports = list(mongo.db.issues.find({"reporter_email": session["user"]}))
            user_report_ids = [str(report["_id"]) for report in user_reports]
            
            if user_report_ids:
                problem_reports_count = mongo.db.issue_problems.count_documents({
                    "original_issue_id": {"$in": user_report_ids},
                    "requires_reporter_action": True,
                    "status": {"$in": ["pending", "notified"]}
                })
        except Exception as e:
            current_app.logger.error(f"Error counting user problem reports: {e}")
            problem_reports_count = 0

    # Route based on role
    if role == "admin":
        # Get all issues for admin dashboard
        try:
            issues = list(mongo.db.issues.find())
            
            # Sort by urgency score (highest priority/severity first)
            def get_priority_score(priority):
                priority_scores = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
                return priority_scores.get(priority.lower() if priority else 'medium', 2)

            def get_severity_score(severity):
                severity_scores = {'minor': 1, 'moderate': 2, 'major': 3, 'critical': 4}
                return severity_scores.get(severity.lower() if severity else 'moderate', 2)

            def calculate_urgency_score(priority, severity):
                priority_weight = 0.6
                severity_weight = 0.4
                priority_score = get_priority_score(priority)
                severity_score = get_severity_score(severity)
                return (priority_score * priority_weight) + (severity_score * severity_weight)

            # Add urgency scores and sort
            for issue in issues:
                if not issue.get('priority'):
                    issue['priority'] = 'medium'
                if not issue.get('severity'):
                    issue['severity'] = 'moderate'
                
                issue['urgency_score'] = calculate_urgency_score(
                    issue.get('priority', 'medium'), 
                    issue.get('severity', 'moderate')
                )
                
                # Serialize ObjectId fields
                if issue.get("_id"):
                    issue["_id"] = str(issue["_id"])
                if issue.get("image_file_id"):
                    issue["image_file_id"] = str(issue["image_file_id"])

            # Sort by urgency score (highest first)
            issues.sort(key=lambda x: x.get('urgency_score', 0), reverse=True)
            
            maintenance_users = list(mongo.db.users.find({"role": "maintenance"}))
            my_issue_count = mongo.db.issues.count_documents({"reporter_email": session["user"]})

            return render_template(
                "admin_dashboard.html",
                issues=issues,
                maintenance_users=maintenance_users,
                user=user_data,
                my_issue_count=my_issue_count,
                current_sort='urgency',
                problem_reports_count=problem_reports_count
            )
            
        except Exception as e:
            current_app.logger.error(f"Error in admin dashboard: {e}")
            flash("Error loading dashboard data", "danger")
            return render_template("admin_dashboard.html", 
                                 issues=[], 
                                 maintenance_users=[], 
                                 user=user_data,
                                 my_issue_count=0,
                                 current_sort='urgency',
                                 problem_reports_count=problem_reports_count)

    elif role == "maintenance":
        # Redirect maintenance users to their dashboard
        return redirect(url_for("reports.maintenance_dashboard"))

    else:
        # Regular user dashboard
        try:
            # Get user's issues
            issues = list(mongo.db.issues.find({"reporter_email": session["user"]}))
            
            # Add urgency scores for sorting
            def calculate_urgency_score(priority, severity):
                priority_scores = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
                severity_scores = {'minor': 1, 'moderate': 2, 'major': 3, 'critical': 4}
                
                priority_weight = 0.6
                severity_weight = 0.4
                
                priority_score = priority_scores.get(priority.lower() if priority else 'medium', 2)
                severity_score = severity_scores.get(severity.lower() if severity else 'moderate', 2)
                
                return (priority_score * priority_weight) + (severity_score * severity_weight)

            for issue in issues:
                if not issue.get('priority'):
                    issue['priority'] = 'medium'
                if not issue.get('severity'):
                    issue['severity'] = 'moderate'
                
                issue['urgency_score'] = calculate_urgency_score(
                    issue.get('priority', 'medium'), 
                    issue.get('severity', 'moderate')
                )
                
                # Serialize ObjectId fields
                if issue.get("_id"):
                    issue["_id"] = str(issue["_id"])
                if issue.get("image_file_id"):
                    issue["image_file_id"] = str(issue["image_file_id"])

            # Sort by urgency score (highest first)
            issues.sort(key=lambda x: x.get('urgency_score', 0), reverse=True)

            return render_template(
                "user_dashboard.html",
                issues=issues,
                user=user_data,
                current_sort='urgency',
                problem_reports_count=problem_reports_count
            )
            
        except Exception as e:
            current_app.logger.error(f"Error in user dashboard: {e}")
            flash("Error loading your reports", "danger")
            return render_template("user_dashboard.html", 
                                 issues=[], 
                                 user=user_data,
                                 current_sort='urgency',
                                 problem_reports_count=problem_reports_count)
        

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
