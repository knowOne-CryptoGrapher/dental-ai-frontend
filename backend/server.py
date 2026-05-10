from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Routers
from routers.retell_router import router as retell_router

# Create FastAPI app
app = FastAPI()

# CORS (optional but recommended)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(retell_router)

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}
