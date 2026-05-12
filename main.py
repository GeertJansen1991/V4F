from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from weasyprint import HTML
from jinja2 import Template
import base64
from fastapi import FastAPI

app = FastAPI()

# This is crucial: it allows your frontend (running on a different port/file) to talk to this backend
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
    # We use .get() so if a field is empty, the server won't crash during demo
    focus = data.get("auditFocus", "Not specified")
    location = data.get("location", "Not specified")
    size = data.get("totalSize", 0)
    unit = data.get("unit", "Hectares")

    # 2. MOCK CALCULATION DATA (Placeholders for your supervisor)
    feasibility_scores = {
        "socio_economic": 85,
        "agronomic": 70,
        "environmental": 92,
        "technical": 65,
        "overall": 78
    }
    
    swot_analysis = {
        "strengths": ["Lorem ipsum dolor sit amet.", "Consectetur adipiscing elit.", "Sed do eiusmod tempor."],
        "weaknesses": ["Ut enim ad minim veniam.", "Quis nostrud exercitation.", "Ullamco laboris nisi."],
        "opportunities": ["Duis aute irure dolor.", "In reprehenderit in voluptate.", "Velit esse cillum dolore."],
        "threats": ["Excepteur sint occaecat.", "Cupidatat non proident.", "Sunt in culpa qui officia."]
    }
    
    recommendations = [
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris."
    ]

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
            
            /* Top Row: Summary & Overall Score */
            .top-container { width: 100%; margin-bottom: 20px; display: table; }
            .summary-box { display: table-cell; width: 60%; background: #FAFAFA; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
            .overall-box { display: table-cell; width: 35%; background: rgba(149, 193, 31, 0.1); border: 2px solid #95C11F; border-radius: 10px; text-align: center; vertical-align: middle; }
            .overall-score { color: #95C11F; font-size: 32pt; font-weight: bold; display: block; }
            
            /* 4 Column Row - Fixed for PDF alignment */
            .row { 
                width: 100%; 
                margin-bottom: 20px; 
                display: table; 
                border-collapse: separate; 
                border-spacing: 5px 0px; /* This creates the horizontal gap between boxes */
            }
            .col { 
                display: table-cell; 
                width: 25%; 
                background: white; 
                border: 1px solid #eee; 
                padding: 10px; 
                text-align: center; 
                border-radius: 8px; 
                vertical-align: top;
            }
            .col-label { font-size: 8pt; font-weight: bold; text-transform: uppercase; display: block; margin-bottom: 5px; }
            .col-val { color: #95C11F; font-size: 16pt; font-weight: bold; }

            /* SWOT Quadrants */
            .swot-grid { width: 100%; display: table; border-collapse: separate; border-spacing: 5px; }
            .swot-row { display: table-row; }
            .swot-cell { display: table-cell; width: 50%; border: 1px solid #eee; padding: 15px; border-radius: 10px; background: white; }
            .swot-title { font-weight: bold; font-size: 9pt; text-transform: uppercase; margin-bottom: 8px; display: block; }
            
            /* Bullet Styles */
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
    
    # Encode PDF to Base64 so it can be sent inside a JSON object
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

    # Return the data for the UI + the PDF for the download button
    return {
        "scores": feasibility_scores,
        "swot": swot_analysis,
        "recommendations": recommendations,
        "pdf": pdf_base64
    }

    # 5. RETURN THE PDF TO THE FRONTEND
    return Response(
        content=pdf_bytes, 
        media_type="application/pdf", 
        headers={"Content-Disposition": "attachment; filename=V4F_Audit_Report.pdf"}
    )