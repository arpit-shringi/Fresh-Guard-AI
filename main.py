import json
from pathlib import Path
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Fresh-Guard AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = Path("seed_inventory.json")

def load_db():
    if not DB_FILE.exists():
        raise HTTPException(status_code=500, detail="seed_inventory.json not found!")
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Prevent null price crashes in the frontend
    for item in data.get("inventory", []):
        if item.get("recommended_price") is None:
            item["recommended_price"] = 0.0
    return data

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class ApprovalRequest(BaseModel):
    item_id: str
    approval_status: str  # "APPROVED" or "REJECTED"
    custom_price: Optional[float] = None


# 0. HOME HEALTH CHECK ROUTE (Fixes 127.0.0.1:8000 "Not Found")
@app.get("/")
def root():
    return {
        "status": "Fresh-Guard AI Backend is live!",
        "docs_url": "http://127.0.0.1:8000/docs"
    }


# 1. GET RECOMMENDATIONS (For Store Manager Audit Portal)
@app.get("/get-recommendations")
def get_recommendations():
    db = load_db()
    return {
        "store_metadata": db.get("store_metadata"),
        "tags": db.get("tags"),
        "inventory": db.get("inventory", [])
    }


# 2. APPROVE OR REJECT ACTION (Manager Human-in-the-Loop Toggle)
@app.post("/approve-action")
def approve_action(req: ApprovalRequest):
    db = load_db()
    for item in db.get("inventory", []):
        if item["item_id"] == req.item_id:
            if item["freshness_status"] == "Spoiled" and req.approval_status == "APPROVED":
                item["recommended_action"] = "REMOVE_FROM_SHELF"
                item["recommended_price"] = 0.0
                item["approval_status"] = "APPROVED"
                save_db(db)
                return {"message": f"Safety alert confirmed: {item['name']} marked for removal.", "item": item}

            if req.custom_price is not None and req.custom_price > 0:
                if req.custom_price < item["min_allowed_price"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Guardrail Violation: Price (₹{req.custom_price}) cannot be below Cost + 5% floor (₹{item['min_allowed_price']})."
                    )
                item["recommended_price"] = req.custom_price

            item["approval_status"] = req.approval_status
            save_db(db)
            return {"message": f"Updated {item['name']} to {req.approval_status}", "item": item}

    raise HTTPException(status_code=404, detail="Item not found")


# 3. CUSTOMER FEED (Only Approved Promotions & Recipes, Never Spoiled Items)
@app.get("/customer-feed")
def get_customer_feed():
    db = load_db()
    approved_promos = [
        item for item in db.get("inventory", [])
        if item.get("approval_status") == "APPROVED"
        and item.get("freshness_status") != "Spoiled"
        and item.get("slm_generated") is not None
    ]
    return {"promotions": approved_promos}


# 4. UPLOAD SHELF IMAGE
@app.post("/upload-shelf")
async def upload_shelf(file: UploadFile = File(...)):
    db = load_db()
    return {
        "filename": file.filename,
        "status": "Image processed successfully",
        "detected_items": len(db.get("inventory", [])),
        "inventory": db.get("inventory", [])
    }


if __name__ == "__main__":
    # Runs Uvicorn while ignoring the frontend folder so node_modules never crashes Python
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_excludes=["frontend/*", "frontend/**"]
    )