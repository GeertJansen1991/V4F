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

# Global placeholders for startup caching
df_main, df_cro_yld, df_wat_dem = None, None, None
bbn_model = None

@app.on_event("startup")
def initialize_system():
    """Caches Excel matrices and initializes the network graph structure once on server boot."""
    global df_main, df_cro_yld, df_wat_dem, bbn_model
    
    if not os.path.exists(EXCEL_PATH):
        raise FileNotFoundError(f"Missing database dependency asset: {EXCEL_PATH}")
        
    df_main = pd.read_excel(EXCEL_PATH, sheet_name='APV_Main')
    df_cro_yld = pd.read_excel(EXCEL_PATH, sheet_name='APV_Cro_Yld')
    df_wat_dem = pd.read_excel(EXCEL_PATH, sheet_name='APV_Wat_Dem')
    
    # Instantiate the network configuration graph
    model = DiscreteBayesianNetwork([
        ('APV_Pol', 'Governance'), ('APV_Per', 'Governance'), ('APV_Sub', 'Governance'), ('APV_Rev', 'Governance'),
        ('Governance', 'Technical_Feasibility'), ('Energy_Potential', 'Technical_Feasibility'),
        ('Economic_Potential', 'Economic_Feasibility'), ('APV_Rev', 'Economic_Feasibility'),
        ('Visual_Impact', 'Social_Feasibility'),
        ('Crop_Yield_Impact', 'Agronomic_Feasibility'), ('Water_Demand_Impact', 'Agronomic_Feasibility'), ('Machinery_Compatibility', 'Agronomic_Feasibility'),
        ('Environmental_Potential', 'Environmental_Feasibility'),
        
        # Integration parameters
        ('Technical_Feasibility', 'Overall_Feasibility'),
        ('Economic_Feasibility', 'Overall_Feasibility'),
        ('Social_Feasibility', 'Overall_Feasibility'),
        ('Agronomic_Feasibility', 'Overall_Feasibility'),
        ('Environmental_Feasibility', 'Overall_Feasibility'),
        ('Land_Ownership', 'Overall_Feasibility'),
        ('Successor_Planning', 'Overall_Feasibility')
    ])

    # Assign core static distribution states
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

    # Build conditional probability tables dynamically
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

    model.add_cpds(cpd_pol, cpd_per, cpd_sub, cpd_rev, cpd_ene, cpd_eco, cpd_vis, cpd_cyi, cpd_wdi, cpd_mac, cpd_env, cpd_own, cpd_suc,
                   cpd_gov, cpd_tech, cpd_eco_feas, cpd_soc_feas, cpd_agro_feas, cpd_env_feas, cpd_overall)
    model.check_model()
    bbn_model = model

@app.post("/generate-report")
async def generate_report(data: dict):
    # Safe Extraction of Vue Frontend Payload Structures
    country = data.get("location", "Austria")
    ownership = data.get("ownership", "Own")
    continuity = data.get("continuity", "")
    
    agri = data.get("agrivoltaics", {})
    available_ha = float(agri.get("landSpace") or 2.5)
    machinery_height = float(agri.get("maxHeight") or 2.2)
    crops_list = agri.get("currentCrops", [])
    crop_choice = crops_list[0] if crops_list else "Cereals"
    
    resources = data.get("resources", {})
    user_electricity_usage = float(resources.get("electricity", {}).get("value") or 50000)

    # Database matching checks
    country_row = df_main[df_main['Country'].str.lower() == country.lower()]
    if country_row.empty:
        raise HTTPException(status_code=400, detail=f"Country '{country}' not found in configuration matrix.")

    evidence = {}
    
    # 1. GOVERNANCE EVIDENCE MAP
    state_map = {"Negative": 0, "Neutral": 1, "Positive": 2}
    evidence['APV_Pol'] = state_map.get(country_row['APV_Pol'].values[0], 1)
    evidence['APV_Per'] = state_map.get(country_row['APV_Per'].values[0], 1)
    evidence['APV_Sub'] = state_map.get(country_row['APV_Sub'].values[0], 1)
    evidence['APV_Rev'] = state_map.get(country_row['APV_Rev'].values[0], 1)

    # 2. CLIMATE PROFILE DISCRETIZATION
    capacity_factor_raw = float(country_row['APV_Cap_Fac'].values[0])
    if capacity_factor_raw < 12.0: climate_column = "Climate 1 (<750 W/m²)"
    elif 12.0 <= capacity_factor_raw < 14.5: climate_column = "Climate 2 (750–1099 W/m²)"
    elif 14.5 <= capacity_factor_raw < 16.5: climate_column = "Climate 3 (1100–1749 W/m²)"
    else: climate_column = "Climate 4 (>1750 W/m²)"

    # 3. TECHNICAL ENERGY PREDICTIONS
    installed_capacity_kwp = (available_ha * 10000) * 0.22 * 0.6
    annual_energy_production_kwh = installed_capacity_kwp * 8760 * (capacity_factor_raw / 100.0)
    specific_yield = annual_energy_production_kwh / installed_capacity_kwp if installed_capacity_kwp > 0 else 0
    evidence['Energy_Potential'] = 0 if specific_yield < 1000 else (1 if specific_yield < 1400 else 2)

    # 4. ECONOMIC RETURNING RATIOS
    lifecycle_cost = installed_capacity_kwp * 1000 * 1.125
    actual_kwh_offset = min(annual_energy_production_kwh * 0.80, user_electricity_usage)
    electricity_price_kwh = float(country_row['Ele_Cos'].values[0]) / 100
    lifecycle_savings = actual_kwh_offset * electricity_price_kwh * 25
    roi = ((lifecycle_savings - lifecycle_cost) / lifecycle_cost) * 100 if lifecycle_cost > 0 else 0
    evidence['Economic_Potential'] = 0 if roi < -25 else (1 if roi < 50 else 2)

    # 5. SOCIAL PROFILE IMPRESSION INDEX
    evidence['Visual_Impact'] = min(4, int(available_ha // 2))

    # 6. AGRONOMIC CONSTRAINTS MATCHING
    crop_match = df_cro_yld[df_cro_yld['Crop Category'].str.lower().str.contains(crop_choice.lower()[:5])]
    raw_yield_impact = crop_match[climate_column].values[0] if not crop_match.empty else "Neutral"
    raw_water_impact = df_wat_dem[climate_column].values[0]
    
    descriptor_map = {"Negative": 0, "Slightly Negative": 0, "Neutral": 1, "Slightly Positive": 2, "Positive": 2, "Very positive": 2}
    evidence['Crop_Yield_Impact'] = descriptor_map.get(raw_yield_impact, 1)
    evidence['Water_Demand_Impact'] = descriptor_map.get(raw_water_impact, 1)
    evidence['Machinery_Compatibility'] = 2 if machinery_height < 2.0 else (1 if machinery_height <= 2.5 else 0)

    # 7. ENVIRONMENTAL FOOTPRINT ADJUSTMENTS
    net_impact = ((annual_energy_production_kwh * 20.0) - (actual_kwh_offset * float(country_row['Gri_Car'].values[0]))) / annual_energy_production_kwh
    evidence['Environmental_Potential'] = 0 if net_impact > 10.0 else (1 if -10.0 <= net_impact <= 10.0 else 2)

    # 8. STRUCTURAL LAND TIMELINES
    evidence['Land_Ownership'] = 2 if ownership == "Own" else (1 if "Share" in ownership or "Lease" in ownership else 0)
    evidence['Successor_Planning'] = 2 if "confirmed" in continuity.lower() or "formal" in continuity.lower() else 1

    # --- INFERENCE BBN GRAPH COMPUTING ENGINE ---
    inference = VariableElimination(bbn_model)
    tech = inference.query(variables=['Technical_Feasibility'], evidence=evidence)
    eco = inference.query(variables=['Economic_Feasibility'], evidence=evidence)
    soc = inference.query(variables=['Social_Feasibility'], evidence=evidence)
    agro = inference.query(variables=['Agronomic_Feasibility'], evidence=evidence)
    env = inference.query(variables=['Environmental_Feasibility'], evidence=evidence)
    overall = inference.query(variables=['Overall_Feasibility'], evidence=evidence)

    # Standardize output percentages
    scores_raw = {
        "overall": int(overall.values[2] * 100),
        "technical": int(tech.values[2] * 100),
        "economic": int(eco.values[2] * 100),
        "socio_economic": int(eco.values[2] * 100),
        "social": int(soc.values[2] * 100),
        "agronomic": int(agro.values[2] * 100),
        "environmental": int(env.values[2] * 100)
    }

    # Helper function to assign traffic light colors based on score thresholds
    def get_light(score):
        if score < 40: return "🔴"
        elif score > 70: return "🟢"
        return "🟡"

    status_lights = {k: get_light(v) for k, v in scores_raw.items()}

    # --- DYNAMIC SWOT LOGIC ---
    swot_strengths = [
        f"High Local Solar Density footprint matching a calculated system sizing scale of {round(installed_capacity_kwp, 1)} kWp.",
        "Strong institutional alignment observed relative to national agricultural structural agendas."
    ]
    swot_weaknesses = [
        f"Machinery spatial adjustments needed for operations above {machinery_height} meters.",
        "Longer capital amortization terms based on specific local grid utility structures."
    ]

    # 1. Dynamic Environmental SWOT Placement
    if net_impact < -10.0:
        swot_strengths.append("Significant greenhouse gas savings expected due to high carbon offset potential relative to your local electricity grid.")
    elif -10.0 <= net_impact <= 10.0:
        swot_strengths.append("Moderate environmental profile, introducing stable ecological lifecycle offsets.")
    else:
        swot_weaknesses.append("Agrivoltaics is unlikely to give considerable greenhouse gas savings compared to your highly decarbonized local electricity grid.")

    # 2. Dynamic Economic SWOT Placement
    if roi > 50:
        swot_strengths.append("Strong business case: The assessment demonstrates a highly positive long-term economic outcome.")
    elif -25 <= roi <= 50:
        swot_strengths.append("Neutral economic outlook: Stable baseline returns projected with standard amortization profiles.")
    else:
        swot_weaknesses.append("Constrained metrics: Project shows a likely not positive economic outcome under current tariff conditions.")

    swot = {
        "strengths": swot_strengths,
        "weaknesses": swot_weaknesses,
        "opportunities": [
            "Integrated Microgrid Synergy: Stabilizing operational margins against structural utility rate variations.",
            "Dual land-use optimization allowing shared yield preservation under fluctuating solar weather patterns."
        ],
        "threats": [
            "Zoning Policy friction risks depending on evolving municipal network compliance frameworks.",
            "Interconnection scheduling volatility during peak structural grid connection updates."
        ]
    }

    recommendations = [
        "Prioritize semi-transparent tracking module positions to optimize under-canopy crop light metrics.",
        "Assess utility sub-station distances to minimize balance-of-system cost overruns.",
        "Initiate a formal structural review of local dual-use zoning guidelines before capital assignment."
    ]

    # --- EMBEDDED DYNAMIC HTML-TO-PDF STRUCTURAL ENGINE ---
    html_template = """
    <html>
    <head>
        <style>
            @page { size: A4; margin: 1.5cm; }
            body { font-family: 'Helvetica', sans-serif; color: #74776A; line-height: 1.4; }
            h1 { color: #95C11F; margin-bottom: 5px; }
            .header-line { border-bottom: 2px solid #95C11F; margin-bottom: 20px; }
            .top-container { width: 100%; margin-bottom: 20px; display: table; }
            .summary-box { display: table-cell; width: 60%; background: #FAFAFA; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
            .overall-box { display: table-cell; width: 35%; background: rgba(149, 193, 31, 0.1); border: 2px solid #95C11F; border-radius: 10px; text-align: center; vertical-align: middle; padding: 10px; }
            .overall-light { font-size: 36pt; display: block; margin-top: 5px; }
            .row { width: 100%; margin-bottom: 20px; display: table; border-collapse: separate; border-spacing: 5px 0px; }
            .col { display: table-cell; width: 25%; background: white; border: 1px solid #eee; padding: 15px; text-align: center; border-radius: 8px; vertical-align: top;}
            .col-label { font-size: 8pt; font-weight: bold; text-transform: uppercase; display: block; margin-bottom: 8px; }
            .col-light { font-size: 22pt; display: block; }
            .swot-grid { width: 100%; display: table; border-collapse: separate; border-spacing: 5px; }
            .swot-row { display: table-row; }
            .swot-cell { display: table-cell; width: 50%; border: 1px solid #eee; padding: 15px; border-radius: 10px; background: white; }
            .swot-title { font-weight: bold; font-size: 9pt; text-transform: uppercase; margin-bottom: 8px; display: block; }
            .bullet { color: #F9B333; font-weight: bold; margin-right: 5px; }
            .swot-list { list-style: none; padding: 0; margin: 0; font-size: 9pt; font-style: italic; }
            .rec-list { list-style: none; padding: 0; margin-top: 10px; }
            .rec-item { margin-bottom: 8px; font-size: 10pt; }
        </style>
    </head>
    <body>
        <h1>Value4Farm Audit Assessment Report</h1>
        <div class="header-line"></div>
        
        <div class="top-container">
            <div class="summary-box">
                <p><strong>Farm Location:</strong> {{ loc }}</p>
                <p><strong>Calculated System Size:</strong> {{ system_size }} kWp</p>
                <p><strong>Analyzed Plot Target Space:</strong> {{ size }} Hectares</p>
            </div>
            <div class="overall-box">
                <span style="font-size: 8pt; font-weight: bold; text-transform: uppercase; color: #74776A;">Overall Feasibility</span><br>
                <span class="overall-light">{{ lights.overall }}</span>
            </div>
        </div>

        <div class="row">
            <div class="col"><span class="col-label">Socio-Economic</span><span class="col-light">{{ lights.socio_economic }}</span></div>
            <div class="col"><span class="col-label">Agronomic</span><span class="col-light">{{ lights.agronomic }}</span></div>
            <div class="col"><span class="col-label">Environmental</span><span class="col-light">{{ lights.environmental }}</span></div>
            <div class="col"><span class="col-label">Technical</span><span class="col-light">{{ lights.technical }}</span></div>
        </div>

        <h3>BBN SWOT Framework Analysis</h3>
        <div class="swot-grid">
            <div class="swot-row">
                <div class="swot-cell">
                    <span class="swot-title" style="color: #10b981;">● Strengths</span>
                    <ul class="swot-list">{% for item in swot.strengths %}<li><span class="bullet">▶</span> {{ item }}</li>{% endfor %}</ul>
                </div>
                <div class="swot-cell">
                    <span class="swot-title" style="color: #f43f5e;">● Weaknesses</span>
                    <ul class="swot-list">{% for item in swot.weaknesses %}<li><span class="bullet">▶</span> {{ item }}</li>{% endfor %}</ul>
                </div>
            </div>
            <div class="swot-row">
                <div class="swot-cell">
                    <span class="swot-title" style="color: #F9B333;">● Opportunities</span>
                    <ul class="swot-list">{% for item in swot.opportunities %}<li><span class="bullet">▶</span> {{ item }}</li>{% endfor %}</ul>
                </div>
                <div class="swot-cell">
                    <span class="swot-title" style="color: #94a3b8;">● Threats</span>
                    <ul class="swot-list">{% for item in swot.threats %}<li><span class="bullet">▶</span> {{ item }}</li>{% endfor %}</ul>
                </div>
            </div>
        </div>

        <h3>Recommendations</h3>
        <ul class="rec-list">
            {% for rec in recommendations %}
            <li class="rec-item"><span class="bullet">▶</span> {{ rec }}</li>
            {% endfor %}
        </ul>
    </body>
    </html>
    """
    
    rendered_html = Template(html_template).render(
        loc=country, 
        size=available_ha,
        system_size=round(installed_capacity_kwp, 1),
        lights=status_lights,
        swot=swot,
        recommendations=recommendations
    )
    
    pdf_bytes = HTML(string=rendered_html).write_pdf()
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

    return {
        "scores": scores_raw,
        "lights": status_lights,
        "swot": swot,
        "recommendations": recommendations,
        "pdf": pdf_base64
    }
