from flask import Blueprint, render_template, session, flash, redirect, url_for, current_app, request
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

main_bp = Blueprint('main', __name__, template_folder='../static/templates')
@main_bp.route("/")
@main_bp.route("/home")
def home():
    """صفحة الهوم تُظهر نفس المحتوى للجميع،
       لكنها ترسل بيانات إضافية إذا كان المستخدم مسجَّلاً."""
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
        user=user_data,                 # None إذا لم يكن مسجَّلاً
        my_issue_count=my_issues_count  # 0 إذا لم يكن مسجَّلاً
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

