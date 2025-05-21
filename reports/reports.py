from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, current_app, abort
)
from werkzeug.utils import secure_filename
from bson import ObjectId
import os
from datetime import datetime
from .email_utils import send_email

reports_bp = Blueprint(
    "reports",
    __name__,
    template_folder="../templates"
)
@reports_bp.route("/admin/test-email")
def test_email():
    # 1) If not logged in, just return 200
    if "user" not in session:
        return "", 200

    # 2) If logged in as admin, send the test email
    user = current_app.mongo.db.users.find_one({"email": session["user"]})
    if user and user.get("role") == "admin":
        send_email(
            user["email"],
            "🐍 Flask-SMTP Test",
            "If you’re reading this, SMTP is working!"
        )

    # 3) Always return 200
    return "", 200
# ---------- تفاصيل بلاغ واحد ----------
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
    # إذا أردت تحويل timestamp لكائن datetime أو أي تنسيق آخر قم هنا
    return render_template("report_detail.html", issue=issue)


# ---------- صفحة عامة لجميع البلاغات ----------
@reports_bp.route("/reports")
def public_reports():
    mongo = current_app.mongo
    issues = list(mongo.db.issues.find().sort("timestamp", -1))
    categories = sorted({i.get("category", "") for i in issues if i.get("category")})
    for i in issues:
        i["_id"] = str(i["_id"])
    return render_template(
        "public_reports.html",
        issues=issues,
        categories=categories
    )


# ---------- صفحة إرسال بلاغ جديد ----------
@reports_bp.route("/report_issue", methods=["GET", "POST"])
def report_issue():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    if request.method == "POST":
        mongo = current_app.mongo
        description  = request.form.get("description", "")
        city_street  = request.form.get("city_street", "")
        category     = request.form.get("category", "")
        lat_str      = request.form.get("lat", "")
        lng_str      = request.form.get("lng", "")

        # Validate coords
        try:
            lat_f, lng_f = float(lat_str), float(lng_str)
        except ValueError:
            flash("Invalid coordinates.", "danger")
            return redirect(url_for("reports.report_issue"))

        if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
            flash("Coordinates out of range.", "danger")
            return redirect(url_for("reports.report_issue"))

        # Handle image
        image_file = request.files.get("image")
        image_path = None
        if image_file and image_file.filename:
            filename      = secure_filename(image_file.filename)
            upload_folder = os.path.join("static", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            save_path     = os.path.join(upload_folder, filename)
            image_file.save(save_path)
            image_path = f"uploads/{filename}"

        issue_data = {
            "reporter_email": session["user"],
            "description":    description,
            "city_street":    city_street,
            "category":       category,
            "location":       {"lat": lat_f, "lng": lng_f},
            "image_path":     image_path,
            "status":         "pending",
            "assigned_to":    None,
            "maintenance_email": None,
            "timestamp":      datetime.utcnow().isoformat()
        }
        mongo.db.issues.insert_one(issue_data)
        flash("Issue reported successfully!", "success")
        return redirect(url_for("reports.report_issue"))

    return render_template("report_issue.html")


# ---------- حذف بلاغ (مستخدم أو أدمن) ----------
@reports_bp.route("/delete_issue/<issue_id>", methods=["POST"])
def delete_issue(issue_id):
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    issue = mongo.db.issues.find_one({"_id": ObjectId(issue_id)})
    if not issue:
        flash("Issue not found.", "danger")
        return redirect(request.referrer or url_for("reports.admin_dashboard"))

    user_data = mongo.db.users.find_one({"email": session["user"]})
    is_admin  = user_data and user_data.get("role") == "admin"
    if issue["reporter_email"] != session["user"] and not is_admin:
        flash("You don't have permission to delete this report.", "danger")
        return redirect(request.referrer or url_for("reports.admin_dashboard"))

    mongo.db.issues.delete_one({"_id": ObjectId(issue_id)})
    flash("Issue deleted successfully.", "success")
    return redirect(request.referrer or url_for("reports.admin_dashboard"))


# ---------- لوحة الأدمن الرئيسية ----------
@reports_bp.route("/admin/issues")
def admin_dashboard():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo     = current_app.mongo
    user_data = mongo.db.users.find_one({"email": session["user"]})
    if not user_data or user_data.get("role") != "admin":
        flash("Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

    # load all issues
    issues = list(mongo.db.issues.find().sort("timestamp", -1))
    for i in issues:
        i["_id"] = str(i["_id"])

    # load maintenance users for the dropdown
    maintenance_users = list(mongo.db.users.find({"role": "maintenance"}))

    # count how many issues this admin has reported
    my_issue_count = mongo.db.issues.count_documents({
        "reporter_email": session["user"]
    })

    # remove sensitive data
    user_data.pop("password", None)

    return render_template(
        "admin_dashboard.html",
        issues=issues,
        maintenance_users=maintenance_users,
        user=user_data,
        my_issue_count=my_issue_count
    )


# ---------- تعيين الصيانة ----------
@reports_bp.route("/reports/assign/<issue_id>", methods=["POST"])
def assign_issue(issue_id):
    maintenance_email = request.form.get("maintenance_email", "").strip()
    mongo = current_app.mongo

    # 1) Update the issue
    update_fields = {}
    if maintenance_email:
        update_fields.update({
            "maintenance_email": maintenance_email,
            "assigned_to":       maintenance_email,
            "status":            "assigned"
        })
    else:
        update_fields.update({
            "maintenance_email": None,
            "assigned_to":       None,
            "status":            "unassigned"
        })

    mongo.db.issues.update_one(
        {"_id": ObjectId(issue_id)},
        {"$set": update_fields}
    )

    # 2) Send notification emails
    issue = mongo.db.issues.find_one({"_id": ObjectId(issue_id)})
    reporter_email = issue.get("reporter_email")

    # — a) To maintenance tech
    if maintenance_email:
        # build Google-Maps link
        loc = issue.get("location", {})
        if isinstance(loc, dict) and "lat" in loc and "lng" in loc:
            lat, lng = loc["lat"], loc["lng"]
            map_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        else:
            map_link = "(none)"

        subject_tech = f"You Have Been Assigned a New Report"
        body_tech = (
            f"Hello,\n\n"
            f"You’ve been assigned new report :\n\n"
            f"Description: {issue.get('description','(none)')}\n"
            f"Location:    {map_link}\n\n"
            f"View details: {url_for('reports.report_detail', issue_id=issue_id, _external=True)}\n\n"
            f"Thanks,\n{current_app.config['MAIL_DEFAULT_SENDER']}"
        )
        try:
            send_email(maintenance_email, subject_tech, body_tech)
            flash("Issue assigned and email sent to maintenance.", "success")
        except Exception as e:
            current_app.logger.error(f"Email to maintenance failed: {e}")
            flash("Assigned, but failed to email maintenance.", "warning")

        # — b) To original reporter
        subject_user = f"Your Report is Now Assigned"
        body_user = (
            f"Hello,\n\n"
            f"Your report has just been assigned to our maintenance team.\n\n"
            f"We’ll keep you updated on its status.\n\n"
            f"View your report: {url_for('reports.report_detail', issue_id=issue_id, _external=True)}\n\n"
            f"Thanks for helping us improve the city,\n"
            f"{current_app.config['MAIL_DEFAULT_SENDER']}"
        )
        try:
            send_email(reporter_email, subject_user, body_user)
        except Exception as e:
            current_app.logger.error(f"Email to reporter failed: {e}")

    else:
        flash("Issue unassigned.", "info")

    return redirect(url_for("reports.admin_dashboard"))
# ---------- البلاغات الخاصة بالمستخدم الحالي ----------
@reports_bp.route("/my_reports")
def my_reports():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo  = current_app.mongo
    issues = list(mongo.db.issues.find({"reporter_email": session["user"]}))
    for i in issues:
        i["_id"] = str(i["_id"])

    user_data = mongo.db.users.find_one({"email": session["user"]})
    user_data.pop("password", None)

    return render_template(
        "user_dashboard.html",
        issues=issues,
        user=user_data
    )


# ---------- API لإرجاع جميع البلاغات بصيغة JSON ----------
@reports_bp.route("/api/issues")
def get_all_issues():
    mongo  = current_app.mongo
    issues = list(mongo.db.issues.find())
    for i in issues:
        i["_id"] = str(i["_id"])
        ts = i.get("timestamp")
        if isinstance(ts, datetime):
            i["timestamp"] = ts.isoformat(timespec="milliseconds") + "Z"
        elif isinstance(ts, str) and "." in ts:
            i["timestamp"] = ts.split(".")[0] + "Z"
    return {"issues": issues}, 200


# ---------- صيانة: لوحة التشغيل ----------
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

    raw_issues = mongo.db.issues.find(
        {"assigned_to": session["user"]}
    ).sort("timestamp", -1)

    issues = []
    for i in raw_issues:
        i["_id"] = str(i["_id"])
        dr = mongo.db.done_issues.find_one({"original_issue_id": i["_id"]})
        if dr and dr.get("status") == "accepted":
            continue
        if dr and dr.get("status") == "rejected":
            i["rejection_reason"] = dr.get("rejection_reason")
            i["awaiting"] = False
        elif dr:
            i["awaiting"] = True
        issues.append(i)

    # count active rejections
    rejected_count = 0
    for r in mongo.db.rejected_reports.find({"technician": session["user"]}):
        try:
            issue = mongo.db.issues.find_one({
                "_id": ObjectId(r["original_issue_id"])
            })
        except:
            continue
        if issue and issue.get("status") not in ("done", "fixed"):
            rejected_count += 1

    return render_template(
        "maintenance_dashboard.html",
        user=user,
        issues=issues,
        rejected_count=rejected_count
    )


# ---------- صيانة: تحديث الحالة (بدون “تم”) ----------
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

    issue = mongo.db.issues.find_one({"_id": ObjectId(issue_id)})
    if not issue or issue.get("assigned_to") != session["user"]:
        flash("Access denied.", "danger")
    else:
        new_status = request.form.get("status")
        if new_status in ["in progress", "resolved"]:
            mongo.db.issues.update_one(
                {"_id": ObjectId(issue_id)},
                {"$set": {"status": new_status}}
            )
            flash("Status updated!", "success")
    return redirect(url_for("reports.maintenance_dashboard"))


# ---------- صيانة: إتمام البلاغ (“تم”) ----------
@reports_bp.route("/maintenance/complete_issue/<issue_id>", methods=["POST"])
def maintenance_complete_issue(issue_id):
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    user = mongo.db.users.find_one({"email": session["user"]})
    if not user or user.get("role") != "maintenance":
        abort(403)

    issue = mongo.db.issues.find_one({"_id": ObjectId(issue_id)})
    if not issue or issue.get("assigned_to") != session["user"]:
        abort(403)

    desc   = request.form.get("completion_description", "")
    before = request.files.get("before_image")
    after  = request.files.get("after_image")

    # Save uploads
    upload_folder = os.path.join("static", "uploads", "done")
    os.makedirs(upload_folder, exist_ok=True)
    def _save(f):
        filename = secure_filename(f.filename)
        path     = os.path.join(upload_folder, filename)
        f.save(path)
        return f"uploads/done/{filename}"

    before_path = _save(before)
    after_path  = _save(after)

    done_doc = {
        "original_issue_id": issue_id,
        "completion_description": desc,
        "before_image": before_path,
        "after_image": after_path,
        "technician": session["user"],
        "timestamp": datetime.utcnow().isoformat()
    }
    mongo.db.done_issues.insert_one(done_doc)

    flash("Work completion report submitted!", "success")
    return redirect(url_for("reports.maintenance_dashboard"))


# ---------- صيانة: البلاغات المرفوضة ----------
@reports_bp.route("/maintenance/rejected_reports")
def rejected_reports():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    user = current_app.mongo.db.users.find_one({"email": session["user"]})
    if not user or user.get("role") != "maintenance":
        flash("Access denied.", "danger")
        return redirect(url_for("reports.maintenance_dashboard"))

    raw = current_app.mongo.db.rejected_reports.find(
        {"technician": session["user"]}
    ).sort("timestamp", -1)

    reports = []
    for r in raw:
        try:
            issue_obj_id = ObjectId(r["original_issue_id"])
        except Exception:
            continue

        issue = current_app.mongo.db.issues.find_one({"_id": issue_obj_id})
        if not issue or issue.get("status") in ("done", "fixed"):
            continue

        r["_id"] = str(r["_id"])
        r["original_issue_id"] = str(r["original_issue_id"])
        reports.append(r)

    return render_template(
        "rejected_reports.html",
        user=user,
        reports=reports
    )


@reports_bp.context_processor
def inject_rejected_count():
    tech = session.get("user")
    if not tech:
        return dict(rejected_count=0)

    count = 0
    for r in current_app.mongo.db.rejected_reports.find({"technician": tech}):
        try:
            issue = current_app.mongo.db.issues.find_one({
                "_id": ObjectId(r["original_issue_id"])
            })
        except:
            continue
        if issue and issue.get("status") not in ("done", "fixed"):
            count += 1

    return dict(rejected_count=count)
