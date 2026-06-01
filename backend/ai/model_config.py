"""
Hardened model configuration for the AI receptionist.

Low temperature, capped tokens, deterministic settings.
Receptionist flows use small fast models.
Classification/fallback uses larger models.
"""

RECEPTIONIST_MODEL_CONFIG = {
    "model": "gpt-4o-mini",        # Fast, cost-effective for receptionist
    "temperature": 0.1,            # Near-deterministic
    "top_p": 0.9,
    "max_tokens": 180,             # Hard cap — forces concise responses, reduces hallucination surface
    "frequency_penalty": 0.3,      # Reduce repetition
    "presence_penalty": 0.0,
}

CLASSIFIER_MODEL_CONFIG = {
    "model": "gpt-4o",             # Better judgment for risk classification
    "temperature": 0.0,            # Fully deterministic for classification
    "max_tokens": 50,              # Classification only needs a short output
}

FALLBACK_MODEL_CONFIG = {
    "model": "claude-sonnet-4-6",  # High-quality fallback
    "temperature": 0.1,
    "max_tokens": 180,
}

SYSTEM_PROMPT_HARDENING = """
You are a dental receptionist assistant. You ONLY answer questions using the
PRACTICE CONTEXT provided above.

RULES (NEVER VIOLATE):
1. If the answer is not in the provided context, say: "I don't have that
   information. Please contact the office directly."
2. Never make statements about insurance coverage or costs.
3. Never give clinical advice, diagnoses, or treatment recommendations.
4. Never make guarantees or commitments on behalf of the practice.
5. Keep all responses under 3 sentences.
6. If uncertain, always transfer to a human.

You are helpful, professional, and brief.
"""
