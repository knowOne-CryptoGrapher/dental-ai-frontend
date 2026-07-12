"""
Intelligent transcript parsing for extracting patient information
when Retell's extraction doesn't provide data
"""
import re
from typing import Optional, Dict


def extract_name_from_context(transcript: str) -> Optional[str]:
    """
    Extract patient name by finding what they say after being asked for their name.
    """
    # Split transcript into agent and caller turns
    lines = transcript.split('\n')
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Check if agent is asking for name
        if 'agent:' in line_lower:
            name_requests = [
                'name for the file',
                'can i have your name',
                'what is your name',
                "what's your name",
                'may i have your name',
                'your name please',
                'and your name',
                'your full name',
                'full name',
            ]
            
            if any(req in line_lower for req in name_requests):
                # Next line should be caller's response
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if 'caller:' in next_line.lower() or 'customer:' in next_line.lower() or 'user:' in next_line.lower():
                        # Extract the response (support caller, customer, or user)
                        response = re.sub(r'^(caller|customer|user):\s*', '', next_line, flags=re.IGNORECASE).strip()
                        
                        # Clean up common non-name responses
                        if response and not any(skip in response.lower() for skip in [
                            "i'd rather not",
                            "prefer not",
                            "don't want to",
                            "not comfortable",
                            "skip",
                        ]):
                            # Extract name-like patterns (capitalized words)
                            name_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', response)
                            if name_match:
                                return name_match.group(1)
                            # If no capitals, still return if it looks like a name (2-30 chars)
                            elif 2 <= len(response.split()) <= 4:
                                return response.title()
    
    return None


def extract_reason_from_context(transcript: str) -> Optional[str]:
    """
    Extract call reason from context.
    """
    lines = transcript.split('\n')
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        if 'agent:' in line_lower:
            reason_requests = [
                'reason for',
                'what brings you',
                'how can i help',
                'what can i help',
                'what do you need',
                'what service',
                'looking for a cleaning',
                'checkup',
                'consultation',
            ]
            
            if any(req in line_lower for req in reason_requests):
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if 'caller:' in next_line.lower() or 'customer:' in next_line.lower() or 'user:' in next_line.lower():
                        response = re.sub(r'^(caller|customer|user):\s*', '', next_line, flags=re.IGNORECASE).strip()
                        return categorize_reason(response)
    
    return None


def categorize_reason(reason_text: str) -> str:
    """
    Categorize the reason into standard categories.
    """
    reason_lower = reason_text.lower()
    
    categories = {
        "Emergency - Pain": ["pain", "hurt", "ache", "sore", "throbbing"],
        "Emergency - Trauma": ["broke", "broken", "chipped", "fell", "knocked out", "accident"],
        "Cleaning": ["cleaning", "clean", "hygienist"],
        "Checkup": ["checkup", "check-up", "exam", "examination", "routine"],
        "Consultation": ["consult", "advice", "question", "wondering"],
        "Extraction": ["extraction", "pull", "remove"],
        "Filling": ["filling", "cavity"],
        "Whitening": ["whitening", "whiten", "bleach"],
    }
    
    for category, keywords in categories.items():
        if any(kw in reason_lower for kw in keywords):
            return category
    
    booking_keywords = ["appointment", "book", "schedule", "reschedule", "make an appointment"]
    if any(k in reason_lower for k in booking_keywords):
        return "Appointment Booking"
    return reason_text if len(reason_text) < 100 else "General Inquiry"


def extract_email_from_context(transcript: str) -> Optional[str]:
    """
    Extract email from transcript.
    """
    # Look for standard email patterns first
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, transcript)
    if match:
        return match.group(0)
    
    # Look for spoken email format with better pattern matching
    # Pattern: [anything] at [domain] dot [tld]
    # Captures the username portion right before "at"
    spoken_pattern = r'(?:^|\s|it\'?s\s+|email\s+is\s+)([a-z0-9\s]+?)\s+at\s+([a-z0-9\s]+?)\s+dot\s+([a-z]+)'
    match = re.search(spoken_pattern, transcript, re.IGNORECASE)
    if match:
        # Clean up the username part (remove spaces, handle spelled-out numbers)
        username = match.group(1).strip()
        domain = match.group(2).strip().replace(' ', '')
        tld = match.group(3).strip()
        
        # Remove common filler words from username
        for filler in ['my', 'email', 'is', 'the']:
            username = re.sub(rf'\b{filler}\b', '', username, flags=re.IGNORECASE).strip()
        
        # Convert spelled numbers and remove spaces
        username = username.replace(' ', '').lower()
        # Handle common spelled-out patterns
        number_map = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
        }
        for word, digit in number_map.items():
            username = username.replace(word, digit)
        
        return f"{username}@{domain}.{tld}"
    
    return None


def extract_provider_preference(transcript: str) -> Optional[str]:
    """
    Extract preferred provider name from transcript.
    Looks for patterns like:
    - "with Dr. Smith"
    - "see Dr. Johnson"
    - "prefer Doctor Rodriguez"
    - "request Dr. Lee"
    """
    # Pattern to match common provider request formats
    provider_patterns = [
        r'(?:with|see|prefer|request|book with|schedule with|want)\s+(?:dr\.?|doctor)\s+([a-z]+)',
        r'(?:dr\.?|doctor)\s+([a-z]+)\s+(?:available|if possible)',
        r'(?:is\s+)?(?:dr\.?|doctor)\s+([a-z]+)',
    ]
    
    transcript_lower = transcript.lower()
    
    for pattern in provider_patterns:
        matches = re.finditer(pattern, transcript_lower, re.IGNORECASE)
        for match in matches:
            provider_surname = match.group(1).strip()
            # Return the surname with proper capitalization
            return provider_surname.title()
    
    return None


def smart_extract(transcript: str, call_data: dict) -> Dict[str, Optional[str]]:
    """
    Intelligently extract all information from transcript.
    
    Returns dict with: patient_name, call_reason, patient_email, preferred_provider
    """
    return {
        "patient_name": extract_name_from_context(transcript),
        "call_reason": extract_reason_from_context(transcript),
        "patient_email": extract_email_from_context(transcript),
        "preferred_provider": extract_provider_preference(transcript),
    }
