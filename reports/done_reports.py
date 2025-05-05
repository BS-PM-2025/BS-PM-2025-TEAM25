from flask import (
    Blueprint, render_template, current_app,
    session, flash, redirect, url_for, abort
)
from bson import ObjectId

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




