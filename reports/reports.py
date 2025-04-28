from datetime import datetime
# reports/reports.py
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, current_app, abort      # ← أضف abort
)
from werkzeug.utils import secure_filename
from bson import ObjectId
import os, datetime

reports_bp = Blueprint(
    "reports",
    __name__,
    template_folder="../templates"      # اتركه كما هو عندك
)

# ---------- صفحة التفاصيل ----------
@reports_bp.route("/report/<issue_id>")
def report_detail(issue_id):
    try:
        _id = ObjectId(issue_id)
    except Exception:
        abort(404)

    mongo = current_app.mongo
    issue = mongo.db.issues.find_one({"_id": _id})
    if not issue:
        abort(404)

    issue["_id"] = str(issue["_id"])
    issue["timestamp"] = issue["timestamp"]
    return render_template("report_detail.html", issue=issue)

# ---------- صفحة جميع البلاغات ----------
@reports_bp.route("/reports")
def public_reports():
    """صفحة عامة تعرض كل البلاغات (قائمة + خريطة)."""
    mongo = current_app.mongo
    issues = list(mongo.db.issues.find().sort("timestamp", -1))
    categories = sorted({i.get("category", "") for i in issues if i.get("category")})
    for i in issues:
        i["_id"] = str(i["_id"])
        i["timestamp"] = i["timestamp"]
    return render_template(
        "public_reports.html",
        issues=issues,
        categories=categories
    )
@reports_bp.route("/report_issue", methods=["GET", "POST"])
def report_issue():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    if request.method == "POST":
        mongo = current_app.mongo

        # Pull form data
        description = request.form.get("description", "")
        city_street = request.form.get("city_street", "")
        category    = request.form.get("category", "")
        lat_str     = request.form.get("lat", "")
        lng_str     = request.form.get("lng", "")

        # Validate coordinates
        try:
            lat_f, lng_f = float(lat_str), float(lng_str)
        except (TypeError, ValueError):
            flash("Invalid coordinates.", "danger")
            return redirect(url_for("reports.report_issue"))

        if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
            flash("Coordinates out of range.", "danger")
            return redirect(url_for("reports.report_issue"))

        # Handle optional image upload
        image_file = request.files.get("image")
        image_path = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            upload_folder = os.path.join("static", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            save_path = os.path.join(upload_folder, filename)
            image_file.save(save_path)
            image_path = f"uploads/{filename}"

        # Build and insert issue
        issue_data = {
            "reporter_email": session["user"],
            "description":    description,
            "city_street":    city_street,
            "category":       category,
            "location":       {"lat": lat_f, "lng": lng_f},
            "image_path":     image_path,
            "status":         "pending",
            "assigned_to":    None,
            "timestamp":       datetime.utcnow().isoformat()

        }
        mongo.db.issues.insert_one(issue_data)
        flash("Issue reported successfully!", "success")
        return redirect(url_for("reports.report_issue"))

    return render_template("report_issue.html")


@reports_bp.route("/delete_issue/<issue_id>", methods=["POST"])
def delete_issue(issue_id):
    """Allow a user to delete their own report."""
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    issue = mongo.db.issues.find_one({"_id": ObjectId(issue_id)})
    if not issue:
        flash("Issue not found.", "danger")
        return redirect(url_for("auth.dashboard"))

    if issue.get("reporter_email") != session["user"]:
        flash("You don't have permission to delete this report.", "danger")
        return redirect(url_for("auth.dashboard"))

    mongo.db.issues.delete_one({"_id": ObjectId(issue_id)})
    flash("Issue deleted successfully.", "success")
    return redirect(url_for("auth.dashboard"))


@reports_bp.route("/admin/issues")
def admin_issues():
    # … your existing admin_issues code …
    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if not user_data or user_data.get("role")!="admin":
        flash("Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))
    issues = list(mongo.db.issues.find().sort("timestamp",-1))
    maintenance_users = list(mongo.db.users.find({"role":"maintenance"}))
    return render_template("admin_issues.html",
                           issues=issues,
                           maintenance_users=maintenance_users)


@reports_bp.route("/admin/update_status/<issue_id>", methods=["POST"])
def update_status(issue_id):
    # … your existing update_status code …
    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    new_status = request.form.get("status")
    issue = mongo.db.issues.find_one({"_id": ObjectId(issue_id)})
    if user_data and (user_data.get("role")=="admin" or 
       (user_data.get("role")=="maintenance" and issue.get("assigned_to")==session["user"])):
        mongo.db.issues.update_one(
            {"_id": ObjectId(issue_id)},
            {"$set": {"status": new_status}}
        )
        flash("Status updated!", "success")
    else:
        flash("Access denied.", "danger")
    return redirect(url_for("auth.dashboard"))




from datetime import datetime

@reports_bp.route("/api/issues")
def get_all_issues():
    mongo = current_app.mongo
    issues = list(mongo.db.issues.find())
    for i in issues:
        i["_id"] = str(i["_id"])
        ts = i.get("timestamp")
        # حوّل دائماً لـ ISO بدون microseconds
        if isinstance(ts, datetime):
            i["timestamp"] = ts.isoformat(timespec="milliseconds") + "Z"
        elif isinstance(ts, str) and "." in ts:
            i["timestamp"] = ts.split(".")[0] + "Z"
    return {"issues": issues}, 200

@reports_bp.route("/admin/assign_issue/<issue_id>", methods=["POST"])
def assign_issue(issue_id):
    # … your existing assign_issue code …
    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if not user_data or user_data.get("role")!="admin":
        flash("Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))
    email = request.form.get("maintenance_email")
    mongo.db.issues.update_one(
        {"_id": ObjectId(issue_id)},
        {"$set": {"assigned_to": email}}
    )
    flash("Assigned!", "success")
    return redirect(url_for("auth.dashboard"))

@reports_bp.route("/my_reports")
def my_reports():
    """
    صفحة تعرض جميع البلاغات التي أبلغها المستخدم الحالي فقط.
    URL  = /my_reports
    endpoint = reports.my_reports
    """
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo  = current_app.mongo
    issues = list(mongo.db.issues.find({"reporter_email": session["user"]}))
    for i in issues:                       # حوّل ObjectId لسلسلة
        i["_id"] = str(i["_id"])

    user_data = mongo.db.users.find_one({"email": session["user"]})
    if user_data and "password" in user_data:
        user_data.pop("password")

    return render_template(
        "user_dashboard.html",   # القالب الذي لديك
        issues=issues,
        user=user_data
    )