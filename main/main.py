from flask import Blueprint, render_template, session, flash, redirect, url_for, current_app, request
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from gridfs import GridFS
from bson import ObjectId

main_bp = Blueprint('main', __name__, template_folder='../static/templates')

@main_bp.route("/")
@main_bp.route("/home")
def home():
    """صفحة الهوم تُظهر نفس المحتوى للجميع،
       لكنها ترسل بيانات إضافية إذا كان المستخدم مسجَّلاً."""
    mongo = current_app.mongo

    user_email = session.get("user")
    user_data  = None
    my_issues_count = 0

    if user_email:
        # -- بيانات المستخدم (لا نُرسل كلمة المرور إلى القالب)
        user_data = mongo.db.users.find_one({"email": user_email})
        if user_data and "password" in user_data:
            user_data.pop("password")

        # -- عدّ التقارير التي أبلغها
        my_issues_count = mongo.db.issues.count_documents(
            {"reporter_email": user_email}
        )

    return render_template(
        "home.html",
        year=datetime.utcnow().year,
        user=user_data,                 # None إذا لم يكن مسجَّلاً
        my_issue_count=my_issues_count  # 0 إذا لم يكن مسجَّلاً
    )

@main_bp.route("/profile")
def profile():
    """Profile page: shows user data if logged in."""
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))  # 'auth.root' is your login form route

    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if user_data and "password" in user_data:
        del user_data["password"]

    return render_template("profile.html", user=user_data)

@main_bp.route("/update_profile", methods=["POST"])
def update_profile():
    """Handle profile edits for name and password."""
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if not user_data:
        flash("User not found", "danger")
        return redirect(url_for("main.profile"))

    # Get updated fields from form
    new_name = request.form.get("name")
    new_password = request.form.get("password")

    update_fields = {}
    if new_name:
        update_fields["name"] = new_name
    if new_password:
        hashed_password = generate_password_hash(new_password)
        update_fields["password"] = hashed_password

    if update_fields:
        mongo.db.users.update_one({"email": session["user"]}, {"$set": update_fields})
        flash("Profile updated successfully", "success")
    else:
        flash("No changes made.", "info")

    return redirect(url_for("main.profile"))

@main_bp.route("/about")
def about():
    """
    About page: renders about.html
    """
    mongo = current_app.mongo

    user_email      = session.get("user")
    user_data       = None
    my_issues_count = 0

    if user_email:
        # fetch & sanitize user
        user_data = mongo.db.users.find_one({"email": user_email})
        if user_data and "password" in user_data:
            user_data.pop("password")
        # count their reports
        my_issues_count = mongo.db.issues.count_documents(
            {"reporter_email": user_email}
        )

    return render_template(
        "about.html",
        year=datetime.utcnow().year,
        user=user_data,
        my_issue_count=my_issues_count
    )

@main_bp.route("/delete_account", methods=["POST"])
def delete_my_account():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    # remove user from DB
    mongo = current_app.mongo
    mongo.db.users.delete_one({"email": session["user"]})
    session.clear()
    flash("Your account has been deleted.", "info")
    return redirect(url_for("auth.root"))

# ---------- Context processor: rejected count and problem reports count for main blueprint ----------
@main_bp.context_processor
def inject_counts():
    """Add rejected reports count and problem reports count to template context for the current user"""
    if "user" not in session:
        return dict(rejected_count=0, problem_reports_count=0)

    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    
    if not user_data:
        return dict(rejected_count=0, problem_reports_count=0)
    
    # Initialize counts
    rejected_count = 0
    problem_reports_count = 0
    
    # Calculate rejected count for maintenance users
    if user_data.get("role") == "maintenance":
        try:
            for r in mongo.db.rejected_reports.find({"technician": session["user"]}):
                try:
                    oid = ObjectId(r.get("original_issue_id"))
                    issue = mongo.db.issues.find_one({"_id": oid})
                except:
                    continue
                if issue and issue.get("status") not in ("done", "fixed"):
                    rejected_count += 1
        except Exception as e:
            current_app.logger.error(f"Error calculating rejected count: {e}")
            rejected_count = 0
    
    # Calculate problem reports count
    try:
        if user_data.get("role") == "admin":
            # For admins: count of all pending problem reports
            problem_reports_count = mongo.db.issue_problems.count_documents({"status": "pending"})
        else:
            # For reporters: count of problems with their reports that need action
            user_reports = list(mongo.db.issues.find({"reporter_email": session["user"]}))
            user_report_ids = [str(report["_id"]) for report in user_reports]
            
            if user_report_ids:
                problem_reports_count = mongo.db.issue_problems.count_documents({
                    "original_issue_id": {"$in": user_report_ids},
                    "requires_reporter_action": True,
                    "status": {"$in": ["pending", "notified"]}
                })
    except Exception as e:
        current_app.logger.error(f"Error calculating problem reports count: {e}")
        problem_reports_count = 0

    return dict(rejected_count=rejected_count, problem_reports_count=problem_reports_count)