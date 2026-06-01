from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import Optional, List
import uuid
from datetime import datetime, timezone

# ==== PRACTICE & ORG ====

class Practice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str = "active"  # active, suspended, cancelled
    billing_status: str = "active"  # active, past_due, cancelled
    stripe_customer_id: Optional[str] = None
    subscription_plan: str = "starter"  # starter, growth, enterprise
    default_timezone: str = "America/Toronto"
    default_retention_years: int = 7
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Data residency fields — set at onboarding, never changed
    province: Optional[str] = None          # Two-letter province code (BC, ON, etc.)
    home_region: Optional[str] = None       # "ca-west" or "ca-east" — derived from province
    db_cluster: Optional[str] = None        # "atlas-ca-west" or "atlas-ca-east"
    compute_region: Optional[str] = None    # GCP region label for audit

class PracticeCreate(BaseModel):
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    default_timezone: str = "America/Toronto"
    province: Optional[str] = None          # Two-letter Canadian province code

class Location(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    practice_id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    timezone: str = "America/Toronto"
    hours: Optional[dict] = None  # {"mon": {"open": "08:00", "close": "18:00"}, ...}
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class LocationCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    timezone: str = "America/Toronto"
    hours: Optional[dict] = None

class Provider(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    practice_id: str
    location_id: Optional[str] = None
    user_id: Optional[str] = None  # link to users collection
    name: str
    title: str = "Dr."  # Dr., Hygienist, etc.
    specialties: List[str] = []
    license_number: Optional[str] = None
    itrans_provider_number: Optional[str] = None
    availability: Optional[dict] = None  # {"mon": [{"start": "09:00", "end": "17:00"}], ...}
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ProviderCreate(BaseModel):
    name: str
    title: str = "Dr."
    role: str = "dentist"  # dentist, hygienist, specialist
    location_ids: List[str] = []  # Array of locations where provider works
    appointment_types: List[str] = ["Cleaning", "Checkup", "Consultation"]  # Appointment types they handle
    working_hours: dict = {
        "monday": [{"start": "09:00", "end": "17:00"}],
        "tuesday": [{"start": "09:00", "end": "17:00"}],
        "wednesday": [{"start": "09:00", "end": "17:00"}],
        "thursday": [{"start": "09:00", "end": "17:00"}],
        "friday": [{"start": "09:00", "end": "17:00"}],
        "saturday": [],
        "sunday": []
    }  # Per-day schedule blocks
    on_call: bool = False  # Available for emergencies
    specialties: List[str] = []
    license_number: Optional[str] = None
    itrans_provider_number: Optional[str] = None
    # Legacy fields for backward compatibility
    location_id: Optional[str] = None
    availability: Optional[dict] = None

# ==== USER ====

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    full_name: str
    practice_id: Optional[str] = None  # null for super_admin
    practice_name: Optional[str] = None
    provider_id: Optional[str] = None  # for provider role
    role: str = "staff"  # super_admin, admin, staff, provider, auditor
    is_active: bool = True
    onboarding_completed: bool = False
    phone_number: Optional[str] = None
    retell_phone_number: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str
    practice_name: str  # creates a new practice

class UserLogin(BaseModel):
    email: str
    password: str

class UserInvite(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "staff"  # admin, staff, provider, auditor
    provider_id: Optional[str] = None

# ==== PATIENT ====

class Patient(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    practice_id: str = ""
    location_id: Optional[str] = None
    provider_id: Optional[str] = None
    file_number: str = ""
    name: str
    date_of_birth: Optional[str] = None
    phone: str
    email: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    insurance_carrier: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_group_number: Optional[str] = None
    notes: Optional[str] = None
    consent_given: bool = False
    consent_date: Optional[str] = None
    consent_method: Optional[str] = None
    preferred_contact: Optional[str] = "phone"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PatientCreate(BaseModel):
    name: str
    phone: str
    date_of_birth: Optional[str] = None
    email: Optional[str] = None
    preferred_contact: Optional[str] = "phone"
    location_id: Optional[str] = None
    provider_id: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    insurance_carrier: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_group_number: Optional[str] = None
    notes: Optional[str] = None

# ==== APPOINTMENT ====

class Appointment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    practice_id: str = ""
    location_id: Optional[str] = None
    provider_id: Optional[str] = None
    patient_id: str
    patient_name: str
    patient_phone: str
    appointment_date: str
    appointment_time: str
    service_type: str
    duration_minutes: int = 60
    status: str = "pending_verification"
    notes: Optional[str] = None
    is_emergency: bool = False
    verified_at: Optional[str] = None
    verified_by: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class AppointmentCreate(BaseModel):
    patient_id: str
    patient_name: str
    patient_phone: str
    appointment_date: str
    appointment_time: str
    service_type: str
    duration_minutes: int = 60
    location_id: Optional[str] = None
    provider_id: Optional[str] = None
    notes: Optional[str] = None

# ==== INSURANCE ====

class InsuranceClaim(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    practice_id: str
    patient_id: str
    patient_name: str
    provider_id: Optional[str] = None
    appointment_id: Optional[str] = None
    carrier: str
    policy_number: str
    group_number: Optional[str] = None
    procedures: List[dict] = []  # [{"code": "01101", "description": "...", "fee": 150.00}]
    total_amount: float = 0.0
    # Lifecycle: draft → ready_to_submit → submitted → accepted | rejected | error → paid | reversed
    status: str = "draft"
    submission_method: str = "itrans"  # itrans, cdanet, manual
    response_data: Optional[dict] = None
    submitted_at: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # ── CDAnet subscriber info ─────────────────────────────────────────────
    subscriber_last_name: Optional[str] = None
    subscriber_first_name: Optional[str] = None
    subscriber_policy_number: Optional[str] = None
    subscriber_certificate_number: Optional[str] = None
    relationship_to_subscriber: Optional[str] = None  # self, spouse, child, other

    # ── CDAnet carrier routing ─────────────────────────────────────────────
    carrier_id: Optional[str] = None           # CDAnet carrier code
    division_number: Optional[str] = None      # Optional carrier division
    practice_province: Optional[str] = None    # Required for carrier routing — varies by province

    # ── CDAnet transaction metadata ────────────────────────────────────────
    cdanet_version: Optional[str] = "4.1"
    transaction_type: Optional[str] = None     # claim, reversal, eligibility, predetermination
    claim_reference_number: Optional[str] = None   # Assigned by carrier on response
    network_reference_number: Optional[str] = None

    # ── Adjudication details (populated from carrier response) ────────────
    adjudication_code: Optional[str] = None
    explanation_codes: List[str] = []
    amount_approved: Optional[float] = None
    amount_patient_responsibility: Optional[float] = None

    # ── Submission tracking (required for retry rules and audit) ──────────
    submission_attempts: int = 0
    last_submitted_at: Optional[str] = None
    last_error_message: Optional[str] = None  # Human-readable only — never raw CDAnet codes


class ClaimCreate(BaseModel):
    """Request body for POST /claims — creates a claim in draft state."""
    patient_id: str
    carrier: str
    policy_number: str
    group_number: Optional[str] = None
    provider_id: Optional[str] = None
    appointment_id: Optional[str] = None
    procedures: List[dict] = []
    # CDAnet fields — optional at creation, required before submission
    carrier_id: Optional[str] = None
    division_number: Optional[str] = None
    practice_province: Optional[str] = None
    subscriber_last_name: Optional[str] = None
    subscriber_first_name: Optional[str] = None
    subscriber_policy_number: Optional[str] = None
    subscriber_certificate_number: Optional[str] = None
    relationship_to_subscriber: Optional[str] = None
    transaction_type: Optional[str] = "claim"


class ClaimUpdate(BaseModel):
    """Request body for PUT /claims/:id — updates mutable fields."""
    status: Optional[str] = None
    procedures: Optional[List[dict]] = None
    total_amount: Optional[float] = None
    carrier_id: Optional[str] = None
    division_number: Optional[str] = None
    practice_province: Optional[str] = None
    subscriber_last_name: Optional[str] = None
    subscriber_first_name: Optional[str] = None
    subscriber_policy_number: Optional[str] = None
    subscriber_certificate_number: Optional[str] = None
    relationship_to_subscriber: Optional[str] = None
    transaction_type: Optional[str] = None


class EligibilityCheck(BaseModel):
    carrier: str
    policy_number: str
    patient_name: str
    date_of_birth: Optional[str] = None
    group_number: Optional[str] = None

class ClaimSubmit(BaseModel):
    patient_id: str
    carrier: str
    policy_number: str
    group_number: Optional[str] = None
    provider_id: Optional[str] = None
    appointment_id: Optional[str] = None
    procedures: List[dict] = []

# ==== BILLING ====

class BillingCustomer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    practice_id: str
    stripe_customer_id: str = ""
    plan: str = "starter"
    status: str = "active"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ==== CALL LOG ====

class CallLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    practice_id: str = ""
    call_id: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_phone: str
    transcript: str
    duration: float
    status: str
    call_summary: Optional[dict] = None
    action_taken: Optional[str] = None
    handled_by: str = "ai"
    call_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ==== NOTIFICATION ====

class Notification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    practice_id: str = ""
    type: str
    title: str
    message: str
    appointment_id: Optional[str] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    status: str = "unread"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Optional[dict] = None


# ==== MULTI-TENANT CONFIG (Phase 1) ====

class DayHours(BaseModel):
    """A single day's opening hours. null in the weekly map = closed."""
    open: str   # "08:00"
    close: str  # "17:00"

class PracticeHours(BaseModel):
    model_config = ConfigDict(extra="ignore")
    timezone: str = "America/Toronto"
    weekly: dict = Field(default_factory=lambda: {
        "mon": {"open": "08:00", "close": "17:00"},
        "tue": {"open": "08:00", "close": "17:00"},
        "wed": {"open": "08:00", "close": "17:00"},
        "thu": {"open": "08:00", "close": "17:00"},
        "fri": {"open": "08:00", "close": "15:00"},
        "sat": None,
        "sun": None,
    })
    closed_dates: List[str] = Field(default_factory=list)  # YYYY-MM-DD

class PracticeBranding(BaseModel):
    model_config = ConfigDict(extra="ignore")
    agent_name: str = "Amanda"
    greeting: str = "Thank you for calling. This is Amanda. How can I help today?"
    closing: str = "Thank you for calling. Have a great day!"
    voice_tone: str = "warm_professional"  # warm_professional | casual | formal

class EmergencyRules(BaseModel):
    model_config = ConfigDict(extra="ignore")
    triggers: List[str] = Field(default_factory=lambda: [
        "severe pain", "swelling", "bleeding", "trauma", "knocked out",
        "excruciating", "abscess", "fever"
    ])
    response_policy: str = "earliest_available"  # earliest_available | transfer | both
    after_hours_handoff_phone: Optional[str] = None

class AppointmentType(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    duration_min: int = 30

class PracticeRetellConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    agent_id: Optional[str] = None
    phone_number: Optional[str] = None
    provisioned_at: Optional[str] = None

class PracticeInsuranceConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    accepted_carriers: List[str] = Field(default_factory=list)
    itrans_enabled: bool = False
    cdanet_enabled: bool = False


DEFAULT_APPOINTMENT_TYPES: List[dict] = [
    {"id": "cleaning",  "name": "Cleaning",  "duration_min": 60},
    {"id": "checkup",   "name": "Checkup",   "duration_min": 30},
    {"id": "emergency", "name": "Emergency", "duration_min": 45},
]


def default_practice_settings() -> dict:
    """Return a complete default settings subdoc for a new practice."""
    return {
        "branding":  PracticeBranding().model_dump(),
        "hours":     PracticeHours().model_dump(),
        "emergency": EmergencyRules().model_dump(),
        "appointment_types": DEFAULT_APPOINTMENT_TYPES,
        "insurance": PracticeInsuranceConfig().model_dump(),
        "retell":    PracticeRetellConfig().model_dump(),
    }


# ==== ONBOARDING ====

class OnboardingRequest(BaseModel):
    practice_name: str
    province: str                           # Required — two-letter Canadian province code (BC, ON, etc.)
    timezone: str = "America/Toronto"
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    admin_email: EmailStr
    admin_password: str
    admin_full_name: str
    # Legal acceptance — required at registration, immutable after creation
    accepted_terms_version: str = Field(..., description="Version of T&C accepted")
    accepted_privacy_version: str = Field(..., description="Version of Privacy Policy accepted")
    accepted_at: datetime = Field(..., description="Timestamp of acceptance (ISO 8601)")
