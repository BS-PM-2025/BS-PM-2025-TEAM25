from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, current_app, abort, send_file, jsonify
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

# ===========================================
# BUSINESS LOGIC FUNCTIONS FOR PRIORITY & SEVERITY
# ===========================================

def get_priority_score(priority):
    """Convert priority to numeric score for sorting (higher = more urgent)"""
    priority_scores = {
        'low': 1,
        'medium': 2,
        'high': 3,
        'critical': 4
    }
    return priority_scores.get(priority.lower() if priority else 'medium', 2)


def get_severity_score(severity):
    """Convert severity to numeric score for sorting (higher = more severe)"""
    severity_scores = {
        'minor': 1,
        'moderate': 2,
        'major': 3,
        'critical': 4
    }
    return severity_scores.get(severity.lower() if severity else 'moderate', 2)


def calculate_urgency_score(priority, severity):
    """Calculate combined urgency score for advanced sorting"""
    priority_weight = 0.6  # Priority has more weight
    severity_weight = 0.4
    
    priority_score = get_priority_score(priority)
    severity_score = get_severity_score(severity)
    
    return (priority_score * priority_weight) + (severity_score * severity_weight)


def validate_priority_severity(priority, severity):
    """Validate priority and severity values"""
    valid_priorities = ['low', 'medium', 'high', 'critical']
    valid_severities = ['minor', 'moderate', 'major', 'critical']
    
    # Validate and set defaults
    if not priority or priority.lower() not in valid_priorities:
        priority = 'medium'
    
    if not severity or severity.lower() not in valid_severities:
        severity = 'moderate'
    
    return priority.lower(), severity.lower()


def get_priority_notification_level(priority, severity):
    """Determine notification urgency based on priority and severity"""
    urgency_score = calculate_urgency_score(priority, severity)
    
    if urgency_score >= 3.5:
        return 'immediate'  # Send immediate notifications
    elif urgency_score >= 2.5:
        return 'urgent'     # Send within 1 hour
    elif urgency_score >= 1.5:
        return 'normal'     # Send within 24 hours
    else:
        return 'low'        # Send in batch notifications


def can_edit_issue(issue, user_email):
    """Determine if a user can edit an issue based on business rules"""
    # Must be the original reporter
    if issue.get("reporter_email") != user_email:
        return False, "You can only edit your own reports."
    
    # Cannot edit completed issues
    if issue.get("status") in ["done", "completed", "closed", "resolved"]:
        return False, "This report cannot be edited as it has been completed."
    
    return True, None


def track_issue_changes(old_issue, new_data, user_email):
    """Track what changes were made to an issue"""
    changes = {}
    
    # Track description changes
    if old_issue.get("description") != new_data.get("description"):
        changes["description"] = {
            "old": old_issue.get("description"),
            "new": new_data.get("description")
        }
    
    # Track category changes
    if old_issue.get("category") != new_data.get("category"):
        changes["category"] = {
            "old": old_issue.get("category"),
            "new": new_data.get("category")
        }
    
    # Track priority changes
    if old_issue.get("priority") != new_data.get("priority"):
        changes["priority"] = {
            "old": old_issue.get("priority"),
            "new": new_data.get("priority")
        }
    
    # Track severity changes
    if old_issue.get("severity") != new_data.get("severity"):
        changes["severity"] = {
            "old": old_issue.get("severity"),
            "new": new_data.get("severity")
        }
    
    # Track location changes
    old_location = old_issue.get("location", {})
    new_location = new_data.get("location", {})
    if old_location != new_location:
        changes["location"] = {
            "old": old_location,
            "new": new_location
        }
    
    # Track address changes
    if old_issue.get("city_street") != new_data.get("city_street"):
        changes["address"] = {
            "old": old_issue.get("city_street"),
            "new": new_data.get("city_street")
        }
    
    # Track image changes
    if old_issue.get("image_file_id") != new_data.get("image_file_id"):
        changes["image"] = {
            "old": str(old_issue.get("image_file_id")) if old_issue.get("image_file_id") else None,
            "new": str(new_data.get("image_file_id")) if new_data.get("image_file_id") else None
        }
    
    return changes


def allowed_file(filename):
    """Check if uploaded file is allowed"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
    
    # Ensure priority and severity have defaults
    if not issue.get("priority"):
        issue["priority"] = "medium"
    if not issue.get("severity"):
        issue["severity"] = "moderate"
    
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
    
    # Get current user data if logged in
    user_data = None
    if "user" in session:
        user_data = mongo.db.users.find_one({"email": session["user"]})
        if user_data:
            user_data.pop("password", None)
    
    return render_template("report_detail.html", issue=issue, user=user_data)

# ---------- Public list of all reports with advanced sorting ----------
@reports_bp.route("/reports")
def public_reports():
    mongo = current_app.mongo
    
    # Get filter parameters
    priority_filter = request.args.get('priority', '')
    severity_filter = request.args.get('severity', '')
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    sort_by = request.args.get('sort', 'urgency')  # Default to urgency sorting
    
    # Build filter query
    filter_query = {}
    if priority_filter:
        filter_query['priority'] = priority_filter
    if severity_filter:
        filter_query['severity'] = severity_filter
    if status_filter:
        filter_query['status'] = status_filter
    if category_filter:
        filter_query['category'] = category_filter
    
    # Get all issues
    issues = list(mongo.db.issues.find(filter_query))
    
    # Apply sorting
    if sort_by == 'urgency':
        # Sort by combined urgency score (priority + severity)
        issues.sort(key=lambda x: calculate_urgency_score(
            x.get('priority', 'medium'), 
            x.get('severity', 'moderate')
        ), reverse=True)
    elif sort_by == 'priority':
        issues.sort(key=lambda x: get_priority_score(x.get('priority', 'medium')), reverse=True)
    elif sort_by == 'severity':
        issues.sort(key=lambda x: get_severity_score(x.get('severity', 'moderate')), reverse=True)
    elif sort_by == 'oldest':
        issues.sort(key=lambda x: x.get('timestamp', ''), reverse=False)
    else:  # newest
        issues.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    categories = sorted({i.get("category", "") for i in mongo.db.issues.find() if i.get("category")})
    
    # Serialize all issues
    serialized_issues = [serialize_issue_for_json(issue) for issue in issues]
    
    return render_template(
        "public_reports.html",
        issues=serialized_issues,
        categories=categories,
        current_filters={
            'priority': priority_filter,
            'severity': severity_filter,
            'status': status_filter,
            'category': category_filter,
            'sort': sort_by
        }
    )

# ---------- Submit a new report with priority/severity ----------
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
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "medium").strip()
        severity = request.form.get("severity", "moderate").strip()
        lat_str = request.form.get("lat", "").strip()
        lng_str = request.form.get("lng", "").strip()

        # Validate coords
        try:
            lat_f, lng_f = float(lat_str), float(lng_str)
        except ValueError:
            flash("Invalid coordinates.", "danger")
            return redirect(url_for("reports.report_issue"))
        if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
            flash("Coordinates out of range.", "danger")
            return redirect(url_for("reports.report_issue"))

        # Validate and set priority/severity
        priority, severity = validate_priority_severity(priority, severity)

        # Save image in GridFS
        image_file = request.files.get("image")
        image_id = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_id = fs.put(image_file.stream, filename=filename, content_type=image_file.mimetype)

        # Calculate urgency score for automatic assignment
        urgency_score = calculate_urgency_score(priority, severity)
        notification_level = get_priority_notification_level(priority, severity)

        issue_data = {
            "reporter_email": session["user"],
            "description": description,
            "city_street": city_street,
            "category": category,
            "priority": priority,
            "severity": severity,
            "urgency_score": urgency_score,
            "notification_level": notification_level,
            "location": {"lat": lat_f, "lng": lng_f},
            "image_file_id": image_id,
            "status": "pending",
            "assigned_to": None,
            "maintenance_email": None,
            "timestamp": datetime.utcnow().isoformat(),
            "edit_count": 0,
            "edit_history": []
        }
        
        result = mongo.db.issues.insert_one(issue_data)
        
        # Send priority-based notifications
        if notification_level == 'immediate':
            # Send immediate notification to all admins
            admins = mongo.db.users.find({"role": "admin"})
            for admin in admins:
                try:
                    send_email(
                        admin["email"],
                        f"🚨 URGENT: {priority.upper()} Priority Report",
                        f"A {priority} priority, {severity} severity issue has been reported.\n\n"
                        f"Description: {description}\n"
                        f"Location: {city_street}\n"
                        f"Urgency Score: {urgency_score:.2f}\n\n"
                        f"View: {url_for('reports.report_detail', issue_id=str(result.inserted_id), _external=True)}"
                    )
                except Exception as e:
                    current_app.logger.error(f"Failed to send urgent notification: {e}")
        
        flash(f"Issue reported successfully with {priority} priority and {severity} severity!", "success")
        return redirect(url_for("reports.report_issue"))

    return render_template("report_issue.html")

# ---------- Enhanced Edit Route with Priority/Severity Support ----------
@reports_bp.route("/reports/edit/<issue_id>", methods=["GET", "POST"])
def edit_issue(issue_id):
    """Enhanced edit with priority/severity tracking"""
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))

    mongo = current_app.mongo
    
    # Validate issue_id
    try:
        oid = ObjectId(issue_id)
    except:
        abort(404)
    
    # Get the issue
    issue = mongo.db.issues.find_one({"_id": oid})
    if not issue:
        abort(404)
    
    # Check edit permissions
    can_edit, error_message = can_edit_issue(issue, session["user"])
    if not can_edit:
        flash(error_message, "danger")
        return redirect(url_for("reports.report_detail", issue_id=issue_id))
    
    if request.method == "POST":
        # Get form data
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "medium").strip()
        severity = request.form.get("severity", "moderate").strip()
        city_street = request.form.get("city_street", "").strip()
        lat = request.form.get("lat")
        lng = request.form.get("lng")
        
        # Validate required fields
        if not description:
            flash("Description is required.", "danger")
            return render_template("edit_issue.html", issue=serialize_issue_for_json(issue))
        
        # Validate and set priority/severity
        priority, severity = validate_priority_severity(priority, severity)
        
        # Prepare update data
        update_data = {
            "description": description,
            "category": category,
            "priority": priority,
            "severity": severity,
            "city_street": city_street,
            "last_modified": datetime.utcnow().isoformat(),
            "modified_by": session["user"]
        }
        
        # Recalculate urgency score
        update_data["urgency_score"] = calculate_urgency_score(priority, severity)
        update_data["notification_level"] = get_priority_notification_level(priority, severity)
        
        # Handle location
        if lat and lng:
            try:
                update_data["location"] = {
                    "lat": float(lat),
                    "lng": float(lng)
                }
                update_data["location_address"] = city_street
            except ValueError:
                flash("Invalid location coordinates.", "danger")
                return render_template("edit_issue.html", issue=serialize_issue_for_json(issue))
        
        # Handle image upload
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename:
                if file and allowed_file(file.filename):
                    try:
                        # Delete old image if exists
                        if issue.get("image_file_id"):
                            fs = GridFS(mongo.db)
                            try:
                                fs.delete(ObjectId(issue["image_file_id"]))
                            except:
                                pass
                        
                        # Save new image
                        fs = GridFS(mongo.db)
                        filename = secure_filename(file.filename)
                        file_id = fs.put(
                            file.stream,
                            filename=filename,
                            content_type=file.content_type or "application/octet-stream"
                        )
                        update_data["image_file_id"] = file_id
                    except Exception as e:
                        current_app.logger.error(f"File upload error: {e}")
                        flash("Error uploading image. Please try again.", "danger")
                        return render_template("edit_issue.html", issue=serialize_issue_for_json(issue))
                else:
                    flash("Invalid file type. Please upload an image.", "danger")
                    return render_template("edit_issue.html", issue=serialize_issue_for_json(issue))
        
        # Track changes
        changes = track_issue_changes(issue, update_data, session["user"])
        
        # Only proceed if there are actual changes
        if changes:
            # Add edit history entry
            edit_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "modified_by": session["user"],
                "changes": changes
            }
            
            # Update edit count
            edit_count = issue.get("edit_count", 0) + 1
            update_data["edit_count"] = edit_count
            
            # Add to edit history
            edit_history = issue.get("edit_history", [])
            edit_history.append(edit_entry)
            update_data["edit_history"] = edit_history
            
            # Update the issue
            result = mongo.db.issues.update_one(
                {"_id": oid},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                flash("Your report has been updated successfully!", "success")
                
                # Check if priority/severity changed significantly
                old_urgency = calculate_urgency_score(
                    issue.get('priority', 'medium'),
                    issue.get('severity', 'moderate')
                )
                new_urgency = update_data["urgency_score"]
                
                # If urgency increased significantly, notify assigned maintenance
                if new_urgency > old_urgency + 0.5 and issue.get("assigned_to"):
                    priority_change = changes.get("priority", {})
                    severity_change = changes.get("severity", {})
                    
                    change_summary = []
                    if priority_change:
                        change_summary.append(f"Priority: {priority_change['old']} → {priority_change['new']}")
                    if severity_change:
                        change_summary.append(f"Severity: {severity_change['old']} → {severity_change['new']}")
                    
                    try:
                        send_email(
                            issue["assigned_to"],
                            f"⚠️ Report {issue_id} Urgency INCREASED",
                            f"Hello,\n\nA report assigned to you has been updated with INCREASED urgency.\n\n"
                            f"Report ID: {issue_id}\n"
                            f"Updated by: {session['user']}\n"
                            f"Changes: {', '.join(change_summary)}\n"
                            f"New Urgency Score: {new_urgency:.2f}\n\n"
                            f"View the updated report: {url_for('reports.report_detail', issue_id=issue_id, _external=True)}"
                        )
                    except Exception as e:
                        current_app.logger.error(f"Email notification error: {e}")
                
                return redirect(url_for("reports.report_detail", issue_id=issue_id))
            else:
                flash("Failed to update the report. Please try again.", "danger")
        else:
            flash("No changes were made.", "info")
    
    # GET request - show edit form
    return render_template("edit_issue.html", issue=serialize_issue_for_json(issue))

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

# ---------- Admin dashboard with advanced priority sorting ----------
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

    # Get sort parameter
    sort_by = request.args.get('sort', 'urgency')  # Default to urgency
    
    # Get all issues
    issues = list(mongo.db.issues.find())
    
    # Apply sorting
    if sort_by == 'urgency':
        # Sort by combined urgency score
        issues.sort(key=lambda x: calculate_urgency_score(
            x.get('priority', 'medium'), 
            x.get('severity', 'moderate')
        ), reverse=True)
    elif sort_by == 'priority':
        issues.sort(key=lambda x: get_priority_score(x.get('priority', 'medium')), reverse=True)
    elif sort_by == 'severity':
        issues.sort(key=lambda x: get_severity_score(x.get('severity', 'moderate')), reverse=True)
    elif sort_by == 'oldest':
        issues.sort(key=lambda x: x.get('timestamp', ''), reverse=False)
    else:  # newest
        issues.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
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
        my_issue_count=my_issue_count,
        current_sort=sort_by
    )

# ---------- Assign a report to maintenance with priority notification ----------
@reports_bp.route("/reports/assign/<issue_id>", methods=["POST"])
def assign_issue(issue_id):
    maintenance_email = request.form.get("maintenance_email", "").strip()
    mongo = current_app.mongo
    try:
        oid = ObjectId(issue_id)
    except:
        abort(404)
    
    issue = mongo.db.issues.find_one({"_id": oid})
    if not issue:
        abort(404)
    
    update_fields = {
        "maintenance_email": maintenance_email or None,
        "assigned_to": maintenance_email or None,
        "status": "assigned" if maintenance_email else "unassigned"
    }
    mongo.db.issues.update_one({"_id": oid}, {"$set": update_fields})

    reporter_email = issue.get("reporter_email")

    if maintenance_email:
        loc = issue.get("location", {})
        map_link = f"https://www.google.com/maps/search/?api=1&query={loc.get('lat','')},"f"{loc.get('lng','')}" if loc.get('lat') is not None else ""
        
        # Get priority and severity for notification
        priority = issue.get('priority', 'medium').title()
        severity = issue.get('severity', 'moderate').title()
        urgency_score = calculate_urgency_score(issue.get('priority', 'medium'), issue.get('severity', 'moderate'))
        notification_level = get_priority_notification_level(issue.get('priority', 'medium'), issue.get('severity', 'moderate'))
        
        # Customize email based on urgency
        if notification_level == 'immediate':
            subject = f"🚨 URGENT ASSIGNMENT: {priority} Priority Report"
            urgency_note = "⚠️ This is a HIGH URGENCY task requiring immediate attention!"
        elif notification_level == 'urgent':
            subject = f"⚡ High Priority Assignment: {priority} Priority Report"
            urgency_note = "⚡ This task should be addressed promptly."
        else:
            subject = f"📋 New Assignment: {priority} Priority Report"
            urgency_note = "📋 Standard priority task assignment."
        
        # notify maintenance
        try:
            send_email(
                maintenance_email,
                subject,
                f"Hello,\n\n{urgency_note}\n\n"
                f"You have been assigned a new report:\n\n"
                f"Priority: {priority}\n"
                f"Severity: {severity}\n"
                f"Urgency Score: {urgency_score:.2f}/4.0\n"
                f"Description: {issue.get('description')}\n"
                f"Location: {issue.get('city_street', 'Not specified')}\n"
                f"Map: {map_link}\n\n"
                f"View details: {url_for('reports.report_detail', issue_id=issue_id, _external=True)}\n\n"
                f"Please prioritize this task based on its {priority.lower()} priority level."
            )
            flash("Issue assigned and emailed.", "success")
        except Exception as e:
            current_app.logger.error(e)
            flash("Assigned but email failed.", "warning")
        
        # notify reporter
        try:
            send_email(
                reporter_email,
                f"Your {priority} Priority Report is Now Assigned",
                f"Hello,\n\nYour {priority.lower()} priority report has been assigned to a maintenance team.\n\n"
                f"Priority Level: {priority}\n"
                f"Severity Level: {severity}\n"
                f"Expected Response Time: {'Immediate' if notification_level == 'immediate' else 'Within 24 hours' if notification_level == 'urgent' else 'Standard processing time'}\n\n"
                f"View status: {url_for('reports.report_detail', issue_id=issue_id, _external=True)}"
            )
        except Exception:
            pass
    else:
        flash("Issue unassigned.", "info")

    return redirect(url_for("reports.admin_dashboard"))

# ---------- Current user's reports with priority sorting ----------
@reports_bp.route("/my_reports")
def my_reports():
    if "user" not in session:
        flash("Please log in first", "warning")
        return redirect(url_for("auth.root"))
    mongo = current_app.mongo
    
    # Get sorting preference
    sort_by = request.args.get('sort', 'urgency')  # Default to urgency
    
    # Get user's issues
    issues = list(mongo.db.issues.find({"reporter_email": session["user"]}))
    
    # Apply sorting
    if sort_by == 'urgency':
        issues.sort(key=lambda x: calculate_urgency_score(
            x.get('priority', 'medium'), 
            x.get('severity', 'moderate')
        ), reverse=True)
    elif sort_by == 'priority':
        issues.sort(key=lambda x: get_priority_score(x.get('priority', 'medium')), reverse=True)
    elif sort_by == 'severity':
        issues.sort(key=lambda x: get_severity_score(x.get('severity', 'moderate')), reverse=True)
    elif sort_by == 'newest':
        issues.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    elif sort_by == 'oldest':
        issues.sort(key=lambda x: x.get('timestamp', ''), reverse=False)
    else:
        # Default: urgency
        issues.sort(key=lambda x: calculate_urgency_score(
            x.get('priority', 'medium'), 
            x.get('severity', 'moderate')
        ), reverse=True)
    
    # Serialize issues for template
    serialized_issues = [serialize_issue_for_json(issue) for issue in issues]
    
    user_data = mongo.db.users.find_one({"email": session["user"]})
    user_data.pop("password", None)
    return render_template(
        "user_dashboard.html",
        issues=serialized_issues,
        user=user_data,
        current_sort=sort_by
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

# ---------- API endpoint for priority/severity statistics ----------
@reports_bp.route("/api/priority-stats")
def get_priority_statistics():
    """Get priority and severity distribution statistics"""
    mongo = current_app.mongo
    
    # Get all issues
    issues = list(mongo.db.issues.find())
    
    # Calculate statistics
    priority_stats = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    severity_stats = {'critical': 0, 'major': 0, 'moderate': 0, 'minor': 0}
    urgency_distribution = []
    
    for issue in issues:
        priority = issue.get('priority', 'medium')
        severity = issue.get('severity', 'moderate')
        
        if priority in priority_stats:
            priority_stats[priority] += 1
        
        if severity in severity_stats:
            severity_stats[severity] += 1
        
        urgency_score = calculate_urgency_score(priority, severity)
        urgency_distribution.append(urgency_score)
    
    # Calculate urgency ranges
    urgent_count = len([score for score in urgency_distribution if score >= 3.0])
    normal_count = len([score for score in urgency_distribution if 2.0 <= score < 3.0])
    low_count = len([score for score in urgency_distribution if score < 2.0])
    
    return jsonify({
        "priority_distribution": priority_stats,
        "severity_distribution": severity_stats,
        "urgency_ranges": {
            "urgent": urgent_count,
            "normal": normal_count,
            "low": low_count
        },
        "total_issues": len(issues),
        "average_urgency": sum(urgency_distribution) / len(urgency_distribution) if urgency_distribution else 0
    })

# ---------- API endpoint for edit history ----------
@reports_bp.route("/api/reports/<issue_id>/edit-history")
def get_edit_history(issue_id):
    """API endpoint to get detailed edit history for an issue"""
    if "user" not in session:
        return {"error": "Authentication required"}, 401
    
    try:
        oid = ObjectId(issue_id)
    except:
        return {"error": "Invalid issue ID"}, 400
    
    mongo = current_app.mongo
    issue = mongo.db.issues.find_one({"_id": oid})
    
    if not issue:
        return {"error": "Issue not found"}, 404
    
    # Check if user has permission to view this issue
    user = mongo.db.users.find_one({"email": session["user"]})
    if not user:
        return {"error": "User not found"}, 401
    
    # Allow access if: owner, assigned maintenance, or admin
    can_view = (
        issue.get("reporter_email") == session["user"] or
        issue.get("assigned_to") == session["user"] or
        user.get("role") == "admin"
    )
    
    if not can_view:
        return {"error": "Access denied"}, 403
    
    edit_history = issue.get("edit_history", [])
    return jsonify({
        "issue_id": str(issue["_id"]),
        "edit_count": issue.get("edit_count", 0),
        "last_modified": issue.get("last_modified"),
        "current_priority": issue.get("priority", "medium"),
        "current_severity": issue.get("severity", "moderate"),
        "current_urgency_score": calculate_urgency_score(
            issue.get("priority", "medium"),
            issue.get("severity", "moderate")
        ),
        "edit_history": edit_history
    })

# ---------- Maintenance dashboard with priority awareness ----------
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

    raw_issues = mongo.db.issues.find({"assigned_to": session["user"]})
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
        
        # Add urgency score for sorting
        i["urgency_score"] = calculate_urgency_score(
            i.get('priority', 'medium'),
            i.get('severity', 'moderate')
        )
            
        issues.append(i)

    # Sort by urgency score (highest priority/severity first)
    issues.sort(key=lambda x: x.get('urgency_score', 0), reverse=True)

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
        "timestamp":              datetime.utcnow().isoformat(),
        "original_priority":      issue.get("priority", "medium"),
        "original_severity":      issue.get("severity", "moderate"),
        "urgency_score":          calculate_urgency_score(
            issue.get("priority", "medium"),
            issue.get("severity", "moderate")
        )
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
        
        # Add priority/severity info for context
        r["priority"] = issue.get("priority", "medium")
        r["severity"] = issue.get("severity", "moderate")
        r["urgency_score"] = calculate_urgency_score(
            issue.get("priority", "medium"),
            issue.get("severity", "moderate")
        )
            
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