from flask import (
    Blueprint, render_template, current_app,
    session, flash, redirect, url_for, abort,
    request, jsonify
)
from bson import ObjectId
from datetime import datetime

done_reports_bp = Blueprint(
    "done_reports",
    __name__,
    template_folder="../templates"
)

@done_reports_bp.route("/api/done_reports")
def api_done_reports():
    docs = current_app.mongo.db.done_issues.find().sort("timestamp", -1)
    out = []
    for dr in docs:
        out.append({
            "_id":                    str(dr["_id"]),
            "before_image":           dr.get("before_image", ""),
            "after_image":            dr.get("after_image", ""),
            "completion_description": dr.get("completion_description", ""),
            "timestamp":              dr.get("timestamp", "")
        })
    return jsonify(done_reports=out)

@done_reports_bp.route("/admin/done_reports")
def done_issue():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))
    user = current_app.mongo.db.users.find_one({"email": session["user"]})
    if not user or user.get("role") != "admin":
        flash("Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

    done_reports = []
    for dr in current_app.mongo.db.done_issues.find().sort("timestamp", -1):
        dr["_id"]                  = str(dr["_id"])
        dr["before_image"]         = dr.get("before_image", "")
        dr["after_image"]          = dr.get("after_image", "")
        dr["completion_description"] = dr.get("completion_description", "")
        try:
            dt = datetime.fromisoformat(dr.get("timestamp", ""))
        except ValueError:
            dt = datetime.now()
        dr["display_date"] = dt.strftime("%Y-%m-%d")
        dr["display_time"] = dt.strftime("%H:%M:%S")
        done_reports.append(dr)

    return render_template(
        "done_reports.html",
        user=user,
        done_reports=done_reports
    )

@done_reports_bp.route("/admin/review_done_report/<dr_id>", methods=["POST"])
def review_done_report(dr_id):
    if "user" not in session:
        flash("Please log in", "warning")
        return redirect(url_for("auth.root"))
    user = current_app.mongo.db.users.find_one({"email": session["user"]})
    if not user or user.get("role") != "admin":
        flash("Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

    try:
        dr_obj = ObjectId(dr_id)
    except:
        abort(404)
    dr = current_app.mongo.db.done_issues.find_one({"_id": dr_obj}) or abort(404)

    status = request.form.get("status")
    orig_id = ObjectId(dr["original_issue_id"])

    if status == "accepted":
        current_app.mongo.db.issues.update_one(
            {"_id": orig_id},
            {"$set": {"status": "done"}}
        )
        flash("Report accepted and issue closed.", "success")

    elif status == "rejected":
        reason = request.form.get("rejection_reason", "").strip()
        if not reason:
            flash("Rejection reason required.", "danger")
            return redirect(url_for("done_reports.done_issue"))

        current_app.mongo.db.done_issues.delete_one({"_id": dr_obj})
        current_app.mongo.db.issues.update_one(
            {"_id": orig_id},
            {"$set": {"status": "in progress"}}
        )
        current_app.mongo.db.rejected_reports.insert_one({
            "original_issue_id": dr["original_issue_id"],
            "technician":        dr["technician"],
            "rejection_reason":  reason,
            "admin":             session["user"],
            "timestamp":         datetime.now().isoformat()
        })
        flash("Report rejected and sent back to technician.", "warning")

    else:
        flash("Unknown action.", "danger")

    return redirect(url_for("done_reports.done_issue"))
