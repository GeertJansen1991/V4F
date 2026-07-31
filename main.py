from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Enable CORS for frontend communication across different origins/domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Render paths are relative to the root directory where the application runs
EXCEL_PATH = "APV_DST (Clean).xlsx"
BIOGAS_EXCEL_PATH = "CH4_DST (Clean).xlsx"

# Global placeholders for startup caching - Explicitly Named!
df_apv_main, df_apv_cro_yld, df_apv_wat_dem = None, None, None
df_ch4_main, df_ch4_the_pot, df_ch4_pro_pot, df_ch4_har_cha = None, None, None, None

# Independent BBN Model Graph Engines
bbn_apv_model = None
bbn_ch4_model = None

@app.on_event("startup")
def initialize_system():
    """Caches Excel matrices for both APV and Biogas and setups both graph networks."""
    global df_apv_main, df_apv_cro_yld, df_apv_wat_dem
    global df_ch4_main, df_ch4_the_pot, df_ch4_pro_pot, df_ch4_har_cha
    global bbn_apv_model, bbn_ch4_model
    
    if not os.path.exists(EXCEL_PATH) or not os.path.exists(BIOGAS_EXCEL_PATH):
        raise FileNotFoundError("Missing database spreadsheet dependencies in root directory.")
        
    # 1. Caches for APV (Solar)
    df_apv_main = pd.read_excel(EXCEL_PATH, sheet_name='APV_Main')
    df_apv_cro_yld = pd.read_excel(EXCEL_PATH, sheet_name='APV_Cro_Yld')
    df_apv_wat_dem = pd.read_excel(EXCEL_PATH, sheet_name='APV_Wat_Dem')
    
    # 2. Caches for CH4 (Biogas)
    df_ch4_main = pd.read_excel(BIOGAS_EXCEL_PATH, sheet_name='CH4_main')
    df_ch4_the_pot = pd.read_excel(BIOGAS_EXCEL_PATH, sheet_name='CH4_The_Pot')
    df_ch4_pro_pot = pd.read_excel(BIOGAS_EXCEL_PATH, sheet_name='CH4_Pro_Pot')
    df_ch4_har_cha = pd.read_excel(BIOGAS_EXCEL_PATH, sheet_name='CH4_Har_Cha')
    
    # ====================================================
    # NETWORK 1: AGRIVOLTAICS GRAPH (APV)
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

    # Assign core static distribution states for APV
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
                    gov_matrix.append([1.0-avg, avg*0.4, avg*0.6])
    cpd_gov = TabularCPD('Governance', 3, np.array(gov_matrix).T.tolist(), evidence=['APV_Pol', 'APV_Per', 'APV_Sub', 'APV_Rev'], evidence_card=[3,3,3,3])

    tech_matrix = []
    for g in [0,1,2]:
        for e in [0,1,2]:
            combined = (g+e)/4.0
            tech_matrix.append([1.0-combined, combined*0.3, combined*0.7])
    cpd_tech = TabularCPD('Technical_Feasibility', 3, np.array(tech_matrix).T.tolist(), evidence=['Governance', 'Energy_Potential'], evidence_card=[3,3])

    eco_matrix = []
    for econ in [0,1,2]: 
        for rev in [0,1,2]:  
            combined = (econ+rev)/4.0
            eco_matrix.append([1.0-combined, combined*0.2, combined*0.8])
    cpd_eco_feas = TabularCPD('Economic_Feasibility', 3, np.array(eco_matrix).T.tolist(), evidence=['Economic_Potential', 'APV_Rev'], evidence_card=[3,3])

    soc_matrix = []
    for vis in [0,1,2,3,4]: 
        social_score = 1.0 - (vis/4.0) 
        soc_matrix.append([1.0-social_score, social_score*0.3, social_score*0.7])
    cpd_soc_feas = TabularCPD('Social_Feasibility', 3, np.array(soc_matrix).T.tolist(), evidence=['Visual_Impact'], evidence_card=[5])

    agro_matrix = []
    for yld in [0,1,2]:     
        for wat in [0,1,2]:  
            for mac in [0,1,2]: 
                combined = (yld+wat+mac)/6.0
                agro_matrix.append([1.0-combined, combined*0.3, combined*0.7])
    cpd_agro_feas = TabularCPD('Agronomic_Feasibility', 3, np.array(agro_matrix).T.tolist(), evidence=['Crop_Yield_Impact', 'Water_Demand_Impact', 'Machinery_Compatibility'], evidence_card=[3,3,3])

    env_matrix = []
    for env_pot in [0,1,2]:
        combined = env_pot/2.0
        env_matrix.append([1.0-combined, combined*0.2, combined*0.8])
    cpd_env_feas = TabularCPD('Environmental_Feasibility', 3, np.array(env_matrix).T.tolist(), evidence=['Environmental_Potential'], evidence_card=[3])

    overall_matrix = []
    for t in [0,1,2]:      
        for ec in [0,1,2]: 
            for s in [0,1,2]:  
                for a in [0,1,2]:  
                    for en in [0,1,2]: 
                        for o in [0,1,2]:  
                            for su in [0,1,2]: 
                                score = (t*2 + ec*2.5 + s*1.2 + a*1.5 + en*1.5 + o*1.5 + su*1.3) / 23.0
                                overall_matrix.append([1.0 - score, score * 0.25, score * 0.75])
                                
    cpd_overall = TabularCPD('Overall_Feasibility', 3, np.array(overall_matrix).T.tolist(),
                             evidence=['Technical_Feasibility', 'Economic_Feasibility', 'Social_Feasibility', 
                                       'Agronomic_Feasibility', 'Environmental_Feasibility', 'Land_Ownership', 'Successor_Planning'],
                             evidence_card=[3, 3, 3, 3, 3, 3, 3])

    model_apv.add_cpds(cpd_pol, cpd_per, cpd_sub, cpd_rev, cpd_ene, cpd_eco, cpd_vis, cpd_cyi, cpd_wdi, cpd_mac, cpd_env, cpd_own, cpd_suc,
                       cpd_gov, cpd_tech, cpd_eco_feas, cpd_soc_feas, cpd_agro_feas, cpd_env_feas, cpd_overall)
    model_apv.check_model()
    bbn_apv_model = model_apv

    # ====================================================
    # NETWORK 2: BIOGAS GRAPH (CH4) - PROBABILISTIC FEASIBILITIES
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

    # Assign base structural distribution states for CH4 Network Nodes
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
                    ch4_gov_matrix.append([1.0-avg, avg*0.4, avg*0.6])
    cpd_ch4_gov = TabularCPD('CH4_Governance', 3, np.array(ch4_gov_matrix).T.tolist(), 
                             evidence=['CH4_Pol', 'CH4_Per', 'CH4_Sub', 'CH4_Rev'], evidence_card=[3,3,3,3])

    ch4_tech_matrix = []
    for g in [0,1,2]:
        for f in [0,1,2]:
            combined = (g+f)/4.0
            ch4_tech_matrix.append([1.0-combined, combined*0.3, combined*0.7])
    cpd_ch4_tech = TabularCPD('Technical_Feasibility', 3, np.array(ch4_tech_matrix).T.tolist(), 
                              evidence=['CH4_Governance', 'Feedstock_Potential'], evidence_card=[3,3])

    ch4_eco_matrix = []
    for econ in [0,1,2]:
        for rev in [0,1,2]:
            combined = (econ+rev)/4.0
            ch4_eco_matrix.append([1.0-combined, combined*0.2, combined*0.8])
    cpd_ch4_eco_feas = TabularCPD('Economic_Feasibility', 3, np.array(ch4_eco_matrix).T.tolist(), 
                                  evidence=['Economic_Potential', 'CH4_Rev'], evidence_card=[3,3])

    ch4_soc_matrix = []
    for odor in [0,1,2,3,4]: 
        social_score = 1.0 - (odor/4.0) 
        ch4_soc_matrix.append([1.0-social_score, social_score*0.3, social_score*0.7])
    cpd_ch4_soc_feas = TabularCPD('Social_Feasibility', 3, np.array(ch4_soc_matrix).T.tolist(), evidence=['CH4_Odor_Impact'], evidence_card=[5])

    ch4_env_matrix = []
    for env_pot in [0,1,2]:
        combined = env_pot/2.0
        ch4_env_matrix.append([1.0-combined, combined*0.2, combined*0.8])
    cpd_ch4_env_feas = TabularCPD('Environmental_Feasibility', 3, np.array(ch4_env_matrix).T.tolist(), 
                                  evidence=['Environmental_Potential'], evidence_card=[3])

    ch4_agro_matrix = []
    for main_c in [0,1,2]:
        for rot_c in [0,1,2]:
            combined = (main_c + rot_c)/4.0
            ch4_agro_matrix.append([1.0-combined, combined*0.3, combined*0.7])
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
                                score = (t*2.0 + ec*2.0 + s*1.0 + a*2.0 + en*1.5 + o*1.0 + su*1.0) / 10.5
                                ch4_overall_matrix.append([1.0 - score, score * 0.25, score * 0.75])
                                
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
    
    # Common Parameters
    mapped_ownership = 2 if ownership == "Own" else (1 if "Share" in ownership or "Lease" in ownership else 0)
    mapped_successor = 2 if "confirmed" in continuity.lower() or "formal" in continuity.lower() else 1

    # ====================================================
    # EXECUTION BRANCH 1: AGRIVOLTAICS ENGINE
    # ====================================================
    if focus in ["Agrivoltaics", "Both"]:
        agri = data.get("agrivoltaics", {})
        available_ha = float(agri.get("landSpace") or 2.5)
        machinery_height = float(agri.get("maxHeight") or 2.2)
        crops_list = agri.get("currentCrops", [])
        crop_choice = crops_list[0] if crops_list else "Cereals"
        resources = data.get("resources", {})
        user_electricity_usage = float(resources.get("electricity", {}).get("value") or 50000)

        country_row = df_apv_main[df_apv_main['Country'].str.lower() == country.lower()]
        if not country_row.empty:
            apv_evidence = {}
            apv_evidence['APV_Pol'] = state_map.get(country_row['APV_Pol'].values[0], 1)
            apv_evidence['APV_Per'] = state_map.get(country_row['APV_Per'].values[0], 1)
            apv_evidence['APV_Sub'] = state_map.get(country_row['APV_Sub'].values[0], 1)
            apv_evidence['APV_Rev'] = state_map.get(country_row['APV_Rev'].values[0], 1)

            capacity_factor_raw = float(country_row['APV_Cap_Fac'].values[0])
            if capacity_factor_raw < 12.0: climate_column = "Climate 1 (<750 W/m²)"
            elif 12.0 <= capacity_factor_raw < 14.5: climate_column = "Climate 2 (750–1099 W/m²)"
            elif 14.5 <= capacity_factor_raw < 16.5: climate_column = "Climate 3 (1100–1749 W/m²)"
            else: climate_column = "Climate 4 (>1750 W/m²)"

            installed_capacity_kwp = (available_ha * 10000) * 0.22 * 0.6
            annual_energy_production_kwh = installed_capacity_kwp * 8760 * (capacity_factor_raw / 100.0)
            specific_yield = annual_energy_production_kwh / installed_capacity_kwp if installed_capacity_kwp > 0 else 0
            apv_evidence['Energy_Potential'] = 0 if specific_yield < 1000 else (1 if specific_yield < 1400 else 2)

            lifecycle_cost = installed_capacity_kwp * 1000 * 1.125
            actual_kwh_offset = min(annual_energy_production_kwh * 0.80, user_electricity_usage)
            electricity_price_kwh = float(country_row['Ele_Cos'].values[0]) / 100
            lifecycle_savings = actual_kwh_offset * electricity_price_kwh * 25
            roi = ((lifecycle_savings - lifecycle_cost) / lifecycle_cost) * 100 if lifecycle_cost > 0 else 0
            apv_evidence['Economic_Potential'] = 0 if roi < -25 else (1 if roi < 50 else 2)

            apv_evidence['Visual_Impact'] = min(4, int(available_ha // 2))

            crop_match = df_apv_cro_yld[df_apv_cro_yld['Crop Category'].str.lower().str.contains(crop_choice.lower()[:5])]
            raw_yield_impact = crop_match[climate_column].values[0] if not crop_match.empty else "Neutral"
            raw_water_impact = df_apv_wat_dem[climate_column].values[0]
            
            descriptor_map = {"Negative": 0, "Slightly Negative": 0, "Neutral": 1, "Slightly Positive": 2, "Positive": 2, "Very positive": 2}
            apv_evidence['Crop_Yield_Impact'] = descriptor_map.get(raw_yield_impact, 1)
            apv_evidence['Water_Demand_Impact'] = descriptor_map.get(raw_water_impact, 1)
            apv_evidence['Machinery_Compatibility'] = 2 if machinery_height < 2.0 else (1 if machinery_height <= 2.5 else 0)

            net_impact = ((annual_energy_production_kwh * 20.0) - (actual_kwh_offset * float(country_row['Gri_Car'].values[0]))) / annual_energy_production_kwh
            apv_evidence['Environmental_Potential'] = 0 if net_impact > 10.0 else (1 if -10.0 <= net_impact <= 10.0 else 2)

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
            scores_raw["socio_economic"] = int(eco_apv.values[2] * 100)
            scores_raw["social"] = int(soc_apv.values[2] * 100)
            scores_raw["environmental"] = int(env_apv.values[2] * 100)
            scores_raw["agronomic"] = int(agro_apv.values[2] * 100)
            
            swot_strengths.append(f"High Local Solar Density sizing footprint matching {round(installed_capacity_kwp, 1)} kWp.")
            if net_impact < -10.0:
                swot_strengths.append("Significant solar grid greenhouse gas savings offset expected.")

    # ====================================================
    # EXECUTION BRANCH 2: BIOGAS ENGINE (CH4) - NATIVE BBN INFERENCE
    # ====================================================
    if focus in ["Biogas", "Both"]:
        total_biogas_potential_nm3 = 0.0
        total_feedstock_input_tonnes = 0.0 
        biogas_data = data.get("biogas", {})
        selected_livestock = biogas_data.get("selectedLivestock", [])
        herd_details = biogas_data.get("herdDetails", {})
        
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

        # Track crop production profiles
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

        ch4_evidence = {}
        
        # Discretize Feedstock Input Node
        if total_biogas_potential_nm3 > 1500000: ch4_evidence['Feedstock_Potential'] = 2
        elif total_biogas_potential_nm3 >= 1000000: ch4_evidence['Feedstock_Potential'] = 1
        else: ch4_evidence['Feedstock_Potential'] = 0

        # Load Country Policies Profile Matrix
        ch4_country_row = df_ch4_main[df_ch4_main['Country'].str.lower() == country.lower()]
        if not ch4_country_row.empty:
            ch4_evidence['CH4_Pol'] = state_map.get(ch4_country_row['CH4_Pol'].values[0], 1)
            ch4_evidence['CH4_Per'] = state_map.get(ch4_country_row['CH4_Per'].values[0], 1)
            ch4_evidence['CH4_Sub'] = state_map.get(ch4_country_row['CH4_Sub'].values[0], 1)
            ch4_evidence['CH4_Rev'] = state_map.get(ch4_country_row['CH4_Rev'].values[0], 1)
            
            # Financial Ledger Sizing Metrics
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

            # Environmental Impact Modeling
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

        # Odor proxy discretization mapping for Biogas Social node
        ch4_evidence['CH4_Odor_Impact'] = min(4, int(total_feedstock_input_tonnes // 2000))

        # Agronomic Node Assignment Engine
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

        # Structural variables context binding
        ch4_evidence['CH4_Land_Ownership'] = mapped_ownership
        ch4_evidence['CH4_Successor_Planning'] = mapped_successor

        # Query dynamic execution matrix through inferential pipeline
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
            scores_raw["socio_economic"] = int(eco_ch4.values[2] * 100)
            scores_raw["social"] = int(soc_ch4.values[2] * 100)
            scores_raw["environmental"] = int(env_ch4.values[2] * 100)
            scores_raw["agronomic"] = int(agro_ch4.values[2] * 100)
        else:
            # Dynamic cross-network mean integration for combined mode assessments
            scores_raw["overall"] = int(((scores_raw.get("overall", 50)) + (overall_ch4.values[2] * 100)) / 2)
            scores_raw["technical"] = int(((scores_raw.get("technical", 50)) + (tech_ch4.values[2] * 100)) / 2)
            scores_raw["economic"] = int(((scores_raw.get("economic", 50)) + (eco_ch4.values[2] * 100)) / 2)
            scores_raw["socio_economic"] = scores_raw["economic"]
            scores_raw["social"] = int(((scores_raw.get("social", 50)) + (soc_ch4.values[2] * 100)) / 2)
            scores_raw["environmental"] = int(((scores_raw.get("environmental", 50)) + (env_ch4.values[2] * 100)) / 2)
            scores_raw["agronomic"] = int(((scores_raw.get("agronomic", 50)) + (agro_ch4.values[2] * 100)) / 2)

        swot_strengths.append(f"Calculated Biogas Loading Asset: {round(total_biogas_potential_nm3, 1)} Nm3/yr available.")
        if ch4_roi > 50.0:
            swot_strengths.append(f"Highly positive Biogas return profile tracking a long-term ROI of {round(ch4_roi, 1)}%.")
        elif ch4_roi < -25.0:
            swot_weaknesses.append(f"Biogas lifecycle capital constraints: operational costs contract net returns ({round(ch4_roi, 1)}% ROI).")
            
        if ch4_net_impact_g_kwh < -10.0:
            swot_strengths.append(f"Substantial climate loop tracking benefits: generated organic digestate replaces up to {round(offset_fertilizer_tonnes, 1)} tonnes of synthetic mineral input compounds.")
        elif ch4_net_impact_g_kwh > 10.0:
            swot_weaknesses.append("Biogas footprint constraint: intensive localized operations yield low net greenhouse gas offsets.")

    # Status indicators mappings
    def get_light(score):
        if score < 40: return "🔴"
        elif score > 70: return "🟢"
        return "🟡"

    status_lights = {k: get_light(v) for k, v in scores_raw.items()}

    swot = {
        "strengths": swot_strengths,
        "weaknesses": swot_weaknesses if swot_weaknesses else ["No structural workflows hazard metrics observed."],
        "opportunities": ["Integrated farm energy microgrid optimizations."],
        "threats": ["Grid capacity headroom constraints."]
    }

    recommendations = ["Review spatial tracking parameters relative to regional advisory guidelines."]

    # --- PDF ENGINE RENDERING ---
    html_template = """
    <html>
    <body>
        <h1>Value4Farm Audit Assessment Report</h1>
        <hr/>
        <p>Location: {{ loc }}</p>
        <p>Overall Feasibility Indicator Status: {{ lights.overall }}</p>
        <p>Technical Aspect: {{ lights.technical }}</p>
        <p>Socio-Economic Aspect: {{ lights.socio_economic }}</p>
        <p>Social Aspect: {{ lights.social }}</p>
        <p>Environmental Aspect: {{ lights.environmental }}</p>
        <p>Agronomic Aspect: {{ lights.agronomic }}</p>
    </body>
    </html>
    """
    rendered_html = Template(html_template).render(loc=country, lights=status_lights, swot=swot, recommendations=recommendations)
    pdf_bytes = HTML(string=rendered_html).write_pdf()
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

    return {
        "scores": scores_raw,
        "lights": status_lights,
        "swot": swot,
        "recommendations": recommendations,
        "pdf": pdf_base64
    }
