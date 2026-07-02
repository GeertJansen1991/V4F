from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from weasyprint import HTML
from jinja2 import Template
import base64
import json
import os

app = FastAPI()

# Configure CORS cross-origin allowances for front-end integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_v4f_cpt_database() -> dict:
    """
    Loads our externalized database containing the structured CPT arrays.
    """
    json_path = "v4f_tables.json"
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def match_cpt_interval(rows: list, numeric_value: float, range_key: str) -> float:
    """
    Dynamically maps a raw number to its true conditional BBN probability weight 
    by checking bounding interval rows from the generated JSON file.
    """
    for row in rows:
        range_str = str(row.get(range_key, "")).replace(" ", "")
        bbn_val = row.get("BBN value") or row.get("BBN Value")
        if bbn_val is None:
            continue
            
        try:
            if "<=" in range_str:
                if numeric_value <= float(range_str.replace("<=", "")): return float(bbn_val)
            elif "<" in range_str:
                if numeric_value < float(range_str.replace("<", "")): return float(bbn_val)
            elif ">" in range_str:
                if numeric_value > float(range_str.replace(">", "")): return float(bbn_val)
            elif "-" in range_str:
                low, high = range_str.split("-")
                if float(low) <= numeric_value <= float(high): return float(bbn_val)
        except ValueError:
            continue
    return 0.5  # Neutral default value if no criteria match

@app.post("/generate-report")
async def generate_report(data: dict):
    # ==========================================
    # 1. INITIALIZE DATA & LOAD CPTs
    # ==========================================
    db = load_v4f_cpt_database()
    
    location = data.get("location", "Netherlands")
    agri = data.get("agrivoltaics", {})
    land_space = float(agri.get("landSpace") or 0)
    
    # ==========================================
    # 2. EVALUATE GOVERNANCE PARENT NODE
    # ==========================================
    country_rows = db.get("APV_Main", [])
    # Find the specific row dictionary for the user's selected country
    country_data = next((row for row in country_rows if row.get("Country") == location), {})
    
    # Standard probability state mappings derived from CPT documentation
    state_weights = {"Positive": 0.9, "Neutral": 0.5, "Negative": 0.1}
    
    prob_pol = state_weights.get(country_data.get("APV_Pol"), 0.5)
    prob_rev = state_weights.get(country_data.get("APV_Rev"), 0.5)
    prob_per = state_weights.get(country_data.get("APV_Per"), 0.5)
    prob_sub = state_weights.get(country_data.get("APV_Sub"), 0.5)
    
    # Aggregate parent policy vector
    score_governance = (prob_pol + prob_rev + prob_per + prob_sub) / 4

    # ==========================================
    # 3. EVALUATE ENERGY POTENTIAL PARENT NODE
    # ==========================================
    cf_percentage = float(country_data.get("APV_Cap_Fac") or 12.0)
    
    # Engineering Math: P = Area (m2) * (Power Density / 1000) * Coverage Factor
    area_m2 = land_space * 10000 
    installed_capacity_kwp = area_m2 * (220 / 1000) * 0.60
    energy_potential_kwh_kwp = 8760 * (cf_percentage / 100)
    
    # Find true conditional probability from CPT sheet based on numerical boundaries
    score_energy_potential = match_cpt_interval(db.get("APV_Ene_Pot", []), energy_potential_kwh_kwp, "kWh/kWp")

    # ==========================================
    # 4. COMPUTE TECHNICAL FEASIBILITY CHILD NODE
    # ==========================================
    # Blending performance (60%) and baseline structural administration framework (40%)
    final_technical_weight = (score_energy_potential * 0.6) + (score_governance * 0.4)
    technical_feasibility_score = int(final_technical_weight * 100)

    # ==========================================
    # 5. ASSEMBLE SUMMARY PACKETS & SCORE MAPS
    # ==========================================
    feasibility_scores = {
        "socio_economic": 75,
        "agronomic": 70,
        "environmental": 85,
        "technical": max(15, min(100, technical_feasibility_score))
    }
    feasibility_scores["overall"] = int(sum(feasibility_scores.values()) / 4)

    return {
        "scores": feasibility_scores,
        "swot": {
            "strengths": [
                f"Dynamic BBN Match: Mapped regional capacity factor of {cf_percentage}% for {location}.",
                f"High-Density Production: System sizing generates an estimated {round(energy_potential_kwh_kwp, 1)} kWh/kWp."
            ],
            "weaknesses": [], "opportunities": [], "threats": []
        },
        "recommendations": [f"Target installation blueprint optimized for a peak threshold of {round(installed_capacity_kwp, 1)} kWp."],
        "pdf": ""
    }
