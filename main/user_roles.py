# app/user_roles.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from bson import ObjectId
from werkzeug.security import generate_password_hash

user_roles_bp = Blueprint(
    'user_roles',
    __name__,
    template_folder='../templates'
)

@user_roles_bp.before_request
def check_admin():
    if session.get("role") != "admin":
        flash("Access denied: Admins only.", "danger")
        return redirect(url_for("auth.dashboard"))

@user_roles_bp.route("/admin/users/", methods=["GET", "POST"])
def edit_user_roles():
    mongo = current_app.mongo
    # POST: apply updates
    if request.method == "POST":
        user_id     = request.form.get("user_id")
        new_role    = request.form.get("role")
        new_pass    = request.form.get("password")
        update_obj  = {}
        if new_role:
            update_obj["role"] = new_role
        if new_pass:
            update_obj["password"] = generate_password_hash(new_pass)
        if update_obj:
            mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_obj}
            )
            flash("User updated successfully.", "success")
        else:
            flash("No changes submitted.", "info")
        return redirect(url_for("user_roles.edit_user_roles"))

    # GET: show all non-admin users
    users = list(mongo.db.users.find(
        {"role": {"$in": ["user", "maintenance"]}},
        {"password": 0}  # hide password hash
    ))
    return render_template("edit_users.html", users=users)


@user_roles_bp.route("/admin/users/delete/<user_id>", methods=["POST"])
def delete_user(user_id):
    """
    Delete a user by their ObjectId.
    Only admins can hit this because of @before_request.
    """
    mongo = current_app.mongo
    result = mongo.db.users.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count:
        flash("User deleted successfully.", "success")
    else:
        flash("User not found or already deleted.", "warning")
    return redirect(url_for("user_roles.edit_user_roles"))
