# reports/reports.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename
from bson import ObjectId  # Convert string IDs to ObjectId if needed
import os
import datetime

reports_bp = Blueprint('reports', __name__, template_folder='../templates')

@reports_bp.route("/report_issue", methods=["GET", "POST"])
def report_issue():
    """Allows a user to report a new road issue."""
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    if request.method == "POST":
        mongo = current_app.mongo

        # 1. Get form data
        description = request.form.get("description")
        lat_str = request.form.get("lat")
        lng_str = request.form.get("lng")

        # 2. Validate and convert lat/lng to floats
        try:
            lat_f = float(lat_str)
            lng_f = float(lng_str)
        except ValueError:
            flash("Invalid coordinates. Please enter valid numeric latitude and longitude.", "danger")
            return redirect(url_for("reports.report_issue"))

        # Optional: range checks
        if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
            flash("Coordinates out of range. Please provide valid lat/lng values.", "danger")
            return redirect(url_for("reports.report_issue"))

        # 3. Handle image upload (optional)
        image_file = request.files.get("image")
        image_path = None
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            upload_folder = os.path.join("static", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            save_path = os.path.join(upload_folder, filename)
            image_file.save(save_path)
            image_path = f"uploads/{filename}"

        # 4. Insert document into "issues" collection
        issue_data = {
            "reporter_email": session["user"],
            "description": description,
            "location": {
                "lat": lat_f,
                "lng": lng_f
            },
            "image_path": image_path,
            "status": "pending",
            "assigned_to": None,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        mongo.db.issues.insert_one(issue_data)

        flash("Issue reported successfully!", "success")
        return redirect(url_for("reports.report_issue"))

    # GET request -> show the form
    return render_template("report_issue.html")

@reports_bp.route("/admin/issues")
def admin_issues():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if not user_data or user_data.get("role") != "admin":
        flash("Access denied: Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

    all_issues = list(mongo.db.issues.find().sort("timestamp", -1))
    # Get all maintenance users from DB
    maintenance_users = list(mongo.db.users.find({"role": "maintenance"}))

    return render_template(
        "admin_issues.html",
        issues=all_issues,
        maintenance_users=maintenance_users
    )



@reports_bp.route("/admin/update_status/<issue_id>", methods=["POST"])
def update_status(issue_id):
    """
    Admin or Maintenance can update the status of an issue.
    Admin can update any issue.
    Maintenance can only update if the issue is assigned to them.
    """
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if not user_data:
        flash("User not found.", "danger")
        return redirect(url_for("auth.root"))

    # Grab new status from form
    new_status = request.form.get("status")
    if not new_status:
        flash("No status selected.", "warning")
        return redirect(url_for("auth.dashboard"))

    role = user_data.get("role")
    issue_obj = mongo.db.issues.find_one({"_id": ObjectId(issue_id)})

    if not issue_obj:
        flash("Issue not found.", "danger")
        return redirect(url_for("auth.dashboard"))

    if role == "admin":
        # Admin can update any issue
        mongo.db.issues.update_one(
            {"_id": ObjectId(issue_id)},
            {"$set": {"status": new_status}}
        )
        flash("Issue status updated by Admin!", "success")

    elif role == "maintenance":
        # Maintenance can only update if assigned_to == their email
        if issue_obj.get("assigned_to") == session["user"]:
            mongo.db.issues.update_one(
                {"_id": ObjectId(issue_id)},
                {"$set": {"status": new_status}}
            )
            flash("Issue status updated by Maintenance!", "success")
        else:
            flash("Access denied: Issue not assigned to you.", "danger")

    else:
        # Regular user => no permission
        flash("Access denied.", "danger")

    return redirect(url_for("auth.dashboard"))


@reports_bp.route("/api/issues")
def get_all_issues():
    """Return all issues as JSON (for map integration or other uses)."""
    mongo = current_app.mongo
    issues = list(mongo.db.issues.find())
    for issue in issues:
        issue["_id"] = str(issue["_id"])  # Convert ObjectId to string for JSON
    return {"issues": issues}, 200


@reports_bp.route("/admin/assign_issue/<issue_id>", methods=["POST"])
def assign_issue(issue_id):
    """Admin can assign an issue to a maintenance user."""
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if not user_data or user_data.get("role") != "admin":
        flash("Access denied: Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

    # Get the maintenance user's email from the form
    maintenance_email = request.form.get("maintenance_email")
    if not maintenance_email:
        flash("Please select a maintenance user.", "warning")
        return redirect(url_for("auth.dashboard"))

    # Update the "assigned_to" field of the issue
    result = mongo.db.issues.update_one(
        {"_id": ObjectId(issue_id)},
        {"$set": {"assigned_to": maintenance_email}}
    )

    if result.modified_count > 0:
        flash("Issue assigned successfully!", "success")
    else:
        flash("No changes made. Check if the issue ID is valid.", "info")

    return redirect(url_for("auth.dashboard"))
