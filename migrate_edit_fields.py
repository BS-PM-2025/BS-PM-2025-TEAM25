# migrate_edit_fields.py
from run import app

def migrate_existing_issues():
    with app.app_context():
        mongo = app.mongo
        
        # Update all existing issues to have the new fields
        result = mongo.db.issues.update_many(
            {"edit_count": {"$exists": False}},
            {"$set": {
                "edit_count": 0,
                "edit_history": []
            }}
        )
        
        print(f"Migration completed: Updated {result.modified_count} issues")

if __name__ == "__main__":
    migrate_existing_issues()