# database_setup.py
"""
Database setup script to create necessary indexes for the password reset system.
Run this once after implementing the forgot password feature.
"""

from datetime import datetime, timedelta
from flask import current_app
import logging

def create_password_reset_indexes(app):
    """
    Create database indexes for optimal password reset performance.
    
    Args:
        app: Flask application instance with MongoDB configuration
    """
    with app.app_context():
        try:
            mongo = current_app.mongo
            db = mongo.db
            
            # Create indexes for password_resets collection
            indexes_created = []
            
            # 1. Index on email for quick lookup
            try:
                db.password_resets.create_index("email")
                indexes_created.append("email")
            except Exception as e:
                logging.warning(f"Email index may already exist: {e}")
            
            # 2. Index on token for verification
            try:
                db.password_resets.create_index("token", unique=True)
                indexes_created.append("token (unique)")
            except Exception as e:
                logging.warning(f"Token index may already exist: {e}")
            
            # 3. Index on expires_at for cleanup operations
            try:
                db.password_resets.create_index("expires_at")
                indexes_created.append("expires_at")
            except Exception as e:
                logging.warning(f"Expires_at index may already exist: {e}")
            
            # 4. Compound index for active reset requests
            try:
                db.password_resets.create_index([
                    ("email", 1),
                    ("used", 1),
                    ("expires_at", 1)
                ])
                indexes_created.append("email_used_expires compound")
            except Exception as e:
                logging.warning(f"Compound index may already exist: {e}")
            
            # 5. TTL index for automatic cleanup (expires documents after 24 hours)
            try:
                db.password_resets.create_index(
                    "created_at", 
                    expireAfterSeconds=86400  # 24 hours
                )
                indexes_created.append("TTL on created_at (24h)")
            except Exception as e:
                logging.warning(f"TTL index may already exist: {e}")
            
            # Create indexes for users collection if needed
            try:
                db.users.create_index("email", unique=True)
                indexes_created.append("users.email (unique)")
            except Exception as e:
                logging.warning(f"Users email index may already exist: {e}")
            
            logging.info(f"Created indexes: {', '.join(indexes_created)}")
            return indexes_created
            
        except Exception as e:
            logging.error(f"Error creating password reset indexes: {e}")
            return []

def create_rate_limiting_collection(app):
    """
    Create a collection for rate limiting password reset requests.
    
    Args:
        app: Flask application instance with MongoDB configuration
    """
    with app.app_context():
        try:
            mongo = current_app.mongo
            db = mongo.db
            
            # Create rate limiting collection with TTL
            try:
                # Create TTL index for automatic cleanup (1 hour)
                db.rate_limits.create_index(
                    "expires_at", 
                    expireAfterSeconds=0  # Expire at the time specified in expires_at
                )
                
                # Create index on identifier (email/IP)
                db.rate_limits.create_index("identifier")
                
                # Create compound index for lookups
                db.rate_limits.create_index([
                    ("identifier", 1),
                    ("action", 1),
                    ("expires_at", 1)
                ])
                
                logging.info("Created rate limiting collection and indexes")
                return True
                
            except Exception as e:
                logging.warning(f"Rate limiting indexes may already exist: {e}")
                return False
                
        except Exception as e:
            logging.error(f"Error creating rate limiting collection: {e}")
            return False

def verify_indexes(app):
    """
    Verify that all required indexes exist.
    
    Args:
        app: Flask application instance with MongoDB configuration
    """
    with app.app_context():
        try:
            mongo = current_app.mongo
            db = mongo.db
            
            # Check password_resets indexes
            reset_indexes = list(db.password_resets.list_indexes())
            print("\nPassword Reset Indexes:")
            for idx in reset_indexes:
                print(f"  - {idx['name']}: {idx.get('key', 'N/A')}")
            
            # Check users indexes
            user_indexes = list(db.users.list_indexes())
            print("\nUsers Indexes:")
            for idx in user_indexes:
                print(f"  - {idx['name']}: {idx.get('key', 'N/A')}")
            
            # Check rate_limits indexes if collection exists
            try:
                rate_indexes = list(db.rate_limits.list_indexes())
                print("\nRate Limiting Indexes:")
                for idx in rate_indexes:
                    print(f"  - {idx['name']}: {idx.get('key', 'N/A')}")
            except:
                print("\nRate Limiting Collection: Not created yet")
            
            return True
            
        except Exception as e:
            logging.error(f"Error verifying indexes: {e}")
            return False

if __name__ == "__main__":
    # Example usage - you'll need to import your Flask app
    print("Database setup script for password reset system")
    print("\nTo use this script:")
    print("1. Import your Flask app")
    print("2. Call create_password_reset_indexes(app)")
    print("3. Call create_rate_limiting_collection(app)")
    print("4. Call verify_indexes(app) to check")
    print("\nExample:")
    print("from your_app import create_app")
    print("app = create_app()")
    print("create_password_reset_indexes(app)")
    print("create_rate_limiting_collection(app)")
    print("verify_indexes(app)")