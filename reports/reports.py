from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, current_app, abort, send_file
)
from werkzeug.utils import secure_filename
from bson import ObjectId
from datetime import datetime
from gridfs import GridFS
import io

from .email_utils import send_email

reports_bp = Blueprint(
    "reports",
    __name__,
    template_folder="../templates"
)

# Helper function to serialize MongoDB documents for JSON
def serialize_issue_for_json(issue):
    """Convert MongoDB document to JSON-serializable format"""
    if issue is None:
        return None
    
    # Convert ObjectId fields to strings
    if "_id" in issue:
        issue["_id"] = str(issue["_id"])
    
    if "image_file_id" in issue and issue["image_file_id"]:
        issue["image_file_id"] = str(issue["image_file_id"])
    
    # Handle timestamp conversion
    if "timestamp" in issue:
        ts = issue["timestamp"]
        if isinstance(ts, datetime):
            issue["timestamp"] = ts.isoformat(timespec="milliseconds") + "Z"
        elif isinstance(ts, str) and "." in ts:
            issue["timestamp"] = ts.split(".")[0] + "Z"
    
    return issue

# ---------- Utility: serve files from GridFS ----------
@reports_bp.route("/uploads/<file_id>")
def serve_upload(file_id):
    mongo = current_app.mongo
    fs = GridFS(mongo.db)
    try:
        grid_out = fs.get(ObjectId(file_id))
    except Exception:
        abort(404)
    return send_file(
        io.BytesIO(grid_out.read()),
        mimetype=grid_out.content_type or "application/octet-stream",
        as_attachment=False,
        download_name=grid_out.filename
    )

# ---------- Test SMTP Email (Admin) ----------
@reports_bp.route("/admin/test-email")
def test_email():
    if "user" not in session:
        return "", 200
    user = current_app.mongo.db.users.find_one({"email": session["user"]})
    if user and user.get("role") == "admin":
        send_email(
            user["email"],
            "🐍 Flask-SMTP Test",
            "If you're reading this, SMTP is working!"
        )
    return "", 200

# ---------- View a single report ----------
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
    
    # Serialize the issue for template use
    issue = serialize_issue_for_json(issue)
    return render_template("report_detail.html", issue=issue)

# ---------- Public list of all reports ----------
@reports_bp.route("/reports")
def public_reports():
    mongo = current_app.mongo
    issues = list(mongo.db.issues.find().sort("timestamp", -1))
    categories = sorted({i.get("category", "") for i in issues if i.get("category")})
    
    # Serialize all issues
    serialized_issues = [serialize_issue_for_json(issue) for issue in issues]
    
    return render_template(
        "public_reports.html",
        issues=serialized_issues,
        categories=categories
    )

# ---------- Submit a new report (store image in GridFS) ----------
@reports_bp.route("/report_issue", methods=["GET", "POST"])
def report_issue():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    fs = GridFS(mongo.db)

    if request.method == "POST":
        description = request.form.get("description", "").strip()
        city_street = request.form.get("city_street", "").strip()
        category    = request.form.get("category", "").strip()
        lat_str     = request.form.get("lat", "").strip()
        lng_str     = request.form.get("lng", "").strip()

        # Validate coords
        try:
            lat_f, lng_f = float(lat_str), float(lng_str)
        except ValueError:
            flash("Invalid coordinates.", "danger")
            return redirect(url_for("reports.report_issue"))
        if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
            flash("Coordinates out of range.", "danger")
            return redirect(url_for("reports.report_issue"))

        # Save image in GridFS
        image_file = request.files.get("image")
        image_id = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_id = fs.put(image_file.stream, filename=filename, content_type=image_file.mimetype)

        issue_data = {
            "reporter_email": session["user"],
            "description":    description,
            "city_street":    city_street,
            "category":       category,
            "location":       {"lat": lat_f, "lng": lng_f},
            "image_file_id":  image_id,
            "status":         "pending",
            "assigned_to":    None,
            "maintenance_email": None,
            "timestamp":      datetime.utcnow().isoformat()
        }
        mongo.db.issues.insert_one(issue_data)
        flash("Issue reported successfully!", "success")
        return redirect(url_for("reports.report_issue"))

    return render_template("report_issue.html")

# ---------- Delete a report ----------
@reports_bp.route("/delete_issue/<issue_id>", methods=["POST"])
def delete_issue(issue_id):
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    try:
        oid = ObjectId(issue_id)
    except:
        flash("Invalid report ID.", "danger")
        return redirect(request.referrer or url_for("reports.admin_dashboard"))
    issue = mongo.db.issues.find_one({"_id": oid})
    if not issue:
        flash("Issue not found.", "danger")
        return redirect(request.referrer or url_for("reports.admin_dashboard"))

    user_data = mongo.db.users.find_one({"email": session["user"]})
    is_admin = user_data and user_data.get("role") == "admin"
    if issue["reporter_email"] != session["user"] and not is_admin:
        flash("Permission denied.", "danger")
        return redirect(request.referrer or url_for("reports.admin_dashboard"))

    mongo.db.issues.delete_one({"_id": oid})
    flash("Issue deleted successfully.", "success")
    return redirect(request.referrer or url_for("reports.admin_dashboard"))

# ---------- Admin dashboard ----------
@reports_bp.route("/admin/issues")
def admin_dashboard():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if not user_data or user_data.get("role") != "admin":
        flash("Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

    issues = list(mongo.db.issues.find().sort("timestamp", -1))
    # Serialize issues for template
    serialized_issues = [serialize_issue_for_json(issue) for issue in issues]
    
    maintenance_users = list(mongo.db.users.find({"role": "maintenance"}))
    my_issue_count = mongo.db.issues.count_documents({"reporter_email": session["user"]})
    user_data.pop("password", None)

    return render_template(
        "admin_dashboard.html",
        issues=serialized_issues,
        maintenance_users=maintenance_users,
        user=user_data,
        my_issue_count=my_issue_count
    )

# ---------- Assign a report to maintenance ----------
@reports_bp.route("/reports/assign/<issue_id>", methods=["POST"])
def assign_issue(issue_id):
    maintenance_email = request.form.get("maintenance_email", "").strip()
    mongo = current_app.mongo
    try:
        oid = ObjectId(issue_id)
    except:
        abort(404)
    update_fields = {
        "maintenance_email": maintenance_email or None,
        "assigned_to":       maintenance_email or None,
        "status":            "assigned" if maintenance_email else "unassigned"
    }
    mongo.db.issues.update_one({"_id": oid}, {"$set": update_fields})

    issue = mongo.db.issues.find_one({"_id": oid})
    reporter_email = issue.get("reporter_email")

    if maintenance_email:
        loc = issue.get("location", {})
        map_link = f"https://www.google.com/maps/search/?api=1&query={loc.get('lat','')},"f"{loc.get('lng','')}" if loc.get('lat') is not None else ""
        # notify maintenance
        try:
            send_email(
                maintenance_email,
                "You Have Been Assigned a New Report",
                f"Hello,\n\nDescription: {issue.get('description')}\nLocation: {map_link}\n"
                f"{url_for('reports.report_detail', issue_id=issue_id, _external=True)}"
            )
            flash("Issue assigned and emailed.", "success")
        except Exception as e:
            current_app.logger.error(e)
            flash("Assigned but email failed.", "warning")
        # notify reporter
        try:
            send_email(
                reporter_email,
                "Your Report is Now Assigned",
                f"Hello,\n\nYour report has been assigned.\n"
                f"{url_for('reports.report_detail', issue_id=issue_id, _external=True)}"
            )
        except Exception:
            pass
    else:
        flash("Issue unassigned.", "info")

    return redirect(url_for("reports.admin_dashboard"))

# ---------- Current user's reports ----------
@reports_bp.route("/my_reports")
def my_reports():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))
    mongo = current_app.mongo
    issues = list(mongo.db.issues.find({"reporter_email": session["user"]}))
    # Serialize issues for template
    serialized_issues = [serialize_issue_for_json(issue) for issue in issues]
    
    user_data = mongo.db.users.find_one({"email": session["user"]})
    user_data.pop("password", None)
    return render_template(
        "user_dashboard.html",
        issues=serialized_issues,
        user=user_data
    )

# ---------- JSON API for all issues ----------
@reports_bp.route("/api/issues")
def get_all_issues():
    mongo = current_app.mongo
    issues = list(mongo.db.issues.find())
    
    # Use the helper function to serialize each issue
    serialized_issues = [serialize_issue_for_json(issue) for issue in issues]
    
    return {"issues": serialized_issues}, 200

# ---------- Additional API endpoints ----------
@reports_bp.route("/api/issues/<issue_id>")
def get_issue_by_id(issue_id):
    """Get a single issue by ID"""
    mongo = current_app.mongo
    try:
        issue = mongo.db.issues.find_one({"_id": ObjectId(issue_id)})
        if not issue:
            return {"error": "Issue not found"}, 404
        
        serialized_issue = serialize_issue_for_json(issue)
        return {"issue": serialized_issue}, 200
    except Exception as e:
        return {"error": "Invalid issue ID"}, 400

@reports_bp.route("/api/issues/user/<user_email>")
def get_user_issues(user_email):
    """Get all issues for a specific user"""
    mongo = current_app.mongo
    issues = list(mongo.db.issues.find({"reporter_email": user_email}))
    
    serialized_issues = [serialize_issue_for_json(issue) for issue in issues]
    
    return {"issues": serialized_issues}, 200

# ---------- Maintenance dashboard ----------
@reports_bp.route("/maintenance/dashboard")
def maintenance_dashboard():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))
    mongo = current_app.mongo
    user = mongo.db.users.find_one({"email": session["user"]})
    if not user or user.get("role") != "maintenance":
        flash("Access denied.", "danger")
        return redirect(url_for("auth.dashboard"))

    raw_issues = mongo.db.issues.find({"assigned_to": session["user"]}).sort("timestamp", -1)
    issues = []
    for i in raw_issues:
        str_id = str(i["_id"])
        i["_id"] = str_id
        i["location"] = i.get("location", {})
        dr = mongo.db.done_issues.find_one({"original_issue_id": str_id})
        if dr and dr.get("status") == "accepted":
            continue
        if dr and dr.get("status") == "rejected":
            i["rejection_reason"] = dr.get("rejection_reason")
            i["awaiting"] = False
        elif dr:
            i["awaiting"] = True
        
        # Serialize image_file_id if present
        if i.get("image_file_id"):
            i["image_file_id"] = str(i["image_file_id"])
            
        issues.append(i)

    rejected_count = 0
    for r in mongo.db.rejected_reports.find({"technician": session["user"]}):
        try:
            orig_id = ObjectId(r.get("original_issue_id"))
            main_issue = mongo.db.issues.find_one({"_id": orig_id})
        except:
            continue
        if main_issue and main_issue.get("status") not in ("done", "fixed"):
            rejected_count += 1

    return render_template(
        "maintenance_dashboard.html",
        user=user,
        issues=issues,
        rejected_count=rejected_count
    )

# ---------- Maintenance: update status ----------
@reports_bp.route("/maintenance/update_status/<issue_id>", methods=["POST"])
def maintenance_update_status(issue_id):
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))
    mongo = current_app.mongo
    user = mongo.db.users.find_one({"email": session["user"]})
    if not user or user.get("role") != "maintenance":
        flash("Access denied.", "danger")
        return redirect(url_for("reports.maintenance_dashboard"))
    try:
        oid = ObjectId(issue_id)
    except:
        abort(404)
    issue = mongo.db.issues.find_one({"_id": oid})
    if not issue or issue.get("assigned_to") != session["user"]:
        flash("Access denied.", "danger")
    else:
        new_status = request.form.get("status")
        if new_status in ["in progress", "resolved"]:
            mongo.db.issues.update_one({"_id": oid}, {"$set": {"status": new_status}})
            flash("Status updated!", "success")
    return redirect(url_for("reports.maintenance_dashboard"))

# ---------- Maintenance: complete issue ----------
@reports_bp.route("/maintenance/complete_issue/<issue_id>", methods=["POST"])
def maintenance_complete_issue(issue_id):
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))
    mongo = current_app.mongo
    fs = GridFS(mongo.db)
    user = mongo.db.users.find_one({"email": session["user"]})
    if not user or user.get("role") != "maintenance":
        abort(403)
    try:
        oid = ObjectId(issue_id)
    except:
        abort(404)
    issue = mongo.db.issues.find_one({"_id": oid})
    if not issue or issue.get("assigned_to") != session["user"]:
        abort(403)

    desc   = request.form.get("completion_description", "").strip()
    before = request.files.get("before_image")
    after  = request.files.get("after_image")

    before_id = fs.put(before.stream, filename=secure_filename(before.filename), content_type=before.mimetype) if before and before.filename else None
    after_id  = fs.put(after.stream, filename=secure_filename(after.filename), content_type=after.mimetype) if after and after.filename else None

    done_doc = {
        "original_issue_id":      str(oid),
        "completion_description": desc,
        "before_file_id":         before_id,
        "after_file_id":          after_id,
        "technician":             session["user"],
        "timestamp":              datetime.utcnow().isoformat()
    }
    mongo.db.done_issues.insert_one(done_doc)

    flash("Work completion report submitted!", "success")
    return redirect(url_for("reports.maintenance_dashboard"))

# ---------- Maintenance: view rejected reports ----------
@reports_bp.route("/maintenance/rejected_reports")
def rejected_reports():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))
    user = current_app.mongo.db.users.find_one({"email": session["user"]})
    if not user or user.get("role") != "maintenance":
        flash("Access denied.", "danger")
        return redirect(url_for("reports.maintenance_dashboard"))

    raw = current_app.mongo.db.rejected_reports.find({"technician": session["user"]}).sort("timestamp", -1)
    reports = []
    for r in raw:
        try:
            oid = ObjectId(r.get("original_issue_id"))
        except:
            continue
        issue = current_app.mongo.db.issues.find_one({"_id": oid})
        if not issue or issue.get("status") in ("done","fixed"):
            continue
        r["_id"] = str(r["_id"])
        r["original_issue_id"] = str(r["original_issue_id"])
        
        # Serialize image_file_id if present in the original issue
        if issue.get("image_file_id"):
            r["image_file_id"] = str(issue["image_file_id"])
            
        reports.append(r)

    return render_template(
        "rejected_reports.html",
        user=user,
        reports=reports
    )

# ---------- Context processor: rejected count ----------
@reports_bp.context_processor
def inject_rejected_count():
    tech = session.get("user")
    if not tech:
        return dict(rejected_count=0)

    count = 0
    for r in current_app.mongo.db.rejected_reports.find({"technician": tech}):
        try:
            oid = ObjectId(r.get("original_issue_id"))
            issue = current_app.mongo.db.issues.find_one({"_id": oid})
        except:
            continue
        if issue and issue.get("status") not in ("done","fixed"):
            count += 1

    return dict(rejected_count=count)

# ---------- Tracking page ----------
@reports_bp.route("/tracking")
def tracking():
    return render_template("tracking.html")