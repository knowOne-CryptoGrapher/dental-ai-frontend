"""
Provider Scheduling Logic
Handles availability validation, conflict detection, and smart routing
"""
from datetime import datetime, time, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


DAY_ABBREVIATIONS = {
    # Full names
    "monday": "mon", "tuesday": "tue", "wednesday": "wed",
    "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun",
    # 3-letter abbreviations (already correct)
    "mon": "mon", "tue": "tue", "wed": "wed",
    "thu": "thu", "fri": "fri", "sat": "sat", "sun": "sun",
    # 2-letter variants
    "mo": "mon", "tu": "tue", "we": "wed",
    "th": "thu", "fr": "fri", "sa": "sat", "su": "sun",
}

def get_day_name(date: datetime) -> str:
    """
    Return the 3-letter lowercase day abbreviation for a date.
    Normalizes any common day name format to match DB working_hours keys
    (mon, tue, wed, thu, fri, sat, sun).
    """
    full_name = date.strftime('%A').lower()  # e.g. "friday"
    return DAY_ABBREVIATIONS.get(full_name, full_name[:3].lower())


def time_to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes since midnight"""
    h, m = map(int, time_str.split(':'))
    return h * 60 + m


def minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight to HH:MM"""
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def validate_provider_availability(
    provider: dict,
    date: str,
    time_slot: str,
    location_id: str,
    appointment_type: str
) -> dict:
    """
    Validate if provider can take an appointment at the given time.
    
    Returns: {
        "available": bool,
        "reason": str (if not available)
    }
    """
    # Check if provider is active
    if not provider.get('is_active', True):
        return {"available": False, "reason": "Provider is inactive"}
    
    # Check if provider works at this location
    location_ids = provider.get('location_ids', [])
    legacy_location = provider.get('location_id')
    if legacy_location and not location_ids:
        location_ids = [legacy_location]
    
    if location_id and location_id not in location_ids:
        return {"available": False, "reason": f"Provider does not work at this location"}
    
    # Check if provider handles this appointment type
    appointment_types = provider.get('appointment_types', [])
    if appointment_type and appointment_type not in appointment_types:
        return {"available": False, "reason": f"Provider does not handle '{appointment_type}' appointments"}
    
    # Check if provider works on this day
    day_name = get_day_name(datetime.fromisoformat(date))
    working_hours = provider.get('working_hours', {})
    day_schedule = working_hours.get(day_name, [])
    
    if not day_schedule:
        return {"available": False, "reason": f"Provider does not work on {day_name.capitalize()}"}
    
    # Check if appointment time falls within working hours
    appointment_minutes = time_to_minutes(time_slot)
    time_is_available = False
    
    for block in day_schedule:
        start_minutes = time_to_minutes(block.get('start', '09:00'))
        end_minutes = time_to_minutes(block.get('end', '17:00'))
        
        # Check if appointment time is within this block
        # Assuming 30-minute appointments
        if start_minutes <= appointment_minutes < end_minutes - 30:
            time_is_available = True
            break
    
    if not time_is_available:
        return {"available": False, "reason": f"Time {time_slot} is outside provider's working hours"}
    
    return {"available": True, "reason": None}


async def check_provider_conflicts(db, provider_id: str, date: str, time_slot: str) -> bool:
    """
    Check if provider already has an appointment at this time.
    Returns True if there's a conflict (double-booked)
    """
    # Check for existing appointments at this time
    existing = await db.appointments.find_one({
        "provider_id": provider_id,
        "appointment_date": date,
        "appointment_time": time_slot,
        "status": {"$nin": ["cancelled", "no_show"]}
    })
    
    return existing is not None


async def get_provider_availability_slots(
    db,
    provider_id: str,
    date: str,
    location_id: Optional[str] = None,
    appointment_type: Optional[str] = None
) -> List[Dict]:
    """
    Get all available time slots for a provider on a given date.
    
    Returns: [
        {"time": "09:00", "available": True},
        {"time": "09:30", "available": False, "reason": "Booked"},
        ...
    ]
    """
    # Get provider details
    provider = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    if not provider:
        return []
    
    # Get working hours for the day
    day_name = get_day_name(datetime.fromisoformat(date))
    working_hours = provider.get('working_hours', {})
    day_schedule = working_hours.get(day_name, [])
    
    if not day_schedule:
        return []
    
    # Generate time slots (30-minute intervals)
    available_slots = []
    
    for block in day_schedule:
        start_time = block.get('start', '09:00')
        end_time = block.get('end', '17:00')
        
        start_minutes = time_to_minutes(start_time)
        end_minutes = time_to_minutes(end_time)
        
        # Generate slots every 30 minutes
        current = start_minutes
        while current + 30 <= end_minutes:
            time_str = minutes_to_time(current)
            
            # Check basic validation
            validation = validate_provider_availability(
                provider, date, time_str, location_id, appointment_type
            )
            
            # Check for conflicts
            has_conflict = await check_provider_conflicts(db, provider_id, date, time_str)
            
            slot = {
                "time": time_str,
                "available": validation["available"] and not has_conflict,
                "reason": validation.get("reason") or ("Booked" if has_conflict else None)
            }
            
            available_slots.append(slot)
            current += 30
    
    return available_slots


async def route_appointment(
    db,
    appointment_type: str,
    location_id: str,
    date: str,
    preferred_provider_id: Optional[str] = None,
    is_emergency: bool = False
) -> Dict:
    """
    Smart routing algorithm to find best available provider.
    
    Returns: {
        "providers": [
            {
                "provider_id": str,
                "provider_name": str,
                "available_times": [str],
                "is_on_call": bool
            }
        ],
        "recommended_provider_id": str
    }
    """
    query = {"is_active": True}
    
    # For emergencies, prioritize on-call providers
    if is_emergency:
        on_call_providers = await db.providers.find({
            **query,
            "on_call": True,
            "location_ids": location_id
        }, {"_id": 0}).to_list(100)
        
        if on_call_providers:
            result_providers = []
            for provider in on_call_providers:
                slots = await get_provider_availability_slots(
                    db, provider['id'], date, location_id, appointment_type
                )
                available_times = [s['time'] for s in slots if s['available']]
                
                if available_times:
                    result_providers.append({
                        "provider_id": provider['id'],
                        "provider_name": f"{provider.get('title', 'Dr.')} {provider['name']}",
                        "available_times": available_times,
                        "is_on_call": True,
                        "role": provider.get('role', 'dentist')
                    })
            
            if result_providers:
                return {
                    "providers": result_providers,
                    "recommended_provider_id": result_providers[0]['provider_id']
                }
    
    # If preferred provider is specified, check them first
    if preferred_provider_id:
        provider = await db.providers.find_one({"id": preferred_provider_id}, {"_id": 0})
        if provider:
            slots = await get_provider_availability_slots(
                db, provider['id'], date, location_id, appointment_type
            )
            available_times = [s['time'] for s in slots if s['available']]
            
            if available_times:
                return {
                    "providers": [{
                        "provider_id": provider['id'],
                        "provider_name": f"{provider.get('title', 'Dr.')} {provider['name']}",
                        "available_times": available_times,
                        "is_on_call": provider.get('on_call', False),
                        "role": provider.get('role', 'dentist')
                    }],
                    "recommended_provider_id": provider['id']
                }
    
    # Find all providers who can handle this appointment
    all_providers = await db.providers.find(query, {"_id": 0}).to_list(100)
    
    result_providers = []
    for provider in all_providers:
        # Check if provider works at this location
        location_ids = provider.get('location_ids', [])
        if provider.get('location_id') and not location_ids:
            location_ids = [provider['location_id']]
        
        if location_id not in location_ids:
            continue
        
        # Check if provider handles this appointment type
        appointment_types = provider.get('appointment_types', [])
        if appointment_type not in appointment_types:
            continue
        
        # Get available slots
        slots = await get_provider_availability_slots(
            db, provider['id'], date, location_id, appointment_type
        )
        available_times = [s['time'] for s in slots if s['available']]
        
        if available_times:
            result_providers.append({
                "provider_id": provider['id'],
                "provider_name": f"{provider.get('title', 'Dr.')} {provider['name']}",
                "available_times": available_times,
                "is_on_call": provider.get('on_call', False),
                "role": provider.get('role', 'dentist')
            })
    
    # Sort: on-call first, then by most available slots
    result_providers.sort(
        key=lambda p: (-int(p['is_on_call']), -len(p['available_times']))
    )
    
    return {
        "providers": result_providers,
        "recommended_provider_id": result_providers[0]['provider_id'] if result_providers else None
    }
