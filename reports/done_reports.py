from flask import (
    Blueprint, render_template, current_app,
    session, flash, redirect, url_for, abort,
    request
)
from bson import ObjectId
from datetime import datetime

done_reports_bp = Blueprint(
    "done_reports",
    __name__,
    template_folder="../templates"
)

@done_reports_bp.route("/admin/done_reports")
def done_issue():
    # → ensure logged in
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    user = mongo.db.users.find_one({"email": session["user"]})
    # → only admins
    if not user or user.get("role") != "admin":
        flash("Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

    # fetch all completed‐work reports
    raw = mongo.db.done_issues.find().sort("timestamp", -1)
    done_reports = []
    for dr in raw:
        # convert ObjectIds to strings
        dr["_id"]               = str(dr["_id"])
        dr["original_issue_id"] = str(dr["original_issue_id"])
        done_reports.append(dr)

    return render_template(
        "done_reports.html",
        user=user,
        done_reports=done_reports
    )


@done_reports_bp.route("/admin/review_done_report/<dr_id>", methods=["POST"])
def review_done_report(dr_id):
    mongo = current_app.mongo

    # auth & role check
    if "user" not in session:
        flash("Please log in", "warning")
        return redirect(url_for("auth.root"))
    user = mongo.db.users.find_one({"email": session["user"]})
    if not user or user.get("role") != "admin":
        flash("Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

    # fetch the done-report
    try:
        dr_obj = ObjectId(dr_id)
    except:
        abort(404)
    dr = mongo.db.done_issues.find_one({"_id": dr_obj})
    if not dr:
        abort(404)

    status = request.form.get("status")
    if status == "accepted":
        # 1) delete the done-report
        mongo.db.done_issues.delete_one({"_id": dr_obj})

        # 2) mark the original issue closed
        orig_id = ObjectId(dr["original_issue_id"])
        mongo.db.issues.update_one(
            {"_id": orig_id},
            {"$set": {
                "status": "done",
            }}
        )

        flash("Report accepted and issue closed.", "success")

    elif status == "rejected":
        reason = request.form.get("rejection_reason", "").strip()
        if not reason:
            flash("Rejection reason required.", "danger")
            return redirect(url_for("done_reports.done_issue"))

        # 1) delete the done-report
        mongo.db.done_issues.delete_one({"_id": dr_obj})

        # 2) revert the original issue back to in-progress
        orig_id = ObjectId(dr["original_issue_id"])
        mongo.db.issues.update_one(
            {"_id": orig_id},
            {"$set": {"status": "in progress"}}
        )

        # 3) record a rejection message for the technician
        mongo.db.rejected_reports.insert_one({
            "original_issue_id": dr["original_issue_id"],
            "technician":        dr["technician"],
            "rejection_reason":  reason,
            "admin":             session["user"],
            "timestamp":         datetime.utcnow().isoformat()
        })

        flash("Report rejected and sent back to technician.", "warning")

    else:
        flash("Unknown action.", "danger")

    return redirect(url_for("done_reports.done_issue"))
