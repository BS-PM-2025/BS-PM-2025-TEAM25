from flask import Flask, session, current_app
from flask_pymongo import PyMongo
from auth.main import auth_bp
from main.main import main_bp
from main.user_roles import user_roles_bp
from reports.reports import reports_bp
from reports.done_reports import done_reports_bp
from config import Config
from bson import ObjectId
import urllib.parse
import os
import atexit
from dotenv import load_dotenv

# NEW imports for browser-auto-open
import webbrowser
from threading import Timer

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

raw_username = os.getenv("raw_username")
raw_password = os.getenv("raw_password")
username = urllib.parse.quote_plus(raw_username)
password = urllib.parse.quote_plus(raw_password)

app.config["MONGO_URI"] = (
    f"mongodb+srv://{username}:{password}@cluster0.05icn.mongodb.net/App"
    "?retryWrites=true&w=majority&appName=Cluster0"
)
app.secret_key = "3ttcwngvw89vtcw5ynvt4qcy0tnqt5"

mongo = PyMongo(app)
app.mongo = mongo

# ===========================================
# GLOBAL CONTEXT PROCESSOR
# ===========================================
@app.context_processor
def inject_global_vars():
    """Make session, user data, and counts available to all templates"""
    # Always provide session access
    context_vars = {'session': session}
    
    # If no user is logged in, return defaults
    if "user" not in session:
        context_vars.update({
            'user': None,
            'problem_reports_count': 0,
            'rejected_count': 0
        })
        return context_vars
    
    # Get user data from database
    try:
        user_data = mongo.db.users.find_one({"email": session["user"]})
        
        if not user_data:
            context_vars.update({
                'user': None,
                'problem_reports_count': 0,
                'rejected_count': 0
            })
            return context_vars
        
        # Remove password for security
        user_data_safe = user_data.copy()
        user_data_safe.pop("password", None)
        
        # Initialize counts
        problem_reports_count = 0
        rejected_count = 0
        
        # Calculate counts based on user role
        user_role = user_data.get("role", "user")
        
        if user_role == "admin":
            # For admins: count of all pending problem reports
            try:
                problem_reports_count = mongo.db.issue_problems.count_documents({"status": "pending"})
            except Exception as e:
                app.logger.error(f"Error counting admin problem reports: {e}")
                problem_reports_count = 0
                
        elif user_role == "maintenance":
            # For maintenance users: count rejected reports that need attention
            try:
                for r in mongo.db.rejected_reports.find({"technician": session["user"]}):
                    try:
                        oid = ObjectId(r.get("original_issue_id"))
                        issue = mongo.db.issues.find_one({"_id": oid})
                    except:
                        continue
                    if issue and issue.get("status") not in ("done", "fixed"):
                        rejected_count += 1
            except Exception as e:
                app.logger.error(f"Error calculating rejected count: {e}")
                rejected_count = 0
        else:
            # For regular users: count problems with their reports that need action
            try:
                user_reports = list(mongo.db.issues.find({"reporter_email": session["user"]}))
                user_report_ids = [str(report["_id"]) for report in user_reports]
                
                if user_report_ids:
                    problem_reports_count = mongo.db.issue_problems.count_documents({
                        "original_issue_id": {"$in": user_report_ids},
                        "requires_reporter_action": True,
                        "status": {"$in": ["pending", "notified"]}
                    })
            except Exception as e:
                app.logger.error(f"Error calculating user problem reports: {e}")
                problem_reports_count = 0
        
        # Update context with calculated values
        context_vars.update({
            'user': user_data_safe,
            'problem_reports_count': problem_reports_count,
            'rejected_count': rejected_count
        })
        
    except Exception as e:
        app.logger.error(f"Error in global context processor: {e}")
        # Return safe defaults on any error
        context_vars.update({
            'user': None,
            'problem_reports_count': 0,
            'rejected_count': 0
        })
    
    return context_vars

# Register blueprints
app.register_blueprint(done_reports_bp)
app.register_blueprint(user_roles_bp)
app.register_blueprint(auth_bp,  url_prefix="/auth")
app.register_blueprint(main_bp)
app.register_blueprint(reports_bp)

@atexit.register
def on_shutdown():
    print("Server is shutting down.")

if __name__ == "__main__":
    # determine host & port
    host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_RUN_PORT", 5000))

    # schedule the browser to open after a short delay
    def _open_browser():
        webbrowser.open_new(f"http://{host}:{port}/")
    Timer(1, _open_browser).start()

    # start the Flask development server
    app.run(host=host, port=port, debug=True, use_reloader=False)