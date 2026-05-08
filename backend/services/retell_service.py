from llm.cache import get_call_cache

def clear_call_cache(call_id: str):
    cache = get_call_cache()
    cache.end_call(call_id)
