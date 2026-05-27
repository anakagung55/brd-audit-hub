from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from auditor import run_single_audit
from dotenv import load_dotenv

load_dotenv() 

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY")

app = FastAPI(title="BlueRock Audit Engine API")

# Izinkan Frontend (Next.js) untuk ngobrol sama Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Buka akses folder outputs agar file PDF/Excel bisa di-download via URL
app.mount("/outputs", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "data", "outputs")), name="outputs")

class AuditRequest(BaseModel):
    url: str
    company_name: str

@app.post("/api/generate")
def generate_report(req: AuditRequest):
    try:
        results = run_single_audit(req.url, req.company_name)
        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])
        return {"status": "success", "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))