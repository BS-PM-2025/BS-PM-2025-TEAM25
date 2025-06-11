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

# ---------- JSON API for done reports with ratings ----------
@done_reports_bp.route("/api/done_reports")
def api_done_reports():
    mongo = current_app.mongo
    docs = mongo.db.done_issues.find().sort("timestamp", -1)
    out = []
    
    for dr in docs:
        # Get average rating for this report
        report_id = str(dr["_id"])
        ratings = list(mongo.db.report_ratings.find({"report_id": report_id}))
        
        avg_rating = 0
        rating_count = len(ratings)
        
        if rating_count > 0:
            total_rating = sum(r.get("rating", 0) for r in ratings)
            avg_rating = round(total_rating / rating_count, 1)
        
        # Check if current user has rated this report
        user_rating = None
        if "user" in session:
            user_rating_doc = mongo.db.report_ratings.find_one({
                "report_id": report_id,
                "user_email": session["user"]
            })
            if user_rating_doc:
                user_rating = user_rating_doc.get("rating")
        
        out.append({
            "_id": report_id,
            "before_file_id": str(dr.get("before_file_id", "")),
            "after_file_id": str(dr.get("after_file_id", "")),
            "completion_description": dr.get("completion_description", ""),
            "timestamp": dr.get("timestamp", ""),
            "technician": dr.get("technician", ""),
            "category": dr.get("category", ""),
            "avg_rating": avg_rating,
            "rating_count": rating_count,
            "user_rating": user_rating
        })
    
    # Sort by rating if requested
    sort_by = request.args.get('sort', '')
    if sort_by == 'rating':
        out.sort(key=lambda x: x['avg_rating'], reverse=True)
    
    return jsonify(done_reports=out)

# ---------- API endpoint for submitting ratings ----------
@done_reports_bp.route("/api/rate_report", methods=["POST"])
def rate_report():
    if "user" not in session:
        return jsonify({"success": False, "message": "You must be logged in to rate reports"}), 401
    
    mongo = current_app.mongo
    
    data = request.json
    report_id = data.get("report_id")
    rating = data.get("rating")
    
    # Validate inputs
    if not report_id or not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({"success": False, "message": "Invalid rating data"}), 400
    
    # Check if report exists
    try:
        report = mongo.db.done_issues.find_one({"_id": ObjectId(report_id)})
        if not report:
            return jsonify({"success": False, "message": "Report not found"}), 404
    except:
        return jsonify({"success": False, "message": "Invalid report ID"}), 400
    
    # Check if user has already rated this report
    existing_rating = mongo.db.report_ratings.find_one({
        "report_id": report_id,
        "user_email": session["user"]
    })
    
    if existing_rating:
        # Update existing rating
        mongo.db.report_ratings.update_one(
            {"_id": existing_rating["_id"]},
            {"$set": {
                "rating": rating,
                "updated_at": datetime.utcnow().isoformat()
            }}
        )
        action = "updated"
    else:
        # Create new rating
        mongo.db.report_ratings.insert_one({
            "report_id": report_id,
            "user_email": session["user"],
            "rating": rating,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        })
        action = "submitted"
    
    # Get updated average rating
    ratings = list(mongo.db.report_ratings.find({"report_id": report_id}))
    avg_rating = 0
    rating_count = len(ratings)
    
    if rating_count > 0:
        total_rating = sum(r.get("rating", 0) for r in ratings)
        avg_rating = round(total_rating / rating_count, 1)
    
    return jsonify({
        "success": True,
        "message": f"Rating {action} successfully",
        "avg_rating": avg_rating,
        "rating_count": rating_count
    })

# ---------- API endpoint for getting report ratings ----------
@done_reports_bp.route("/api/report_ratings/<report_id>")
def get_report_ratings(report_id):
    mongo = current_app.mongo
    
    # Get all ratings for this report
    ratings = list(mongo.db.report_ratings.find({"report_id": report_id}))
    
    # Calculate average rating
    avg_rating = 0
    rating_count = len(ratings)
    
    if rating_count > 0:
        total_rating = sum(r.get("rating", 0) for r in ratings)
        avg_rating = round(total_rating / rating_count, 1)
    
    # Check if current user has rated this report
    user_rating = None
    if "user" in session:
        user_rating_doc = mongo.db.report_ratings.find_one({
            "report_id": report_id,
            "user_email": session["user"]
        })
        if user_rating_doc:
            user_rating = user_rating_doc.get("rating")
    
    # Get rating distribution
    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in ratings:
        r_value = r.get("rating")
        if r_value in distribution:
            distribution[r_value] += 1
    
    return jsonify({
        "avg_rating": avg_rating,
        "rating_count": rating_count,
        "user_rating": user_rating,
        "distribution": distribution
    })

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
        
        # Get ratings info
        ratings = list(current_app.mongo.db.report_ratings.find({"report_id": dr["_id"]}))
        rating_count = len(ratings)
        avg_rating = 0
        if rating_count > 0:
            total_rating = sum(r.get("rating", 0) for r in ratings)
            avg_rating = round(total_rating / rating_count, 1)
        
        dr["avg_rating"] = avg_rating
        dr["rating_count"] = rating_count

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
            f"You can now rate the quality of the repair work on our 'Completed Reports' page.\n"
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


# Add this route to the done_reports.py file
@done_reports_bp.route("/done_reports_public")
def done_reports_public():
    """Public view of completed reports for all users"""
    user_data = None
    if "user" in session:
        user_data = current_app.mongo.db.users.find_one({"email": session["user"]})
        if user_data:
            user_data.pop("password", None)
    
    return render_template(
        "done_reports_public.html",
        user=user_data
    )