from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import string

# Import email utility - updated for your project structure
from reports.email_utils import send_password_reset_email

auth_bp = Blueprint('auth', __name__, template_folder='../static/templates')

def generate_reset_code():
    """Generate a random 6-digit code"""
    return ''.join(random.choices(string.digits, k=6))

def generate_reset_token():
    """Generate a secure random token"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

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

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Handle forgot password requests"""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        
        if not email:
            flash("Please enter your email address.", "danger")
            return render_template('forgot_password.html')
        
        mongo = current_app.mongo
        user = mongo.db.users.find_one({"email": email})
        
        if not user:
            # Don't reveal if email exists or not for security
            flash("If your email is registered, you will receive a password reset code.", "info")
            return render_template('forgot_password.html')
        
        # Generate reset code and token
        reset_code = generate_reset_code()
        reset_token = generate_reset_token()
        expires_at = datetime.utcnow() + timedelta(minutes=15)  # Code expires in 15 minutes
        
        # Store reset request in database
        reset_data = {
            "email": email,
            "code": reset_code,
            "token": reset_token,
            "expires_at": expires_at,
            "used": False,
            "created_at": datetime.utcnow()
        }
        
        # Remove any existing reset requests for this email
        mongo.db.password_resets.delete_many({"email": email})
        
        # Insert new reset request
        mongo.db.password_resets.insert_one(reset_data)
        
        # Send email with reset code
        try:
            send_password_reset_email(email, reset_code, 15)
            flash("A verification code has been sent to your email address.", "success")
            return redirect(url_for("auth.verify_reset_code", token=reset_token))
            
        except Exception as e:
            current_app.logger.error(f"Failed to send reset email: {e}")
            flash("Failed to send reset email. Please try again later.", "danger")
            return render_template('forgot_password.html')
    
    return render_template('forgot_password.html')

@auth_bp.route("/verify-reset-code/<token>", methods=["GET", "POST"])
def verify_reset_code(token):
    """Verify the reset code and show password reset form"""
    mongo = current_app.mongo
    
    # Find the reset request
    reset_request = mongo.db.password_resets.find_one({
        "token": token,
        "used": False,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not reset_request:
        flash("Invalid or expired reset link. Please request a new password reset.", "danger")
        return redirect(url_for("auth.forgot_password"))
    
    if request.method == "POST":
        submitted_code = request.form.get("code", "").strip()
        new_password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        
        # Verify the code
        if submitted_code != reset_request["code"]:
            flash("Invalid verification code. Please try again.", "danger")
            return render_template('verify_reset_code.html', token=token, email=reset_request["email"])
        
        # Validate passwords
        if not new_password:
            flash("Please enter a new password.", "danger")
            return render_template('verify_reset_code.html', token=token, email=reset_request["email"])
        
        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('verify_reset_code.html', token=token, email=reset_request["email"])
        
        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('verify_reset_code.html', token=token, email=reset_request["email"])
        
        # Update the user's password
        hashed_password = generate_password_hash(new_password)
        mongo.db.users.update_one(
            {"email": reset_request["email"]},
            {"$set": {"password": hashed_password}}
        )
        
        # Mark the reset request as used
        mongo.db.password_resets.update_one(
            {"_id": reset_request["_id"]},
            {"$set": {"used": True}}
        )
        
        flash("Your password has been successfully reset! You can now log in with your new password.", "success")
        return redirect(url_for("auth.root"))
    
    return render_template('verify_reset_code.html', token=token, email=reset_request["email"])

@auth_bp.route("/resend-code", methods=["POST"])
def resend_code():
    """Resend verification code for password reset"""
    try:
        import json
        data = request.get_json()
        email = data.get('email', '').strip() if data else request.form.get('email', '').strip()
        
        if not email:
            return {"success": False, "message": "Email is required"}, 400
        
        mongo = current_app.mongo
        user = mongo.db.users.find_one({"email": email})
        
        if not user:
            # Don't reveal if email exists or not for security
            return {"success": True, "message": "If your email is registered, you will receive a new code."}, 200
        
        # Check if there's an existing, non-expired reset request
        existing_request = mongo.db.password_resets.find_one({
            "email": email,
            "used": False,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if existing_request:
            # Check if the last request was sent less than 60 seconds ago
            last_sent = existing_request.get("created_at", datetime.utcnow() - timedelta(minutes=2))
            if datetime.utcnow() - last_sent < timedelta(seconds=60):
                return {"success": False, "message": "Please wait before requesting another code."}, 429
        
        # Generate new reset code and token
        reset_code = generate_reset_code()
        reset_token = generate_reset_token()
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        
        # Remove any existing reset requests for this email
        mongo.db.password_resets.delete_many({"email": email})
        
        # Insert new reset request
        reset_data = {
            "email": email,
            "code": reset_code,
            "token": reset_token,
            "expires_at": expires_at,
            "used": False,
            "created_at": datetime.utcnow()
        }
        mongo.db.password_resets.insert_one(reset_data)
        
        # Send email with reset code
        try:
            send_password_reset_email(email, reset_code, 15)
            return {"success": True, "message": "A new verification code has been sent to your email."}, 200
            
        except Exception as e:
            current_app.logger.error(f"Failed to send reset email: {e}")
            return {"success": False, "message": "Failed to send email. Please try again."}, 500
    
    except Exception as e:
        current_app.logger.error(f"Error in resend_code: {e}")
        return {"success": False, "message": "An error occurred. Please try again."}, 500

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