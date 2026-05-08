from auth import get_db

def get_user_by_id(user_id: str):
    db = get_db()
    return db.users.find_one({"id": user_id}, {"_id": 0})
