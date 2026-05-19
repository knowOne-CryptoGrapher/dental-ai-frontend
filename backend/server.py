from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import json

# -------------------------------------------------------------------
# Load Environment Variables
# -------------------------------------------------------------------

load_dotenv("backend/.env", override=True)

# -------------------------------------------------------------------
# Router Imports
# -------------------------------------------------------------------

from routers.auth_router import router as auth_router
from routers.billing_router import router as billing_router
from routers.stripe_webhook_router import router as stripe_webhook_router
from routers.onboarding_router import router as onboarding_router
from routers.retell_router import router as retell_router
from routers.llm_router import router as llm_router

# Additional routers based on your backend structure
from routers.analytics_router import router as analytics_router
from routers.appointment_router import router as appointment_router
from routers.calllog_router import router as calllog_router
from routers.insurance_router import router as insurance_router
from routers.patient_router import router as patient_router
from routers.practice_router import router as practice_router
from routers.practice_config_router import router as practice_config_router
from routers.superadmin_router import router as superadmin_router
from routers.retell_api_router import router as retell_api_router
from routers.retell_webhook_router import router as retell_webhook_router

# -------------------------------------------------------------------
# LLM Manager Initialization
# -------------------------------------------------------------------

from services.llm_manager import LLMManager

def load_json_file(path: str):
    if not path or not os.path.exists(path):
        print(f"[WARN] JSON file not found: {path}")
        return {}
    with open(path, "r") as f:
        return json.load(f)

LLM_RULES = load_json_file(os.getenv("LLM_RULES_PATH"))
LLM_PRICING = load_json_file(os.getenv("LLM_PRICING_PATH"))

llm_manager = LLMManager(
    default_provider=os.getenv("LLM_DEFAULT_PROVIDER"),
    default_model=os.getenv("LLM_DEFAULT_MODEL"),
    escalation_provider=os.getenv("LLM_ESCALATION_PROVIDER"),
    escalation_model=os.getenv("LLM_ESCALATION_MODEL"),
    rules=LLM_RULES,
    pricing=LLM_PRICING
)

# -------------------------------------------------------------------
# App Initialization
# -------------------------------------------------------------------

app = FastAPI(
    title="Dental AI Backend",
    version="2.0.0",
    description="Backend API for FrontDesk Dental AI"
)

# -------------------------------------------------------------------
# CORS Configuration
# -------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Startup / Shutdown Events
# -------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    print("🚀 Server starting...")
    print("🔧 Initializing LLM router...")
    llm_manager.initialize()
    print("✅ LLM router ready")

@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 Server shutting down...")

# -------------------------------------------------------------------
# Health Check
# -------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"status": "ok", "llm_router": llm_manager.status()}

# -------------------------------------------------------------------
# Include Routers
# -------------------------------------------------------------------

# Core
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(stripe_webhook_router)
app.include_router(onboarding_router)
app.include_router(retell_router)
app.include_router(llm_router)

# Additional routers
app.include_router(analytics_router)
app.include_router(appointment_router)
app.include_router(calllog_router)
app.include_router(insurance_router)
app.include_router(patient_router)
app.include_router(practice_router)
app.include_router(practice_config_router)
app.include_router(superadmin_router)
app.include_router(retell_api_router)
app.include_router(retell_webhook_router)

# -------------------------------------------------------------------
# Global Error Handler
# -------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"[ERROR] {exc}")
    return {"error": "Internal server error", "details": str(exc)}

#force new commit
