from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from weasyprint import HTML
from jinja2 import Template
import base64

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "V4F Backend is online!"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/generate-report")
async def generate_report(data: dict):
    # ==========================================
    # 1. EXTRACT DATA FROM FRONTEND
    # ==========================================
    focus = data.get("auditFocus", "Not specified")
    location = data.get("location", "Not specified")
    size = float(data.get("totalSize") or 0)
    unit = data.get("unit", "Hectares")
    
    # Extract structural sub-objects from Vue state
    agri = data.get("agrivoltaics", {})
    biogas = data.get("biogas", {})
    activities = data.get("activities", [])

    # ==========================================
    # 2. SIMPLE CONDITIONAL LOOKUP LOGIC
    # ==========================================
    # Set fallback baselines
    base_socio = 75
    base_agronomic = 75
    base_environmental = 75
    base_technical = 75

    swot_strengths = ["Anonymous local data compiled seamlessly."]
    swot_weaknesses = []
    swot_opportunities = ["Framework aligns with Value4Farm standard practices."]
    swot_threats = []
    recommendations = []

    # ----------- AGRIVOLTAICS EVALUATION -----------
    if focus in ["Agrivoltaics", "Both"]:
        terrain = agri.get("terrain")
        max_width = float(agri.get("maxWidth") or 0)
        max_height = float(agri.get("maxHeight") or 0)
        obstacles = agri.get("obstacles")

        # Technical Score & SWOT adjustments
        if terrain == "Flat":
            base_technical += 10
            swot_strengths.append("Flat terrain significantly reduces tracking system engineering costs.")
        elif terrain == "Hilly":
            base_technical -= 20
            swot_weaknesses.append("Steep/Hilly terrain increases structural loading and excavation costs.")
            recommendations.append("Conduct a professional civil engineering assessment to design anchor foundations for sloped terrain.")

        # Machinery constraints logic
        if max_width > 6.0 or max_height > 4.0:
            base_technical -= 10
            swot_threats.append("Large machinery dimensions risk hitting low-clearance racking infrastructure.")
            recommendations.append(f"Specify elevated tracking systems with a minimum clearance of {max_height + 0.5}m to accommodate your machinery.")
        else:
            swot_strengths.append("Standard farming machinery fits seamlessly within baseline row spacing specifications.")

        if obstacles == "Yes":
            base_technical -= 15
            swot_weaknesses.append("Known underground obstacles present drilling and structural placement challenges.")

        # Environmental & Agronomic adjustments
        if "I grow perennial crops (e.g., orchards, vineyards, berries)." in activities:
            base_agronomic += 15
            swot_opportunities.append("High synergy potential: Agri-PV structures can double as hail/frost protection nets for fruit variants.")
            recommendations.append("Investigate fixed-tilt overhead orchard configurations to maximize solar microclimate benefits.")
        else:
            recommendations.append("Consider tracker-based row layout matching standard arable width cycles.")

    # ----------- BIOGAS EVALUATION -----------
    if focus in ["Biogas", "Both"]:
        livestock = biogas.get("selectedLivestock", [])
        pathway = biogas.get("energy", {}).get("pathway")
        gas_grid = biogas.get("infrastructure", {}).get("gasGrid")
        herd_details = biogas.get("herdDetails", {})

        # Calculate rough animal stock baseline
        total_animals = 0
        has_pasture_risk = False
        for animal in livestock:
            details = herd_details.get(animal, {})
            total_animals += int(details.get("count") or 0)
            if details.get("housingMode") == "pasture":
                has_pasture_risk = True

        if len(livestock) > 0 and total_animals > 50:
            base_environmental += 15
            base_socio += 10
            swot_strengths.append(f"Substantial consistent slurry resource from your local livestock population ({total_animals} head count).")
        else:
            base_environmental -= 10
            swot_weaknesses.append("Low animal headcount baseline results in a heavy reliance on external feedstock dependencies.")

        if has_pasture_risk:
            base_technical -= 20
            swot_threats.append("Continuous open pasture tracking lowers the volume of collectible, fresh manure inputs.")
            recommendations.append("Optimize indoor transitional bedding collection schemes during the colder high-yield months.")

        # Pathway vs Grid logic
        if pathway == "Biomethane" and gas_grid == "No":
            base_technical -= 25
            swot_weaknesses.append("Biomethane upgrading target selected without a localized gas injection point.")
            recommendations.append("Pivot study focus toward On-site Combined Heat & Power (CHP) deployment loops, or look into local virtual pipeline transport solutions.")
        elif pathway == "CHP":
            swot_opportunities.append("CHP path allows for continuous local offset options for standard grid electrical costs.")

    # ----------- SCORE CONSTRAINT BOUNDS -----------
    # Keep final mock math scaled safely between 0% and 100%
    feasibility_scores = {
        "socio_economic": max(10, min(100, base_socio)),
        "agronomic": max(10, min(100, base_agronomic)),
        "environmental": max(10, min(100, base_environmental)),
        "technical": max(10, min(100, base_technical))
    }
    
    # Calculate overall weight average
    feasibility_scores["overall"] = int(sum(feasibility_scores.values()) / 4)

    # Clean empty lists defaults just in case
    if not recommendations:
        recommendations.append("Schedule a spatial engineering site verification with a Value4Farm coordinator.")

    # Add default fallbacks if lists are brief
    while len(swot_weaknesses) < 2: swot_weaknesses.append("Baseline project dependency checks pending step 3 transitions.")
    while len(swot_threats) < 2: swot_threats.append("Regulatory shifting limits require updated zoning reviews.")

    swot_analysis = {
        "strengths": swot_strengths[:3],
        "weaknesses": swot_weaknesses[:3],
        "opportunities": swot_opportunities[:3],
        "threats": swot_threats[:3]
    }

    # ==========================================
    # 3. DEFINE THE HTML TEMPLATE 
    # ==========================================
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

    # ==========================================
    # 4. RENDER HTML AND CONVERT TO PDF
    # ==========================================
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
