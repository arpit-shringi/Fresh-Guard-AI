import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Fresh-Guard AI Backend")

# Allow your React/Next.js frontend to talk to this backend without CORS errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = Path("seed_inventory.json")

# --- Helper Functions to Read & Save JSON Database ---
def load_db():
    if not DB_FILE.exists():
        raise HTTPException(status_code=500, detail="seed_inventory.json not found!")
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- Request Model for Manager Approval ---
class ApprovalRequest(BaseModel):
    item_id: str
    approval_status: str  # "APPROVED" or "REJECTED"
    custom_price: Optional[float] = None


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
            # Safety Guardrail: Never allow marketing spoiled food
            if item["freshness_status"] == "Spoiled" and req.approval_status == "APPROVED":
                item["recommended_action"] = "REMOVE_FROM_SHELF"
                item["approval_status"] = "APPROVED"
                save_db(db)
                return {"message": f"Safety alert confirmed: {item['name']} marked for removal.", "item": item}

            # Margin Floor Guardrail: Never allow price below min_allowed_price (Cost + 5%)
            if req.custom_price is not None:
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


# 4. UPLOAD SHELF IMAGE (Hook for Rishabh's Vision Engine & Arpit Sonar's SLM Engine)
@app.post("/upload-shelf")
async def upload_shelf(file: UploadFile = File(...)):
    db = load_db()
    # TODO: When Rishabh & Arpit Sonar finish their files, import and call:
    # vision_results = analyze_shelf_image(file)
    # pricing_results = calculate_pricing(vision_results)
    # slm_results = generate_marketing_copy(pricing_results)
    return {
        "filename": file.filename,
        "status": "Image processed successfully",
        "detected_items": len(db.get("inventory", [])),
        "inventory": db.get("inventory", [])
    }