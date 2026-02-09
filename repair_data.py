from app import create_app
from models import mongo

def repair_data():
    app = create_app()
    with app.app_context():
        print("Starting data repair...")
        
        # 1. Update 'Submitted' to 'Pending'
        # This fixes the issue where 'submitted' was used as a status
        result_submitted = mongo.db.applications.update_many(
            {'status': 'Submitted'},
            {'$set': {'status': 'Pending'}}
        )
        print(f"Updated {result_submitted.modified_count} records from 'Submitted' to 'Pending'.")

        # 2. Update 'Under Review' to 'Pending' (just in case)
        result_review = mongo.db.applications.update_many(
            {'status': 'Under Review'},
            {'$set': {'status': 'Pending'}}
        )
        print(f"Updated {result_review.modified_count} records from 'Under Review' to 'Pending'.")

        # 3. Update NULL/Missing/Empty status to 'Pending'
        # Using $or for efficiency
        result_missing = mongo.db.applications.update_many(
            {'$or': [
                {'status': {'$exists': False}},
                {'status': None},
                {'status': ''}
            ]},
            {'$set': {'status': 'Pending'}}
        )
        
        print(f"Updated {result_missing.modified_count} records with missing/null/empty status to 'Pending'.")
        
        print("Data repair complete.")

if __name__ == '__main__':
    repair_data()
