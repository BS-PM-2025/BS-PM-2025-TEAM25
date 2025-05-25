# reports/done_reports.py
from flask import (
    Blueprint, render_template, current_app,
    session, flash, redirect, url_for, abort,
    request, jsonify, send_file
)
from bson import ObjectId
from datetime import datetime
from gridfs import GridFS
import io

from .email_utils import send_email


done_reports_bp = Blueprint(
    "done_reports",
    __name__,
    template_folder="../templates"
)

# ---------- Serve before/after images from GridFS ----------
@done_reports_bp.route("/done_uploads/<file_id>")
def serve_done_upload(file_id):
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

# ---------- JSON API for done reports ----------
@done_reports_bp.route("/api/done_reports")
def api_done_reports():
    docs = current_app.mongo.db.done_issues.find().sort("timestamp", -1)
    out = []
    for dr in docs:
        out.append({
            "_id":                    str(dr["_id"]),
            "before_file_id":         str(dr.get("before_file_id", "")),
            "after_file_id":          str(dr.get("after_file_id", "")),
            "completion_description": dr.get("completion_description", ""),
            "timestamp":              dr.get("timestamp", "")
        })
    return jsonify(done_reports=out)

# ---------- Admin view of done reports ----------
@done_reports_bp.route("/admin/done_reports")
def done_issue():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))
    user_data = current_app.mongo.db.users.find_one({"email": session["user"]})
    if not user_data or user_data.get("role") != "admin":
        flash("Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

    done_reports = []
    for dr in current_app.mongo.db.done_issues.find().sort("timestamp", -1):
        dr["_id"] = str(dr["_id"])
        dr["before_file_id"] = str(dr.get("before_file_id", ""))
        dr["after_file_id"] = str(dr.get("after_file_id", ""))
        dr["completion_description"] = dr.get("completion_description", "")

        # Format timestamp
        try:
            dt = datetime.fromisoformat(dr.get("timestamp", ""))
        except:
            dt = datetime.now()
        dr["display_date"] = dt.strftime("%Y-%m-%d")
        dr["display_time"] = dt.strftime("%H:%M:%S")

        # Pull main issue status
        try:
            orig_id = ObjectId(dr.get("original_issue_id"))
            main_issue = current_app.mongo.db.issues.find_one({"_id": orig_id})
            dr["issue_status"] = main_issue.get("status", "") if main_issue else ""
        except:
            dr["issue_status"] = ""

        done_reports.append(dr)

    return render_template(
        "done_reports.html",
        user=user_data,
        done_reports=done_reports
    )

# ---------- Review (accept/reject) ----------
@done_reports_bp.route("/admin/review_done_report/<dr_id>", methods=["POST"])
def review_done_report(dr_id):
    if "user" not in session:
        flash("Please log in", "warning")
        return redirect(url_for("auth.root"))
    user_data = current_app.mongo.db.users.find_one({"email": session["user"]})
    if not user_data or user_data.get("role") != "admin":
        flash("Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

    try:
        dr_obj = ObjectId(dr_id)
    except:
        abort(404)
    dr = current_app.mongo.db.done_issues.find_one({"_id": dr_obj}) or abort(404)

    status = request.form.get("status")
    orig_id = ObjectId(dr.get("original_issue_id"))
    issue = current_app.mongo.db.issues.find_one({"_id": orig_id}) or abort(404)
    reporter_email = issue.get("reporter_email")

    if status == "accepted":
        current_app.mongo.db.issues.update_one({"_id": orig_id}, {"$set": {"status": "done"}})
        subject = "Your Report Has Been Completed"
        body = (
            f"Hello,\n\nGreat news! Your report #{orig_id} was marked done.\n\n"
            f"View details: {url_for('reports.report_detail', issue_id=str(orig_id), _external=True)}\n"
            f"Thank you!"
        )
        try:
            send_email(reporter_email, subject, body)
            flash("Report accepted and reporter notified.", "success")
        except Exception as e:
            current_app.logger.error(e)
            flash("Accepted but notification failed.", "warning")

    elif status == "rejected":
        reason = request.form.get("rejection_reason", "").strip()
        if not reason:
            flash("Rejection reason required.", "danger")
            return redirect(url_for("done_reports.done_issue"))
        current_app.mongo.db.done_issues.delete_one({"_id": dr_obj})
        current_app.mongo.db.issues.update_one({"_id": orig_id}, {"$set": {"status": "in progress"}})
        current_app.mongo.db.rejected_reports.insert_one({
            "original_issue_id": dr.get("original_issue_id"),
            "technician": dr.get("technician"),
            "rejection_reason": reason,
            "admin": session["user"],
            "timestamp": datetime.utcnow().isoformat()
        })
        flash("Report rejected and sent back.", "warning")

    else:
        flash("Unknown action.", "danger")

    return redirect(url_for("done_reports.done_issue"))
