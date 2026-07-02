from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from weasyprint import HTML
from jinja2 import Template
import base64

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "V4F Backend is online!"}

# Crucial for frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/generate-report")
async def generate_report(data: dict):

    # 1. EXTRACT DATA FROM FRONTEND

    focus = data.get("auditFocus", "Not specified")
    location = data.get("location", "Not specified")
    size = float(data.get("totalSize") or 0)
    unit = data.get("unit", "Hectares")
    
    agri = data.get("agrivoltaics", {})
    biogas = data.get("biogas", {})
    activities = data.get("activities", [])

    base_socio = 80          
    base_agronomic = 75       
    base_environmental = 80   
    base_technical = 70       

    swot_strengths = []
    swot_weaknesses = []
    swot_opportunities = []
    swot_threats = []
    recommendations = []

    ownership = data.get("ownership")
    if ownership == "Own":
        swot_strengths.append("Secure Asset Control: Full land title allows for hassle-free long-term structural zoning and bankable underwriting.")
    else:
        base_socio -= 15
        swot_weaknesses.append("Contractual Bottleneck: Land lease or rental status limits long-term collateral asset assignment options.")
        swot_threats.append("Tenancy Expiry Friction: Lease timelines may not match typical 20-30 year infrastructure lifespans.")
        recommendations.append("Secure an immediate, long-term easement or surface rights extension with the landowner prior to technical applications.")

    #  AGRIVOLTAICS EVALUATION

    if focus in ["Agrivoltaics", "Both"]:
        selected_crops = agri.get("currentCrops", [])
        terrain = agri.get("terrain")
        slope_dir = agri.get("slopeDirection")
        max_width = float(agri.get("maxWidth") or 0)
        max_height = float(agri.get("maxHeight") or 0)
        obstacles = agri.get("obstacles")
        land_space = float(agri.get("landSpace") or 0)
        irrigation = agri.get("irrigation")
        water_source = agri.get("waterSource")
        

        if "I grow perennial crops (e.g., orchards, vineyards, berries)." in activities:
            base_agronomic += 15
            base_technical -= 5  
            swot_strengths.append("High Crop-PV Synergy: Perennial crops/berries benefit immensely from modular shade and microclimate tracking.")
            swot_opportunities.append("Premium APV Subsidies: High-clearance orchard systems qualify for top-tier European dual-use grants.")
            recommendations.append("Prioritize overhead, semi-transparent glass-glass solar configurations to maintain appropriate crop light levels.")
        elif "I grow arable field crops (e.g., grains, oilseeds, pulses)." in activities:
            base_agronomic -= 5  
            swot_strengths.append("Broadacre Flexibility: Large uniform plots simplify layout planning for standard row tracking configurations.")
            swot_opportunities.append("Large-Scale Generation: Wide rows allow high-capacity bifacial vertical arrays, maximizing peak pricing markets.")
            
            if any(c for c in selected_crops if "Root" in c or "Maize" in c):
                base_agronomic -= 10
                swot_weaknesses.append("Crop Light Deficit: Maize/Root crops have high light-saturation points and risk structural microclimate yield reduction.")
                recommendations.append("Utilize dynamic tracking algorithms that prioritize agricultural solar sharing during peak crop-growth phases.")

 
        if irrigation in ["Sprinkler", "Center Pivot"]:
            base_technical -= 10
            swot_weaknesses.append(f"Irrigation Collision Risk: Active {irrigation} frameworks require careful spatial coordination to prevent wetting module junctions.")
            swot_threats.append("Operational Overhead: High overhead tracking infrastructure is required to clear tall physical sprayers.")
            recommendations.append("Evaluate a sub-canopy transition to drip irrigation to enhance layout efficiency and water savings.")
        elif irrigation == "None":
            swot_opportunities.append("Microclimate Micro-saving: Reduced solar evaporation under panels can naturally optimize soil moisture tracking.")

        if water_source == "Public Supply":
            swot_threats.append("Resource Cost Vulnerability: High public water tariff rates degrade long-term agricultural operational margins under panels.")


        if max_width > 0:
            if max_width <= 4.5:
                base_technical += 10
                swot_strengths.append(f"Compact Operations: Machinery width ({max_width}m) matches optimized high-density row layouts.")
            elif max_width > 4.5 and max_width <= 9.0:
                swot_strengths.append(f"Standard Clearance: Row configuration fits integer multiples of your {max_width}m machine cycles.")
                recommendations.append(f"Design row interspaces at exactly {round(max_width + 0.8, 1)}m to maintain an operational safety margin.")
            else:
                base_technical -= 15
                swot_threats.append(f"Extreme Machine Footprint: Massive machinery width ({max_width}m) forces ultra-wide rows, reducing solar density.")
                recommendations.append("Evaluate whether a dedicated smaller tractor implement fleet is viable to protect target solar capacity.")

        if max_height > 0:
            if max_height >= 3.8:
                base_technical -= 15
                swot_weaknesses.append(f"Elevated Overhead Risk: High machinery clearance requirements ({max_height}m) demand heavy steel substructures, spiking CAPEX.")
                recommendations.append(f"Specify a minimum pile clearance height of {round(max_height + 0.5, 1)}m to eliminate field turnaround collision risks.")
            else:
                swot_strengths.append("Low Structural Profile: Standard height profile permits cost-effective, lower fixed pile assemblies.")


        if terrain == "Flat":
            base_technical += 10
            swot_strengths.append("Optimal Topography: Flat plots minimize grading requirements and ensure uniform tracking angles.")
        elif terrain == "Hilly":
            base_technical -= 20
            swot_weaknesses.append("Topographic Constraints: Slope variations (>10%) complicate mechanical single-axis tracker engineering.")
            recommendations.append("Deploy string-level maximum power point trackers (MPPT) to mitigate uneven hill shading patterns.")

        if slope_dir in ["South-facing", "East-West"]:
            base_technical += 10
            swot_strengths.append(f"Ideal Land Aspect: {slope_dir} orientation guarantees highly efficient production yield generation profiles.")
        elif slope_dir == "North-facing":
            base_technical -= 15
            swot_threats.append("Sub-optimal Microclimate: North-facing terrain coupled with panels risks creating over-chilled, damp crop conditions.")

        if obstacles == "Yes":
            base_technical -= 10
            swot_weaknesses.append("Subsurface Hazards: Documented underground obstructions mean ramming piles could damage infrastructure or fail depth tests.")
            recommendations.append("Budget for pre-drilling validation or concrete shoe foundations rather than direct structural pile-driving.")

        if land_space > 0:
            if land_space < 2.0:
                base_socio -= 10
                swot_weaknesses.append(f"Scaling Bottleneck: Small available area ({land_space} Ha) struggles to absorb fixed substation grid-entry costs.")
            elif land_space >= 10.0:
                base_socio += 15
                swot_opportunities.append(f"Utility-Scale Advantage: Large footprint opens up direct private Corporate Power Purchase Agreements (PPAs).")

    # BIOGAS EVALUATION

    if focus in ["Biogas", "Both"]:
        livestock = biogas.get("selectedLivestock", [])
        pathway = biogas.get("energy", {}).get("pathway")
        gas_grid = biogas.get("infrastructure", {}).get("gasGrid")
        herd_details = biogas.get("herdDetails", {})

        total_animals = 0
        has_pasture_risk = False
        for animal in livestock:
            details = herd_details.get(animal, {})
            total_animals += int(details.get("count") or 0)
            if details.get("housingMode") == "pasture":
                has_pasture_risk = True

        if len(livestock) > 0 and total_animals > 40:
            base_environmental += 15
            base_socio += 10
            swot_strengths.append(f"High Manure Asset Volumetrics: Local herd headcount ({total_animals}) secures a reliable, consistent biomethane supply.")
            swot_opportunities.append("Circular Economy Arbitrage: Capitalize on localized organic nutrient closed-loops, replacing chemical fertilizers.")
        else:
            base_environmental -= 10
            swot_weaknesses.append("Feedstock Limitation: Low on-site animal count limits continuous daily anaerobic organic loading capability.")

        if has_pasture_risk:
            base_threats.append("Manure Collection Deficit: Continuous open pasture modes drastically reduce total collectable slurry metrics.")
            recommendations.append("Optimize high-traffic transitional bedding capture mechanics during colder indoor-stabling months.")

        if pathway == "Biomethane":
            if gas_grid == "Yes":
                swot_opportunities.append("Direct Pipeline Connectivity: Proximity to regional networks unlocks premium biomethane injection tariffs.")
            else:
                base_technical -= 25
                swot_threats.append("Logistical Bottleneck: Lack of close gas grid infrastructure forces high virtual compressed trucking transport costs.")
                recommendations.append("Pivot technical focus toward local grid-tied Combined Heat & Power (CHP) generating systems.")
        elif pathway == "CHP":
            swot_opportunities.append("Thermal Offset Efficiency: Local cogeneration policies support direct district or process facility heating loops.")

    # CROSS-SYSTEM SYNERGY (Only triggers if user picks "Both")
    if focus == "Both":
        base_environmental += 10
        swot_opportunities.append("Integrated Microgrid Synergy: APV electrical production can directly power biogas digester auxiliary pumping tools.")
        recommendations.append("Incorporate a centralized battery storage system to buffer daytime solar spikes and power overnight anaerobic mixers.")

    # DYNAMIC FILLER (Ensures exactly 3 unique rows)
    backup_strengths = [
        "Data Sovereignty: Real-time calculation keeps internal farm metrics fully localized and anonymous.",
        "Systemic Versatility: Multi-criteria baseline aligns with Value4Farm framework research.",
        "Resource Baselines: Existing infrastructure supports clean structural transformation loops."
    ]
    backup_weaknesses = [
        "CapEx Inertia: High upfront development cost profiles require secondary investment validation.",
        "Grid Headroom Constraints: Local network connection capacities require formal verification.",
        "Zoning Friction: Transitioning agricultural plots to dual-use requires municipal structural authorization."
    ]
    backup_opportunities = [
        "Carbon Offset Valuation: Earn regional ecosystem credits via dual-use land execution.",
        "Energy Independence: Stabilize localized operational buffers against volatile utility markets.",
        "Decarbonization Subsidies: Unlock targeted EU sustainable agricultural transition funds."
    ]
    backup_threats = [
        "Regulatory Volatility: Shifts in agricultural cross-compliance tracking parameters could impact targets.",
        "Climatic Variances: Sudden extreme weather trends affect historical solar irradiation projections.",
        "Market Tariff Shifts: Unpredictable changes in feed-in pricing rules change expected ROI curves."
    ]

    for item in backup_strengths:
        if len(swot_strengths) >= 3: break
        if item not in swot_strengths: swot_strengths.append(item)

    for item in backup_weaknesses:
        if len(swot_weaknesses) >= 3: break
        if item not in swot_weaknesses: swot_weaknesses.append(item)

    for item in backup_opportunities:
        if len(swot_opportunities) >= 3: break
        if item not in swot_opportunities: swot_opportunities.append(item)

    for item in backup_threats:
        if len(swot_threats) >= 3: break
        if item not in swot_threats: swot_threats.append(item)

    if not recommendations: 
        recommendations.append("Initiate a preliminary site coordination brief with a Value4Farm advisory team member.")

    # Keep scores strictly bounded between 15% and 100%
    feasibility_scores = {
        "socio_economic": max(15, min(100, base_socio)),
        "agronomic": max(15, min(100, base_agronomic)),
        "environmental": max(15, min(100, base_environmental)),
        "technical": max(15, min(100, base_technical))
    }
    feasibility_scores["overall"] = int(sum(feasibility_scores.values()) / 4)

    swot_analysis = {
        "strengths": swot_strengths[:3],
        "weaknesses": swot_weaknesses[:3],
        "opportunities": swot_opportunities[:3],
        "threats": swot_threats[:3]
    }

    # 3. DEFINE THE HTML TEMPLATE 
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page { size: A4; margin: 1.5cm; }
            body { font-family: 'Helvetica', sans-serif; color: #74776A; line-height: 1.4; }
            h1 { color: #95C11F; margin-bottom: 5px; }
            .header-line { border-bottom: 2px solid #95C11F; margin-bottom: 20px; }
            
            .top-container { width: 100%; margin-bottom: 20px; display: table; }
            .summary-box { display: table-cell; width: 60%; background: #FAFAFA; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
            .overall-box { display: table-cell; width: 35%; background: rgba(149, 193, 31, 0.1); border: 2px solid #95C11F; border-radius: 10px; text-align: center; vertical-align: middle; }
            .overall-score { color: #95C11F; font-size: 32pt; font-weight: bold; display: block; }
            
            .row { width: 100%; margin-bottom: 20px; display: table; border-collapse: separate; border-spacing: 5px 0px; }
            .col { display: table-cell; width: 25%; background: white; border: 1px solid #eee; padding: 10px; text-align: center; border-radius: 8px; vertical-align: top;}
            .col-label { font-size: 8pt; font-weight: bold; text-transform: uppercase; display: block; margin-bottom: 5px; }
            .col-val { color: #95C11F; font-size: 16pt; font-weight: bold; }

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
        <h1>Value4Farm Audit Report</h1>
        <div class="header-line"></div>
        
        <div class="top-container">
            <div class="summary-box">
                <p><strong>Farm Location:</strong> {{ loc }}</p>
                <p><strong>Audit Focus:</strong> {{ focus }}</p>
                <p><strong>Total Size:</strong> {{ size }} {{ unit }}</p>
            </div>
            <div class="overall-box">
                <span style="font-size: 9pt; font-weight: bold; text-transform: uppercase;">Overall Feasibility</span><br>
                <span class="overall-score">{{ scores.overall }}%</span>
            </div>
        </div>

        <div class="row">
            <div class="col"><span class="col-label">Socio-Economic</span><span class="col-val">{{ scores.socio_economic }}%</span></div>
            <div class="col"><span class="col-label">Agronomic</span><span class="col-val">{{ scores.agronomic }}%</span></div>
            <div class="col"><span class="col-label">Environmental</span><span class="col-val">{{ scores.environmental }}%</span></div>
            <div class="col" style="margin-right: 0;"><span class="col-label">Technical</span><span class="col-val">{{ scores.technical }}%</span></div>
        </div>

        <h3>SWOT Analysis</h3>
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

    # 4. RENDER HTML AND CONVERT TO PDF
    template = Template(html_template)
    rendered_html = template.render(
        loc=location,
        size=size,
        unit=unit,
        focus=focus,
        scores=feasibility_scores,
        swot=swot_analysis,
        recommendations=recommendations
    )
    
    pdf_bytes = HTML(string=rendered_html).write_pdf()
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

    return {
        "scores": feasibility_scores,
        "swot": swot_analysis,
        "recommendations": recommendations,
        "pdf": pdf_base64
    }
