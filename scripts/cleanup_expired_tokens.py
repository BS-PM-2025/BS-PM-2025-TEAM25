# cleanup_expired_tokens.py
"""
Database cleanup script for expired password reset tokens.
This script should be run periodically (e.g., daily) to clean up expired tokens.
You can set this up as a cron job or scheduled task.
"""

from datetime import datetime, timedelta
from flask import current_app
import logging

def cleanup_expired_password_resets(app):
    """
    Remove expired password reset tokens from the database.
    
    Args:
        app: Flask application instance with MongoDB configuration
    """
    with app.app_context():
        try:
            mongo = current_app.mongo
            
            # Calculate cutoff time (remove tokens older than 24 hours)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            # Remove expired tokens
            result = mongo.db.password_resets.delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })
            
            # Also remove very old tokens (even if not technically expired)
            old_result = mongo.db.password_resets.delete_many({
                "created_at": {"$lt": cutoff_time}
            })
            
            total_deleted = result.deleted_count + old_result.deleted_count
            
            if total_deleted > 0:
                logging.info(f"Cleaned up {total_deleted} expired password reset tokens")
            else:
                logging.info("No expired password reset tokens to clean up")
                
            return total_deleted
            
        except Exception as e:
            logging.error(f"Error cleaning up password reset tokens: {e}")
            return 0

def cleanup_old_sessions(app):
    """
    Remove old password reset sessions that have been used or are very old.
    
    Args:
        app: Flask application instance with MongoDB configuration
    """
    with app.app_context():
        try:
            mongo = current_app.mongo
            
            # Remove used tokens older than 1 hour
            used_cutoff = datetime.utcnow() - timedelta(hours=1)
            result = mongo.db.password_resets.delete_many({
                "used": True,
                "created_at": {"$lt": used_cutoff}
            })
            
            logging.info(f"Cleaned up {result.deleted_count} used password reset tokens")
            return result.deleted_count
            
        except Exception as e:
            logging.error(f"Error cleaning up used password reset tokens: {e}")
            return 0

if __name__ == "__main__":
    # This would be run as a standalone script
    # You'll need to import your Flask app here
    
    # Example usage:
    # from your_app import create_app
    # app = create_app()
    # cleanup_expired_password_resets(app)
    # cleanup_old_sessions(app)
    
    print("This script should be run with your Flask app context.")
    print("Example cron job entry (run daily at 2 AM):")
    print("0 2 * * * /path/to/python /path/to/cleanup_expired_tokens.py")