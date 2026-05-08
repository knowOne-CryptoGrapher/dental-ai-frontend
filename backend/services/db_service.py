from auth import get_db

def get_practice(practice_id: str):
    db = get_db()
    return db.practices.find_one({"id": practice_id}, {"_id": 0})
