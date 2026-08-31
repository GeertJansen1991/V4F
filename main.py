from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination
from weasyprint import HTML
from jinja2 import Template
import pandas as pd
import numpy as np
import base64
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SOLAR_EXCEL_PATH = "APV_DST (Clean).xlsx"
BIOGAS_EXCEL_PATH = "CH4_DST (Clean).xlsx"

# Global placeholders for cached lookup matrices
df_apv_main, df_apv_cro_yld, df_apv_wat_dem = None, None, None
df_ch4_main, df_ch4_the_pot, df_ch4_pro_pot, df_ch4_har_cha = None, None, None, None

# Independent BBN Model Graph Engines
bbn_apv_model = None
bbn_ch4_model = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML_PATH = os.path.join(BASE_DIR, "index.html")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serves the index.html user interface directly at the root domain URL."""
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(
        content="<h3>Error: index.html not found in project root directory.</h3>",
        status_code=404
    )

@app.on_event("startup")
def initialize_system():
    """Loads spreadsheets and initializes Bayesian Belief Networks on startup."""
    global df_apv_main, df_apv_cro_yld, df_apv_wat_dem
    global df_ch4_main, df_ch4_the_pot, df_ch4_pro_pot, df_ch4_har_cha
    global bbn_apv_model, bbn_ch4_model
    
    if not os.path.exists(SOLAR_EXCEL_PATH) or not os.path.exists(BIOGAS_EXCEL_PATH):
        raise FileNotFoundError("Missing database spreadsheet dependencies in root directory.")
        
    # 1. Caches for APV (Solar)
    df_apv_main = pd.read_excel(SOLAR_EXCEL_PATH, sheet_name='APV_Main')
    df_apv_cro_yld = pd.read_excel(SOLAR_EXCEL_PATH, sheet_name='APV_Cro_Yld')
    df_apv_wat_dem = pd.read_excel(SOLAR_EXCEL_PATH, sheet_name='APV_Wat_Dem')
    
    # 2. Caches for CH4 (Biogas)
    df_ch4_main = pd.read_excel(BIOGAS_EXCEL_PATH, sheet_name='CH4_main')
    df_ch4_the_pot = pd.read_excel(BIOGAS_EXCEL_PATH, sheet_name='CH4_The_Pot')
    df_ch4_pro_pot = pd.read_excel(BIOGAS_EXCEL_PATH, sheet_name='CH4_Pro_Pot')
    df_ch4_har_cha = pd.read_excel(BIOGAS_EXCEL_PATH, sheet_name='CH4_Har_Cha')
    
    # ====================================================
    # 1: AGRIVOLTAICS GRAPH MODEL
    # ====================================================
    model_apv = DiscreteBayesianNetwork([
        ('APV_Pol', 'Governance'), ('APV_Per', 'Governance'), ('APV_Sub', 'Governance'), ('APV_Rev', 'Governance'),
        ('Governance', 'Technical_Feasibility'), ('Energy_Potential', 'Technical_Feasibility'),
        ('Economic_Potential', 'Economic_Feasibility'), ('APV_Rev', 'Economic_Feasibility'),
        ('Visual_Impact', 'Social_Feasibility'),
        ('Crop_Yield_Impact', 'Agronomic_Feasibility'), ('Water_Demand_Impact', 'Agronomic_Feasibility'), ('Machinery_Compatibility', 'Agronomic_Feasibility'),
        ('Environmental_Potential', 'Environmental_Feasibility'),
        
        ('Technical_Feasibility', 'Overall_Feasibility'),
        ('Economic_Feasibility', 'Overall_Feasibility'),
        ('Social_Feasibility', 'Overall_Feasibility'),
        ('Agronomic_Feasibility', 'Overall_Feasibility'),
        ('Environmental_Feasibility', 'Overall_Feasibility'),
        ('Land_Ownership', 'Overall_Feasibility'),
        ('Successor_Planning', 'Overall_Feasibility')
    ])

    cpd_pol = TabularCPD('APV_Pol', 3, [[0.33], [0.34], [0.33]])
    cpd_per = TabularCPD('APV_Per', 3, [[0.33], [0.34], [0.33]])
    cpd_sub = TabularCPD('APV_Sub', 3, [[0.33], [0.34], [0.33]])
    cpd_rev = TabularCPD('APV_Rev', 3, [[0.33], [0.34], [0.33]])
    cpd_ene = TabularCPD('Energy_Potential', 3, [[0.33], [0.34], [0.33]])
    cpd_eco = TabularCPD('Economic_Potential', 3, [[0.33], [0.34], [0.33]])
    cpd_vis = TabularCPD('Visual_Impact', 5, [[0.2], [0.2], [0.2], [0.2], [0.2]])
    cpd_cyi = TabularCPD('Crop_Yield_Impact', 3, [[0.33], [0.34], [0.33]])
    cpd_wdi = TabularCPD('Water_Demand_Impact', 3, [[0.33], [0.34], [0.33]])
    cpd_mac = TabularCPD('Machinery_Compatibility', 3, [[0.33], [0.34], [0.33]])
    cpd_env = TabularCPD('Environmental_Potential', 3, [[0.33], [0.34], [0.33]])
    cpd_own = TabularCPD('Land_Ownership', 3, [[0.33], [0.34], [0.33]])
    cpd_suc = TabularCPD('Successor_Planning', 3, [[0.33], [0.34], [0.33]])

    gov_matrix = []
    for p in [0,1,2]:
        for pe in [0,1,2]:
            for s in [0,1,2]:
                for r in [0,1,2]:
                    avg = (p+pe+s+r)/8.0
                    gov_matrix.append([1.0-avg, avg*0.5, avg*0.5])
    cpd_gov = TabularCPD('Governance', 3, np.array(gov_matrix).T.tolist(), evidence=['APV_Pol', 'APV_Per', 'APV_Sub', 'APV_Rev'], evidence_card=[3,3,3,3])

    tech_matrix = []
    for g in [0,1,2]:
        for e in [0,1,2]:
            combined = (g+e)/4.0
            tech_matrix.append([1.0-combined, combined*0.5, combined*0.5])
    cpd_tech = TabularCPD('Technical_Feasibility', 3, np.array(tech_matrix).T.tolist(), evidence=['Governance', 'Energy_Potential'], evidence_card=[3,3])

    eco_matrix = []
    for econ in [0,1,2]: 
        for rev in [0,1,2]:  
            combined = (econ+rev)/4.0
            eco_matrix.append([1.0-combined, combined*0.5, combined*0.5])
    cpd_eco_feas = TabularCPD('Economic_Feasibility', 3, np.array(eco_matrix).T.tolist(), evidence=['Economic_Potential', 'APV_Rev'], evidence_card=[3,3])

    soc_matrix = []
    for vis in [0,1,2,3,4]: 
        social_score = 1.0 - (vis/4.0) 
        soc_matrix.append([1.0-social_score, social_score*0.5, social_score*0.5])
    cpd_soc_feas = TabularCPD('Social_Feasibility', 3, np.array(soc_matrix).T.tolist(), evidence=['Visual_Impact'], evidence_card=[5])

    agro_matrix = []
    for yld in [0,1,2]:     
        for wat in [0,1,2]:  
            for mac in [0,1,2]: 
                combined = (yld+wat+mac)/6.0
                agro_matrix.append([1.0-combined, combined*0.5, combined*0.5])
    cpd_agro_feas = TabularCPD('Agronomic_Feasibility', 3, np.array(agro_matrix).T.tolist(), evidence=['Crop_Yield_Impact', 'Water_Demand_Impact', 'Machinery_Compatibility'], evidence_card=[3,3,3])

    env_matrix = []
    for env_pot in [0,1,2]:
        combined = env_pot/2.0
        env_matrix.append([1.0-combined, combined*0.5, combined*0.5])
    cpd_env_feas = TabularCPD('Environmental_Feasibility', 3, np.array(env_matrix).T.tolist(), evidence=['Environmental_Potential'], evidence_card=[3])

    overall_matrix = []
    for t in [0,1,2]:      
        for ec in [0,1,2]: 
            for s in [0,1,2]:  
                for a in [0,1,2]:  
                    for en in [0,1,2]: 
                        for o in [0,1,2]:  
                            for su in [0,1,2]: 
                                score = (t*1 + ec*1 + s*1 + a*1 + en*1 + o*1 + su*1) / 14.0
                                overall_matrix.append([1.0 - score, score * 0.5, score * 0.5])
                                
    cpd_overall = TabularCPD('Overall_Feasibility', 3, np.array(overall_matrix).T.tolist(),
                             evidence=['Technical_Feasibility', 'Economic_Feasibility', 'Social_Feasibility', 
                                       'Agronomic_Feasibility', 'Environmental_Feasibility', 'Land_Ownership', 'Successor_Planning'],
                             evidence_card=[3, 3, 3, 3, 3, 3, 3])

    model_apv.add_cpds(cpd_pol, cpd_per, cpd_sub, cpd_rev, cpd_ene, cpd_eco, cpd_vis, cpd_cyi, cpd_wdi, cpd_mac, cpd_env, cpd_own, cpd_suc,
                       cpd_gov, cpd_tech, cpd_eco_feas, cpd_soc_feas, cpd_agro_feas, cpd_env_feas, cpd_overall)
    model_apv.check_model()
    bbn_apv_model = model_apv

    # ====================================================
    # 2: BIOGAS GRAPH MODEL (CH4)
    # ====================================================
    model_ch4 = DiscreteBayesianNetwork([
        ('CH4_Pol', 'CH4_Governance'), ('CH4_Per', 'CH4_Governance'), ('CH4_Sub', 'CH4_Governance'), ('CH4_Rev', 'CH4_Governance'),
        ('CH4_Governance', 'Technical_Feasibility'), ('Feedstock_Potential', 'Technical_Feasibility'),
        ('Economic_Potential', 'Economic_Feasibility'), ('CH4_Rev', 'Economic_Feasibility'),
        ('CH4_Odor_Impact', 'Social_Feasibility'),
        ('Environmental_Potential', 'Environmental_Feasibility'),
        ('Main_Crop_Potential', 'Agronomic_Feasibility'), ('Rotation_Crops_Potential', 'Agronomic_Feasibility'),
        
        ('Technical_Feasibility', 'Overall_Feasibility'),
        ('Economic_Feasibility', 'Overall_Feasibility'),
        ('Social_Feasibility', 'Overall_Feasibility'),
        ('Agronomic_Feasibility', 'Overall_Feasibility'),
        ('Environmental_Feasibility', 'Overall_Feasibility'),
        ('CH4_Land_Ownership', 'Overall_Feasibility'),
        ('CH4_Successor_Planning', 'Overall_Feasibility')
    ])

    cpd_ch4_pol = TabularCPD('CH4_Pol', 3, [[0.33], [0.34], [0.33]])
    cpd_ch4_per = TabularCPD('CH4_Per', 3, [[0.33], [0.34], [0.33]])
    cpd_ch4_sub = TabularCPD('CH4_Sub', 3, [[0.33], [0.34], [0.33]])
    cpd_ch4_rev = TabularCPD('CH4_Rev', 3, [[0.33], [0.34], [0.33]])
    cpd_ch4_fee = TabularCPD('Feedstock_Potential', 3, [[0.33], [0.34], [0.33]])
    cpd_ch4_eco_pot = TabularCPD('Economic_Potential', 3, [[0.33], [0.34], [0.33]])
    cpd_ch4_env_pot = TabularCPD('Environmental_Potential', 3, [[0.33], [0.34], [0.33]])
    cpd_ch4_main_crop = TabularCPD('Main_Crop_Potential', 3, [[0.33], [0.34], [0.33]])
    cpd_ch4_rot_crop = TabularCPD('Rotation_Crops_Potential', 3, [[0.33], [0.34], [0.33]])
    cpd_ch4_odor = TabularCPD('CH4_Odor_Impact', 5, [[0.2], [0.2], [0.2], [0.2], [0.2]])
    cpd_ch4_own = TabularCPD('CH4_Land_Ownership', 3, [[0.33], [0.34], [0.33]])
    cpd_ch4_suc = TabularCPD('CH4_Successor_Planning', 3, [[0.33], [0.34], [0.33]])

    ch4_gov_matrix = []
    for p in [0,1,2]:
        for pe in [0,1,2]:
            for s in [0,1,2]:
                for r in [0,1,2]:
                    avg = (p+pe+s+r)/8.0
                    ch4_gov_matrix.append([1.0-avg, avg*0.5, avg*0.5])
    cpd_ch4_gov = TabularCPD('CH4_Governance', 3, np.array(ch4_gov_matrix).T.tolist(), 
                             evidence=['CH4_Pol', 'CH4_Per', 'CH4_Sub', 'CH4_Rev'], evidence_card=[3,3,3,3])

    ch4_tech_matrix = []
    for g in [0,1,2]:
        for f in [0,1,2]:
            combined = (g+f)/4.0
            ch4_tech_matrix.append([1.0-combined, combined*0.5, combined*0.5])
    cpd_ch4_tech = TabularCPD('Technical_Feasibility', 3, np.array(ch4_tech_matrix).T.tolist(), 
                              evidence=['CH4_Governance', 'Feedstock_Potential'], evidence_card=[3,3])

    ch4_eco_matrix = []
    for econ in [0,1,2]:
        for rev in [0,1,2]:
            combined = (econ+rev)/4.0
            ch4_eco_matrix.append([1.0-combined, combined*0.5, combined*0.5])
    cpd_ch4_eco_feas = TabularCPD('Economic_Feasibility', 3, np.array(ch4_eco_matrix).T.tolist(), 
                                  evidence=['Economic_Potential', 'CH4_Rev'], evidence_card=[3,3])

    ch4_soc_matrix = []
    for odor in [0,1,2,3,4]: 
        social_score = 1.0 - (odor/4.0) 
        ch4_soc_matrix.append([1.0-social_score, social_score*0.5, social_score*0.5])
    cpd_ch4_soc_feas = TabularCPD('Social_Feasibility', 3, np.array(ch4_soc_matrix).T.tolist(), evidence=['CH4_Odor_Impact'], evidence_card=[5])

    ch4_env_matrix = []
    for env_pot in [0,1,2]:
        combined = env_pot/2.0
        ch4_env_matrix.append([1.0-combined, combined*0.5, combined*0.5])
    cpd_ch4_env_feas = TabularCPD('Environmental_Feasibility', 3, np.array(ch4_env_matrix).T.tolist(), 
                                  evidence=['Environmental_Potential'], evidence_card=[3])

    ch4_agro_matrix = []
    for main_c in [0,1,2]:
        for rot_c in [0,1,2]:
            combined = (main_c + rot_c)/4.0
            ch4_agro_matrix.append([1.0-combined, combined*0.5, combined*0.5])
    cpd_ch4_agro_feas = TabularCPD('Agronomic_Feasibility', 3, np.array(ch4_agro_matrix).T.tolist(),
                                   evidence=['Main_Crop_Potential', 'Rotation_Crops_Potential'], evidence_card=[3,3])

    ch4_overall_matrix = []
    for t in [0,1,2]:      
        for ec in [0,1,2]: 
            for s in [0,1,2]:  
                for a in [0,1,2]:  
                    for en in [0,1,2]: 
                        for o in [0,1,2]:  
                            for su in [0,1,2]: 
                                score = (t*1.0 + ec*1.0 + s*1.0 + a*1.0 + en*1.0 + o*1.0 + su*1.0) / 14
                                ch4_overall_matrix.append([1.0 - score, score * 0.5, score * 0.5])
                                
    cpd_ch4_overall = TabularCPD('Overall_Feasibility', 3, np.array(ch4_overall_matrix).T.tolist(),
                             evidence=['Technical_Feasibility', 'Economic_Feasibility', 'Social_Feasibility', 
                                       'Agronomic_Feasibility', 'Environmental_Feasibility', 'CH4_Land_Ownership', 'CH4_Successor_Planning'],
                             evidence_card=[3, 3, 3, 3, 3, 3, 3])

    model_ch4.add_cpds(cpd_ch4_pol, cpd_ch4_per, cpd_ch4_sub, cpd_ch4_rev, cpd_ch4_fee, cpd_ch4_eco_pot, cpd_ch4_env_pot,
                       cpd_ch4_main_crop, cpd_ch4_rot_crop, cpd_ch4_odor, cpd_ch4_own, cpd_ch4_suc,
                       cpd_ch4_gov, cpd_ch4_tech, cpd_ch4_eco_feas, cpd_ch4_soc_feas, cpd_ch4_env_feas, cpd_ch4_agro_feas, cpd_ch4_overall)
    model_ch4.check_model()
    bbn_ch4_model = model_ch4


@app.post("/generate-report")
async def generate_report(data: dict):
    focus = data.get("auditFocus", "Agrivoltaics")
    country = data.get("location", "Austria")
    ownership = data.get("ownership", "Own")
    continuity = data.get("continuity", "")
    state_map = {"Negative": 0, "Neutral": 1, "Positive": 2}
    
    scores_raw = {}
    swot_strengths = []
    swot_weaknesses = []
    swot_opportunities = []
    swot_threats = []
    
    # Common mappings
    mapped_ownership = 2 if ownership == "Own" else (1 if "Share" in ownership or "Lease" in ownership else 0)
    mapped_successor = 2 if "confirmed" in continuity.lower() or "formal" in continuity.lower() else 1

    # ====================================================
    # 1: AGRIVOLTAICS ENGINE & DYNAMIC SWOT
    # ====================================================
    if focus in ["Agrivoltaics", "Both"]:
        agri = data.get("agrivoltaics", {})
        available_ha = float(agri.get("landSpace") or 2.5)
        machinery_height = float(agri.get("maxHeight") or 2.2)
        crops_list = agri.get("currentCrops", [])
        crop_choice = crops_list[0] if crops_list else "Cereals"
        resources = data.get("resources", {})
        user_electricity_usage = float(resources.get("electricity", {}).get("value") or 50000)

        has_panels = agri.get("hasPanels", "No")
        terrain_val = agri.get("terrain", "")
        slope_dir = agri.get("slopeDirection", "")

        # 1. Ownership SWOT
        if ownership == "Own":
            swot_strengths.append("Full land ownership provides full decision-making autonomy and eliminates landlord or third-party consent requirements.")
        elif ownership:
            swot_weaknesses.append("Tenancy, share agreements, or long-term leasehold require landlord approval and introduce tenure risk over the system's 25-year lifespan.")

        # 2. Succession Plan SWOT
        if "confirmed" in continuity.lower():
            swot_strengths.append("A clear farm succession plan secures the multi-decade investment and long-term economic return for the next generation.")
        elif "not sure" in continuity.lower() or "not applicable" in continuity.lower():
            swot_weaknesses.append("Lack of long-term succession planning introduces uncertainty regarding who will manage and benefit from the multi-decade asset.")

        # 3. Terrain SWOT
        if terrain_val == "Flat":
            swot_strengths.append("Flat topography lowers structural engineering costs and offers maximum flexibility for optimal row spacing and PV orientation.")
        elif terrain_val == "Gently Sloping":
            swot_opportunities.append("Minor slope allows deployment of south-facing fixed-tilt or tracking systems with basic contour engineering.")
        elif terrain_val == "Hilly":
            swot_weaknesses.append("Steep terrain complicates structural mounting, increases balance-of-system installation costs, and restricts machinery turning paths.")

        # 4. Slope Direction SWOT
        if slope_dir == "South-facing":
            swot_strengths.append("South-facing orientation optimizes solar irradiation and peaks specific electricity yield per installed kWp.")
        elif slope_dir == "North-facing":
            swot_threats.append("North-facing incline reduces total irradiation absorption and limits PV energy generation efficiency.")
        elif slope_dir == "East-West":
            swot_opportunities.append("East-West orientation enables dual-axis tracking or vertical bifacial setups, spreading generation evenly across morning and afternoon peaks.")

        # 5. Existing PV SWOT
        if has_panels == "Yes":
            swot_weaknesses.append("Grid connection capacity and existing transformer limits must be audited to prevent curtailment when expanding PV capacity.")
        elif has_panels == "No":
            swot_strengths.append("Greenfield site provides a blank canvas to design electrical sizing and grid interconnection specifically for agrivoltaics.")

        # 6. Machinery Dimensions SWOT
        if machinery_height > 0:
            if machinery_height < 2.0:
                swot_strengths.append("Standard machinery heights allow lower overhead clearance structures, reducing structural steel requirements and CAPEX.")
            elif machinery_height > 2.0:
                swot_weaknesses.append("High-clearance tractors or wide implements require elevated mounting structures or wider inter-row spacing, increasing structural and installation costs.")

        country_row = df_apv_main[df_apv_main['Country'].str.lower() == country.lower()]
        if not country_row.empty:
            apv_evidence = {}
            
            pol_raw = country_row['APV_Pol'].values[0]
            per_raw = country_row['APV_Per'].values[0]
            sub_raw = country_row['APV_Sub'].values[0]
            rev_raw = country_row['APV_Rev'].values[0]

            apv_evidence['APV_Pol'] = state_map.get(pol_raw, 1)
            apv_evidence['APV_Per'] = state_map.get(per_raw, 1)
            apv_evidence['APV_Sub'] = state_map.get(sub_raw, 1)
            apv_evidence['APV_Rev'] = state_map.get(rev_raw, 1)

            # 7. Policy SWOT
            if pol_raw == "Positive":
                swot_opportunities.append("Favourable national/regional policies provide active support and streamlined pathways for agrivoltaics deployment.")
            elif pol_raw == "Negative":
                swot_threats.append("Unclear or restrictive agrivoltaic policy frameworks may create administrative delays or regulatory hurdles.")

            # 8. Revenue SWOT
            if rev_raw == "Positive":
                swot_opportunities.append("Grid export frameworks and dynamic power market access allow for attractive feed-in revenue.")
            elif rev_raw == "Negative":
                swot_threats.append("Exporting surplus electricity is restricted or unprofitable, capping economic return strictly to on-farm self-consumption.")

            # 9. Permitting SWOT
            if per_raw == "Positive":
                swot_opportunities.append("Well-defined permitting and zoning pathways enable rapid planning approval and project execution.")
            elif per_raw == "Negative":
                swot_threats.append("Complex spatial planning and dual-use permitting regulations may cause extended development lead times.")

            # 10. Subsidy SWOT
            if sub_raw == "Positive":
                swot_opportunities.append("Target agrivoltaic/renewable subsidies and CAP eco-scheme incentives can significantly reduce initial capital expenditure.")
            elif sub_raw == "Negative":
                swot_threats.append("Lack of dedicated agrivoltaic financial support structures requires complete private financing.")

            capacity_factor_raw = float(country_row['APV_Cap_Fac'].values[0])
            if capacity_factor_raw < 12.0: climate_column = "Climate 1 (<750 W/m²)"
            elif 12.0 <= capacity_factor_raw < 14.5: climate_column = "Climate 2 (750–1099 W/m²)"
            elif 14.5 <= capacity_factor_raw < 16.5: climate_column = "Climate 3 (1100–1749 W/m²)"
            else: climate_column = "Climate 4 (>1750 W/m²)"

            installed_capacity_kwp = (available_ha * 10000) * 0.22 * 0.6
            annual_energy_production_kwh = installed_capacity_kwp * 8760 * (capacity_factor_raw / 100.0)
            specific_yield = annual_energy_production_kwh / installed_capacity_kwp if installed_capacity_kwp > 0 else 0
            apv_evidence['Energy_Potential'] = 0 if specific_yield < 1000 else (1 if specific_yield < 1400 else 2)

            # 11. Specific Yield SWOT
            if specific_yield > 1400:
                swot_strengths.append("High solar resource availability yields substantial on-farm electricity generation and strong self-consumption savings.")
            elif 0 < specific_yield < 1000:
                swot_weaknesses.append("Lower solar irradiation lengthens payback horizons and reduces total energy offset against grid purchases.")

            lifecycle_cost = installed_capacity_kwp * 1000 * 1.125
            actual_kwh_offset = min(annual_energy_production_kwh * 0.80, user_electricity_usage)
            electricity_price_kwh = float(country_row['Ele_Cos'].values[0]) / 100
            lifecycle_savings = actual_kwh_offset * electricity_price_kwh * 25
            roi = ((lifecycle_savings - lifecycle_cost) / lifecycle_cost) * 100 if lifecycle_cost > 0 else 0
            apv_evidence['Economic_Potential'] = 0 if roi < -25 else (1 if roi < 50 else 2)

            # 12. ROI SWOT
            if roi > 50:
                swot_strengths.append("Strong financial viability driven by high self-consumption, favorable avoided retail tariffs, and rapid capital amortisation.")
            elif roi < 0:
                swot_weaknesses.append("Limited on-site electricity demand or low retail power prices extend payback times beyond standard commercial financing windows.")

            if available_ha <= 0 or installed_capacity_kwp <= 0:
                apv_evidence['Energy_Potential'] = 0
                apv_evidence['Economic_Potential'] = 0
                apv_evidence['Environmental_Potential'] = 0
                apv_evidence['Crop_Yield_Impact'] = 0
                apv_evidence['Water_Demand_Impact'] = 0
                apv_evidence['Machinery_Compatibility'] = 0
            
            apv_evidence['Visual_Impact'] = min(4, int(available_ha // 2))

            crop_clean = crop_choice.strip().lower()
            crop_match = df_apv_cro_yld[df_apv_cro_yld['Crop Category'].str.lower() == crop_clean]
            if crop_match.empty:
                crop_match = df_apv_cro_yld[df_apv_cro_yld['Crop Category'].str.lower().str.contains("cereal")]
                
            if crop_match.empty:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Spreadsheet Resolution Error: Crop type '{crop_choice}' cannot be resolved."
                )
            
            raw_yield_impact = crop_match[climate_column].values[0] if not crop_match.empty else "Neutral"
            raw_water_impact = df_apv_wat_dem[climate_column].values[0]
            
            descriptor_map = {"Negative": 0, "Slightly Negative": 0, "Neutral": 1, "Slightly Positive": 2, "Positive": 2, "Very positive": 2}
            apv_evidence['Crop_Yield_Impact'] = descriptor_map.get(raw_yield_impact, 1)
            apv_evidence['Water_Demand_Impact'] = descriptor_map.get(raw_water_impact, 1)
            apv_evidence['Machinery_Compatibility'] = 2 if machinery_height < 2.0 else (1 if machinery_height <= 2.5 else 0)

            # 13. Crop Yield Impact SWOT
            if "Positive" in str(raw_yield_impact):
                swot_strengths.append("Overhead microclimate sheltering reduces heat stress and soil moisture loss, improving yields for shade-tolerant crops (e.g., berries, brassicas, root vegetables).")
            elif "Negative" in str(raw_yield_impact):
                swot_weaknesses.append("Light interception by dense panel coverage can cause yield loss in light-demanding field crops (e.g., grain maize, cereals).")

            net_impact = ((annual_energy_production_kwh * 20.0) - (actual_kwh_offset * float(country_row['Gri_Car'].values[0]))) / annual_energy_production_kwh if annual_energy_production_kwh > 0 else 0
            apv_evidence['Environmental_Potential'] = 0 if net_impact > 10.0 else (1 if -10.0 <= net_impact <= 10.0 else 2)

            # 14. Environmental Potential SWOT
            if net_impact > 10.0:
                swot_weaknesses.append("High grid-carbon displacement potential leads to a significant net reduction in farm greenhouse gas emissions.")
            elif net_impact < -10.0:
                swot_strengths.append("Operating on a deeply decarbonized local grid limits the direct emission-abatement leverage of additional solar generation.")

            # 15. Water Demand Impact SWOT
            if specific_yield > 1400:
                swot_opportunities.append("Microclimate sheltering and reduced evapotranspiration lower irrigation demand, improving drought resilience.")
            elif 0 < specific_yield < 1000:
                swot_threats.append("Inadequate module drip-lip management can concentrate rainwater runoff, causing localized soil erosion or waterlogging along panel edges.")

            apv_evidence['Land_Ownership'] = mapped_ownership
            apv_evidence['Successor_Planning'] = mapped_successor

            inference_apv = VariableElimination(bbn_apv_model)
            overall_apv = inference_apv.query(variables=['Overall_Feasibility'], evidence=apv_evidence)
            tech_apv = inference_apv.query(variables=['Technical_Feasibility'], evidence=apv_evidence)
            eco_apv = inference_apv.query(variables=['Economic_Feasibility'], evidence=apv_evidence)
            soc_apv = inference_apv.query(variables=['Social_Feasibility'], evidence=apv_evidence)
            env_apv = inference_apv.query(variables=['Environmental_Feasibility'], evidence=apv_evidence)
            agro_apv = inference_apv.query(variables=['Agronomic_Feasibility'], evidence=apv_evidence)
            
            scores_raw["overall"] = int(overall_apv.values[2] * 100)
            scores_raw["technical"] = int(tech_apv.values[2] * 100)
            scores_raw["economic"] = int(eco_apv.values[2] * 100)
            scores_raw["social"] = int(soc_apv.values[2] * 100)
            scores_raw["environmental"] = int(env_apv.values[2] * 100)
            scores_raw["agronomic"] = int(agro_apv.values[2] * 100)

    # ====================================================
    # 2: BIOGAS ENGINE & DYNAMIC SWOT
    # ====================================================
    if focus in ["Biogas", "Both"]:
        total_biogas_potential_nm3 = 0.0
        total_feedstock_input_tonnes = 0.0 
        biogas_data = data.get("biogas", {})
        selected_livestock = biogas_data.get("selectedLivestock", [])
        herd_details = biogas_data.get("herdDetails", {})
        manure_systems = biogas_data.get("manureSystems", {})
        
        # 1. Feedstock Calculations
        manure_rows = {"Bovine": "Dairy cattle", "Swine": "Pig/Swine (fattening)", "Poultry": "Broiler poultry"}
        for animal in selected_livestock:
            details = herd_details.get(animal, {})
            count = float(details.get("count") or 0)
            db_label = manure_rows.get(animal, "")
            if animal == "Bovine":
                db_label = "Dairy cattle" if "Dairy Cows" in details.get("subtype", []) else "Non-Dairy cattle"
                    
            row_data = df_ch4_the_pot[df_ch4_the_pot.iloc[:, 0] == db_label]
            if not row_data.empty:
                fresh_manure_per_year = float(row_data.iloc[0, 1])
                volatile_solids_pct = float(row_data.iloc[0, 2])
                biogas_yield_vs = float(row_data.iloc[0, 3])
                
                animal_potential = count * fresh_manure_per_year * volatile_solids_pct * biogas_yield_vs
                total_biogas_potential_nm3 += animal_potential
                total_feedstock_input_tonnes += (count * fresh_manure_per_year)

        max_crop_yield_nm3 = 0.0
        crop_tonnes = biogas_data.get("cropTonnes", {})
        for crop_name, tonnes in crop_tonnes.items():
            tonnes_val = float(tonnes or 0)
            if tonnes_val > 0:
                row_data = df_ch4_the_pot[df_ch4_the_pot.iloc[:, 0] == crop_name]
                if not row_data.empty:
                    vs_pct = float(row_data.iloc[0, 1])
                    biogas_yield_vs = float(row_data.iloc[0, 2])
                    crop_yield_nm3 = tonnes_val * vs_pct * biogas_yield_vs
                    
                    total_biogas_potential_nm3 += crop_yield_nm3
                    total_feedstock_input_tonnes += tonnes_val
                    
                    if crop_yield_nm3 > max_crop_yield_nm3:
                        max_crop_yield_nm3 = crop_yield_nm3

        # ----------------------------------------------------
        # DYNAMIC BIOGAS SWOT EVALUATION
        # ----------------------------------------------------

        # A. Feedstock Availability SWOT
        if total_biogas_potential_nm3 > 1500000:
            swot_strengths.append("High-volume on-farm feedstock (manure and crop biomass) ensures continuous, stable digester loading and high energy yields.")
        elif 0 < total_biogas_potential_nm3 < 750000:
            swot_weaknesses.append("Limited on-farm substrate volumes may lead to suboptimal digester capacity utilization and higher unit operating costs.")

        # B. Manure Collection Method SWOT
        has_liquid_system = any("Liquid" in str(sys) or "slurry" in str(sys).lower() or "Vacuum" in str(sys) for sys in manure_systems.values())
        has_solid_system = any("Solid" in str(sys) or "Deep Litter" in str(sys) or "bedding" in str(sys).lower() for sys in manure_systems.values())
        
        if has_liquid_system:
            swot_strengths.append("Automated slurry/liquid systems allow direct, frequent loading with minimal labor and preserve volatile solids for maximum methane yield.")
        if has_solid_system:
            swot_weaknesses.append("High straw bedding content requires mechanical pre-treatment (shredding/maceration) and increases solid-handling operational effort.")

        # C. Gas Grid Infrastructure SWOT
        gas_grid_status = biogas_data.get("infrastructure", {}).get("gasGrid", "")
        if gas_grid_status == "Yes":
            swot_opportunities.append("Proximity to the gas transmission or distribution grid creates potential for biomethane upgrading and direct pipeline injection.")
        elif gas_grid_status == "No":
            swot_threats.append("Distance from the gas grid limits energy recovery to on-site CHP electricity/heat or requires costly off-grid transport solutions.")

        # D. Ownership & Succession for Biogas
        if focus == "Biogas":
            if ownership == "Own":
                swot_strengths.append("Full freehold land ownership provides security for the permanent civil works, concrete storage, and deep utility lines required by a 15-year installation.")
            elif ownership:
                swot_weaknesses.append("Leasehold agreements may restrict heavy civil infrastructure and introduce contractual risk over the 15-year plant lifetime.")

            if "confirmed" in continuity.lower():
                swot_strengths.append("Defined multi-generation farm succession ensures continued operational expertise and management of capital-intensive plant equipment.")
            elif "not sure" in continuity.lower() or "not applicable" in continuity.lower():
                swot_weaknesses.append("Uncertain operational succession creates long-term risk for an asset requiring continuous monitoring and mechanical maintenance.")

        # Load Country Policies Profile Matrix
        ch4_evidence = {}
        ch4_roi = 0.0
        ch4_net_impact_g_kwh = 0.0
        
        if total_biogas_potential_nm3 > 1500000: ch4_evidence['Feedstock_Potential'] = 2
        elif total_biogas_potential_nm3 >= 1000000: ch4_evidence['Feedstock_Potential'] = 1
        else: ch4_evidence['Feedstock_Potential'] = 0

        ch4_country_row = df_ch4_main[df_ch4_main['Country'].str.lower() == country.lower()]
        if not ch4_country_row.empty:
            ch4_pol_raw = ch4_country_row['CH4_Pol'].values[0]
            ch4_per_raw = ch4_country_row['CH4_Per'].values[0]
            ch4_sub_raw = ch4_country_row['CH4_Sub'].values[0]
            ch4_rev_raw = ch4_country_row['CH4_Rev'].values[0]

            ch4_evidence['CH4_Pol'] = state_map.get(ch4_pol_raw, 1)
            ch4_evidence['CH4_Per'] = state_map.get(ch4_per_raw, 1)
            ch4_evidence['CH4_Sub'] = state_map.get(ch4_sub_raw, 1)
            ch4_evidence['CH4_Rev'] = state_map.get(ch4_rev_raw, 1)

            # E. Biogas Policy & Market Frameworks SWOT
            if ch4_pol_raw == "Positive":
                swot_opportunities.append("Favourable national policy and renewable gas targets streamline the regulatory roadmap for agricultural anaerobic digestion.")
            elif ch4_pol_raw == "Negative":
                swot_threats.append("Inconsistent or restrictive biogas regulations may increase administrative overhead and project risk.")

            if ch4_rev_raw == "Positive":
                swot_opportunities.append("Remuneration frameworks (feed-in tariffs, biomethane certificates, or power export) provide predictable long-term revenue.")
            elif ch4_rev_raw == "Negative":
                swot_threats.append("Low export compensation and lack of green gas certificate mechanisms make project viability strictly dependent on self-consumption savings.")

            if ch4_per_raw == "Positive":
                swot_opportunities.append("Clear environmental and spatial permitting standards allow for timely plant construction and commissioning.")
            elif ch4_per_raw == "Negative":
                swot_threats.append("Lengthy environmental impact assessments, emissions permitting, and zoning hurdles may delay installation.")

            if ch4_sub_raw == "Positive":
                swot_opportunities.append("Targeted capital investment grants and decarbonization subsidies lower initial digester and CHP capital expenditure.")
            elif ch4_sub_raw == "Negative":
                swot_threats.append("Limited subsidy availability requires full upfront capital financing and increases payback sensitivity.")
            
            # Financial Ledger Sizing
            resources_input = data.get("resources", {})
            user_elec_volume = float(resources_input.get("electricity", {}).get("value") or 0)
            user_gas_cost = float(resources_input.get("gas", {}).get("cost") or 0)
            user_fert_volume = float(resources_input.get("fertilizer", {}).get("value") or 0)
            user_fert_cost = float(resources_input.get("fertilizer", {}).get("cost") or 0)
            
            total_annual_energy_kwh = total_biogas_potential_nm3 * 9.97
            calculated_kw_capacity = total_annual_energy_kwh / 8000.0
            annual_electricity_produced_kwh = total_annual_energy_kwh * 0.35
            annual_heat_produced_kwh = total_annual_energy_kwh * 0.50
            
            if calculated_kw_capacity < 1000.0:
                capex = calculated_kw_capacity * 7500.0
                annual_opex = (annual_electricity_produced_kwh / 1000.0) * 30.0
            elif calculated_kw_capacity <= 10000.0:
                capex = calculated_kw_capacity * 2600.0
                annual_opex = (annual_electricity_produced_kwh / 1000.0) * 25.0
            else:
                capex = calculated_kw_capacity * 2000.0
                annual_opex = (annual_electricity_produced_kwh / 1000.0) * 20.0
                
            ch4_lifecycle_cost = capex + (annual_opex * 15.0)
            db_electricity_price_kwh = float(ch4_country_row['Ele_Cos'].values[0]) / 100.0
            offset_electricity_kwh = min(annual_electricity_produced_kwh, user_elec_volume)
            annual_electricity_savings = offset_electricity_kwh * db_electricity_price_kwh
            
            annual_gas_savings = user_gas_cost  
            annual_fertilizer_savings = user_fert_cost  
            
            ch4_lifecycle_savings = (annual_electricity_savings + annual_gas_savings + annual_fertilizer_savings) * 15.0
            ch4_roi = ((ch4_lifecycle_savings - ch4_lifecycle_cost) / ch4_lifecycle_cost * 100.0) if ch4_lifecycle_cost > 0 else 0.0
            
            if ch4_roi > 50.0: ch4_evidence['Economic_Potential'] = 2
            elif ch4_roi >= -25.0: ch4_evidence['Economic_Potential'] = 1
            else: ch4_evidence['Economic_Potential'] = 0

            # F. Return on Investment (ROI) SWOT
            if ch4_roi > 50.0:
                swot_strengths.append("Substantial combined savings across electricity, heating fuel, and mineral fertilizers deliver an attractive payback profile.")
            elif ch4_roi < 0.0:
                swot_weaknesses.append("High capital expenditure relative to energy offsets results in a long financial payback period under standard tariff baselines.")

            # Environmental Calculations
            digestate_produced_tonnes = total_feedstock_input_tonnes * 0.9
            offset_fertilizer_tonnes = min(digestate_produced_tonnes, user_fert_volume)
            
            fertilizer_emissions_avoided_g = offset_fertilizer_tonnes * 3.5 * 1000000.0
            electricity_emissions_avoided_g = offset_electricity_kwh * float(ch4_country_row['Gri_Car'].values[0])
            natural_gas_emissions_avoided_g = annual_heat_produced_kwh * 202.0
            biogas_embodied_emissions_g = annual_electricity_produced_kwh * 220.0
            
            total_avoided_g = electricity_emissions_avoided_g + natural_gas_emissions_avoided_g + fertilizer_emissions_avoided_g
            ch4_net_impact_g_kwh = (biogas_embodied_emissions_g - total_avoided_g) / annual_electricity_produced_kwh if annual_electricity_produced_kwh > 0 else 0.0
            
            if ch4_net_impact_g_kwh < -10.0: ch4_evidence['Environmental_Potential'] = 2
            elif ch4_net_impact_g_kwh <= 10.0: ch4_evidence['Environmental_Potential'] = 1
            else: ch4_evidence['Environmental_Potential'] = 0

            # G. Net GHG Impact SWOT
            if ch4_net_impact_g_kwh < -10.0:
                swot_strengths.append("Capturing raw manure methane emissions and displacing fossil fuel and synthetic fertilizer produces a strong net-negative carbon footprint.")
            elif ch4_net_impact_g_kwh > 10.0:
                swot_weaknesses.append("Intensive processing energy or high-emission feedstocks limit the net greenhouse gas abatement potential.")

        # Social / Odor Impact SWOT
        odor_score = min(4, int(total_feedstock_input_tonnes // 2000))
        ch4_evidence['CH4_Odor_Impact'] = odor_score
        if odor_score >= 3:
            swot_threats.append("Large substrate handling volumes and open digestate basins near residential zones risk odor complaints and local community pushback.")
        else:
            swot_opportunities.append("Enclosed storage, sealed digesters, and digested slurry reduce raw manure odor, improving community relations.")

        # Agronomic Calculations
        if max_crop_yield_nm3 > 1500000: ch4_evidence['Main_Crop_Potential'] = 2
        elif max_crop_yield_nm3 >= 1000000: ch4_evidence['Main_Crop_Potential'] = 1
        else: ch4_evidence['Main_Crop_Potential'] = 0

        rotation_crops_list = biogas_data.get("selectedCrops", [])
        total_rotational_potential_yield = 0.0
        valid_crop_lookups = 0
        
        for rot_crop in rotation_crops_list:
            row_data = df_ch4_the_pot[df_ch4_the_pot.iloc[:, 0] == rot_crop]
            if not row_data.empty:
                vs_factor = float(row_data.iloc[0, 1] or 0)
                yield_factor = float(row_data.iloc[0, 2] or 0)
                total_rotational_potential_yield += (vs_factor * yield_factor)
                valid_crop_lookups += 1
                
        avg_rotation_yield = (total_rotational_potential_yield / valid_crop_lookups) if valid_crop_lookups > 0 else 0.0
        
        if avg_rotation_yield > 400.0: ch4_evidence['Rotation_Crops_Potential'] = 2 
        elif avg_rotation_yield >= 200.0: ch4_evidence['Rotation_Crops_Potential'] = 1 
        else: ch4_evidence['Rotation_Crops_Potential'] = 0 

        # H. Crops & Residue Potential SWOT
        if avg_rotation_yield > 400.0:
            swot_strengths.append("High-energy substrate rotation (e.g., maize, beet pulp) boosts methane production without requiring proportional digester volume increases.")
        elif 0 < avg_rotation_yield < 200.0:
            swot_weaknesses.append("Low-yielding fibrous residues provide lower specific methane output, requiring larger retention times and digester sizing.")

        ch4_evidence['CH4_Land_Ownership'] = mapped_ownership
        ch4_evidence['CH4_Successor_Planning'] = mapped_successor
        if total_biogas_potential_nm3 <= 0:
            ch4_evidence['Feedstock_Potential'] = 0
            ch4_evidence['Economic_Potential'] = 0
            ch4_evidence['Environmental_Potential'] = 0
            ch4_evidence['Main_Crop_Potential'] = 0
            ch4_evidence['Rotation_Crops_Potential'] = 0
            ch4_net_impact_g_kwh = 999.0  
            ch4_roi = -100.0
            
        inference_ch4 = VariableElimination(bbn_ch4_model)
        overall_ch4 = inference_ch4.query(variables=['Overall_Feasibility'], evidence=ch4_evidence)
        tech_ch4 = inference_ch4.query(variables=['Technical_Feasibility'], evidence=ch4_evidence)
        eco_ch4 = inference_ch4.query(variables=['Economic_Feasibility'], evidence=ch4_evidence)
        soc_ch4 = inference_ch4.query(variables=['Social_Feasibility'], evidence=ch4_evidence)
        env_ch4 = inference_ch4.query(variables=['Environmental_Feasibility'], evidence=ch4_evidence)
        agro_ch4 = inference_ch4.query(variables=['Agronomic_Feasibility'], evidence=ch4_evidence)
        
        if focus == "Biogas":
            scores_raw["overall"] = int(overall_ch4.values[2] * 100)
            scores_raw["technical"] = int(tech_ch4.values[2] * 100)
            scores_raw["economic"] = int(eco_ch4.values[2] * 100)
            scores_raw["social"] = int(soc_ch4.values[2] * 100)
            scores_raw["environmental"] = int(env_ch4.values[2] * 100)
            scores_raw["agronomic"] = int(agro_ch4.values[2] * 100)
        else:
            for key in ["overall", "technical", "economic", "social", "environmental", "agronomic"]:
                if key not in scores_raw:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Inference Engine Error: Combined mode execution failed. Expected Agrivoltaics data point '{key}' was not found before cross-network merge."
                    )
            scores_raw["overall"] = int((scores_raw["overall"] + (overall_ch4.values[2] * 100)) / 2)
            scores_raw["technical"] = int((scores_raw["technical"] + (tech_ch4.values[2] * 100)) / 2)
            scores_raw["economic"] = int((scores_raw["economic"] + (eco_ch4.values[2] * 100)) / 2)
            scores_raw["social"] = int((scores_raw["social"] + (soc_ch4.values[2] * 100)) / 2)
            scores_raw["environmental"] = int((scores_raw["environmental"] + (env_ch4.values[2] * 100)) / 2)
            scores_raw["agronomic"] = int((scores_raw["agronomic"] + (agro_ch4.values[2] * 100)) / 2)

    required_metrics = ["overall", "technical", "economic", "social", "environmental", "agronomic"]
    missing_metrics = [metric for metric in required_metrics if metric not in scores_raw]

    if missing_metrics:
        raise HTTPException(
            status_code=500, 
            detail=f"Inference Engine Error: Missing probabilistic components: {', '.join(missing_metrics)}"
        )

    def get_light(score):
        if score < 10: return "🔴"
        elif score > 50: return "🟢"
        return "🟡"

    status_lights = {k: get_light(v) for k, v in scores_raw.items()}

# ----------------------------------------------------
    # 1. UPDATED TRAFFIC LIGHT THRESHOLDS
    # ----------------------------------------------------
    def get_light(score):
        if score < 10:
            return "🔴"
        elif score > 50:
            return "🟢"
        return "🟡"

    status_lights = {k: get_light(v) for k, v in scores_raw.items()}

    # ----------------------------------------------------
    # 2. UPDATED DYNAMIC RECOMMENDATIONS ENGINE
    # ----------------------------------------------------
    dynamic_recommendations = []
    overall_score = scores_raw.get("overall", 50)

    # Tier 1: Primary Framework Progression
    if overall_score >= 10:
        # Green (🟢) or Orange (🟡)
        dynamic_recommendations.append(
            "Overall Feasibility is positive/moderate: Proceed to Step 3 (Transition) of the Value4Farm Decision Support Tool to explore actionable deployment paths, detailed engineering designs, and local expert support."
        )
    else:
        # Red (🔴)
        dynamic_recommendations.append(
            "Overall Feasibility shows critical bottlenecks (<10%): Re-evaluate fundamental parameters (such as land tenure terms, grid connectivity, or minimum scale) to improve viability before capital commitment."
        )

    # Tier 2: Targeted Remediation for Specific Red (🔴) Aspects (Score < 10)
    if scores_raw.get("agronomic", 100) < 10:
        if focus in ["Agrivoltaics", "Both"]:
            dynamic_recommendations.append(
                "Agronomic Remediation: Shift toward shade-tolerant crop varieties (e.g., berries, brassicas, root vegetables) or increase inter-row panel spacing to reduce photosynthetically active radiation (PAR) deficits."
            )
        if focus == "Biogas":
            dynamic_recommendations.append(
                "Agronomic Remediation: Introduce higher methane-yield rotation substrates (e.g., energy beet, maize silage) to optimize digester biological efficiency."
            )

    if scores_raw.get("technical", 100) < 10:
        if focus in ["Agrivoltaics", "Both"]:
            dynamic_recommendations.append(
                "Technical Remediation: Increase module clearance height or reconfigure row spacing to eliminate interference with current farm machinery dimensions."
            )
        if focus == "Biogas":
            dynamic_recommendations.append(
                "Technical Remediation: Modernize feedstock handling systems (e.g., automated slurry scraping or high-volume pumps) to ensure steady volatile solids loading."
            )

    if scores_raw.get("economic", 100) < 10:
        if focus in ["Agrivoltaics", "Both"]:
            dynamic_recommendations.append(
                "Economic Remediation: Maximize on-site power self-consumption or explore local renewable energy communities to safeguard against wholesale grid price volatility."
            )
        if focus in ["Biogas", "Both"]:
            dynamic_recommendations.append(
                "Economic Remediation: Evaluate co-digestion partnerships with neighboring farms to distribute capital costs and secure high-energy co-substrates."
            )

    if scores_raw.get("social", 100) < 10:
        if focus in ["Biogas", "Both"]:
            dynamic_recommendations.append(
                "Social/Odor Remediation: Implement air-tight digester dome covers and bio-filtration units on storage pits to mitigate odor impact and protect neighbor relations."
            )
        if focus in ["Agrivoltaics", "Both"]:
            dynamic_recommendations.append(
                "Social/Landscape Remediation: Plant perimeter hedgerows or vegetative screens along adjacent roadways and public viewpoints."
            )

    if scores_raw.get("environmental", 100) < 10:
        dynamic_recommendations.append(
            "Environmental Remediation: Optimize nutrient cycles by utilizing digested bio-fertilizer to fully displace synthetic mineral fertilizer purchases."
        )

    
    # ====================================================
    # SWOT POST-PROCESSING: GUARANTEE EXACTLY 3 POINTS PER CATEGORY
    # ====================================================
    fallback_pool = {
        "strengths": [
            "Dual-use land and bio-resource design maintains underlying agricultural production while adding a reliable energy yield stream.",
            "Standard electrical balance-of-system and CHP components provide straightforward integration and long-term reliability.",
            "Preservation of core farming activities maintains eligibility for standard agricultural land classification and support.",
            "Modular installation layout allows flexible phasing and straightforward future maintenance access."
        ],
        "weaknesses": [
            "Increased initial engineering and installation complexity compared to single-purpose installations.",
            "Operational management must account for machinery movement constraints and biological digester balance.",
            "Long-term soil compaction and substrate storage maintenance require structured operational workflows.",
            "Seasonal maintenance schedules must be tightly coordinated with crop planting and harvesting cycles."
        ],
        "opportunities": [
            "Participation in regional energy communities or direct corporate power purchase agreements (PPAs) can enhance revenue.",
            "Utilization of processed organic digestate internally systematically phases out synthetic mineral fertilizer expenditures.",
            "Emerging bio-economy research and standardized agricultural module designs continue to reduce balance-of-system costs.",
            "Potential for biodiversity enhancement and emissions reduction along uncultivated boundary buffer strips."
        ],
        "threats": [
            "Future fluctuations in grid connection capacity and regional transmission queue timelines may delay activation.",
            "Evolving regional dual-use and emissions regulations may require periodic compliance adjustments over the asset lifespan.",
            "Extreme weather events and supply chain variations require robust operational planning and insurance coverage.",
            "Shifting wholesale electricity/gas market dynamics and curtailment policies may affect long-term feed-in economics."
        ]
    }

    def finalize_swot_category(collected_items: list, category_key: str, max_count: int = 3) -> list:
        unique_items = []
        for item in collected_items:
            if item not in unique_items:
                unique_items.append(item)
        
        for fallback in fallback_pool[category_key]:
            if len(unique_items) >= max_count:
                break
            if fallback not in unique_items:
                unique_items.append(fallback)
                
        return unique_items[:max_count]

    swot = {
        "strengths": finalize_swot_category(swot_strengths, "strengths", 3),
        "weaknesses": finalize_swot_category(swot_weaknesses, "weaknesses", 3),
        "opportunities": finalize_swot_category(swot_opportunities, "opportunities", 3),
        "threats": finalize_swot_category(swot_threats, "threats", 3)
    }

    # ====================================================
    # PDF RENDERING TEMPLATE
    # ====================================================
    html_template = """
    <html>
    <head>
        <style>
            body { font-family: sans-serif; color: #1e293b; padding: 20px; }
            h1 { color: #74776A; border-bottom: 2px solid #95C11F; padding-bottom: 8px; font-size: 24px; }
            h2 { color: #74776A; font-size: 16px; margin-top: 20px; }
            .badge { font-size: 12px; font-weight: bold; padding: 4px 8px; border-radius: 4px; }
            .grid { display: flex; flex-wrap: wrap; margin-top: 15px; }
            .card { width: 46%; margin: 1%; padding: 12px; border-radius: 8px; box-sizing: border-box; }
            .strengths { background-color: #ecfdf5; border-left: 4px solid #10b981; }
            .weaknesses { background-color: #fef2f2; border-left: 4px solid #ef4444; }
            .opportunities { background-color: #eff6ff; border-left: 4px solid #3b82f6; }
            .threats { background-color: #fffbeb; border-left: 4px solid #f59e0b; }
            .card h3 { margin-top: 0; font-size: 14px; text-transform: uppercase; }
            ul { margin: 0; padding-left: 18px; font-size: 11px; line-height: 1.4; }
            li { margin-bottom: 6px; }
            .indicator-row { display: flex; margin: 15px 0; border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden; }
            .indicator-item { flex: 1; text-align: center; padding: 8px; font-size: 10px; font-weight: bold; text-transform: uppercase; border-right: 1px solid #e2e8f0; }
            .indicator-item:last-child { border-right: none; }
            .indicator-item span { display: block; font-size: 18px; margin-top: 4px; }
        </style>
    </head>
    <body>
        <h1>Value4Farm Audit Assessment Report</h1>
        <p><strong>Location:</strong> {{ loc }} &nbsp;|&nbsp; <strong>Focus:</strong> {{ focus }}</p>
        
        <h2>Feasibility Indicators</h2>
        <div class="indicator-row">
            <div class="indicator-item">Overall<span>{{ lights.overall }}</span></div>
            <div class="indicator-item">Technical<span>{{ lights.technical }}</span></div>
            <div class="indicator-item">Economic<span>{{ lights.economic }}</span></div>
            <div class="indicator-item">Social<span>{{ lights.social }}</span></div>
            <div class="indicator-item">Environmental<span>{{ lights.environmental }}</span></div>
            <div class="indicator-item">Agronomic<span>{{ lights.agronomic }}</span></div>
        </div>

        <h2>Dynamic SWOT Analysis</h2>
        <div class="grid">
            <div class="card strengths">
                <h3 style="color: #059669;">Strengths</h3>
                <ul>
                    {% for item in swot.strengths %}
                    <li>{{ item }}</li>
                    {% endfor %}
                </ul>
            </div>
            <div class="card weaknesses">
                <h3 style="color: #dc2626;">Weaknesses</h3>
                <ul>
                    {% for item in swot.weaknesses %}
                    <li>{{ item }}</li>
                    {% endfor %}
                </ul>
            </div>
            <div class="card opportunities">
                <h3 style="color: #2563eb;">Opportunities</h3>
                <ul>
                    {% for item in swot.opportunities %}
                    <li>{{ item }}</li>
                    {% endfor %}
                </ul>
            </div>
            <div class="card threats">
                <h3 style="color: #d97706;">Threats</h3>
                <ul>
                    {% for item in swot.threats %}
                    <li>{{ item }}</li>
                    {% endfor %}
                </ul>
            </div>
        </div>

        <h2>Recommendations</h2>
        <ul>
            {% for rec in recommendations %}
            <li style="font-size: 11px; margin-bottom: 4px;">{{ rec }}</li>
            {% endfor %}
        </ul>
    </body>
    </html>
    """
    rendered_html = Template(html_template).render(
        loc=country, focus=focus, lights=status_lights, swot=swot, recommendations=dynamic_recommendations
    )
    pdf_bytes = HTML(string=rendered_html).write_pdf()
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

    return {
        "scores": scores_raw,
        "lights": status_lights,
        "swot": swot,
        "recommendations": dynamic_recommendations,
        "pdf": pdf_base64
    }
