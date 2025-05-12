from flask import Flask
from flask_pymongo import PyMongo
from auth.main import auth_bp
from main.main import main_bp
from main.user_roles import user_roles_bp
from reports.reports import reports_bp
from reports.done_reports import done_reports_bp

import urllib.parse
import os
import atexit
from dotenv import load_dotenv





# after other blueprints...

load_dotenv()

app = Flask(__name__)



raw_username = os.getenv("raw_username")
raw_password = os.getenv("raw_password")
print("USERNAME VALUE:", raw_username)
print("RAW_PASSWORD:", raw_password)
username = urllib.parse.quote_plus(raw_username)
password = urllib.parse.quote_plus(raw_password)

app.config["MONGO_URI"] = (
    f"mongodb+srv://{username}:{password}@cluster0.05icn.mongodb.net/App"
    "?retryWrites=true&w=majority&appName=Cluster0"
)
app.secret_key = "3ttcwngvw89vtcw5ynvt4qcy0tnqt5"

mongo = PyMongo(app)
app.mongo = mongo

# Register blueprints
app.register_blueprint(done_reports_bp)
app.register_blueprint(user_roles_bp)
app.register_blueprint(auth_bp,  url_prefix="/auth")
app.register_blueprint(main_bp)
app.register_blueprint(reports_bp)

# Graceful shutdown log (no session logic!)
@atexit.register
def on_shutdown():
    print("Server is shutting down.")

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
