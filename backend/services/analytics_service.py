from auth import get_db

def record_llm_event(event: dict):
    db = get_db()
    db.llm_routing_logs.insert_one(event)
