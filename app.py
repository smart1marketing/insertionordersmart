import json
import threading
from datetime import datetime, timezone
import os
import logging
from pathlib import Path
from flask import Flask, jsonify, render_template, request
import cloudinary
import cloudinary.utils
import cloudinary.uploader
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv

from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak, KeepTogether
from reportlab.lib.utils import ImageReader
from xml.sax.saxutils import escape as xml_escape

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(BASE_DIR / 'templates'))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set CLOUDINARY_URL in the environment. Never place the API secret in browser JavaScript.
cloudinary.config(secure=True)

@app.get('/health')
def health():
    template_path = BASE_DIR / 'templates' / 'index.html'
    return jsonify({
        'status': 'ok',
        'template_exists': template_path.exists(),
        'template_path': str(template_path),
        'cloudinary_configured': bool(os.getenv('CLOUDINARY_URL')),
        'brandfetch_configured': bool(os.getenv('BRANDFETCH_API_KEY')),
        'openai_configured': bool(os.getenv('OPENAI_API_KEY')),
    })

@app.get('/')
def index():
    template_path = BASE_DIR / 'templates' / 'index.html'
    if not template_path.exists():
        logger.error('Missing template: %s', template_path)
        return (
            'SMART1 Campaign Builder deployment is missing templates/index.html. '
            'Upload the templates folder beside app.py and leave Render Root Directory blank.',
            500,
        )
    return render_template('index.html')

@app.get('/api/cloudinary-config')
def cloudinary_config():
    cfg = cloudinary.config()
    if not cfg.cloud_name or not cfg.api_key or not cfg.api_secret:
        return jsonify({'error': 'Cloudinary is not configured'}), 503
    return jsonify({'cloud_name': cfg.cloud_name})



def _extract_brandfetch(payload, requested_domain):
    logos = payload.get('logos') or []
    logo_url = ''
    for logo in logos:
        for fmt in (logo.get('formats') or []):
            src = fmt.get('src')
            if src:
                logo_url = src
                break
        if logo_url:
            break
    colors = []
    for color in payload.get('colors') or []:
        value = color.get('hex') or color.get('value')
        if value and value not in colors:
            colors.append(value)
    fonts = []
    for font in payload.get('fonts') or []:
        name = font.get('name') or font.get('family')
        if name and name not in fonts:
            fonts.append(name)
    links = []
    for link in payload.get('links') or []:
        if isinstance(link, dict):
            links.append({'name': link.get('name') or link.get('type') or '', 'url': link.get('url') or ''})
        elif isinstance(link, str):
            links.append({'name': '', 'url': link})
    company = payload.get('company') or {}
    return {
        'status': 'loaded',
        'name': payload.get('name') or company.get('name') or '',
        'domain': payload.get('domain') or requested_domain,
        'description': payload.get('description') or company.get('description') or '',
        'logo': logo_url,
        'colors': colors[:12],
        'fonts': fonts[:12],
        'links': links[:20],
        'company': company,
        'brand_id': payload.get('id') or '',
        'claimed': payload.get('claimed'),
        'quality_score': payload.get('qualityScore') or payload.get('quality_score'),
    }

@app.get('/api/brandfetch')
def brandfetch_lookup():
    api_key = os.getenv('BRANDFETCH_API_KEY', '').strip()
    client_id = os.getenv('BRANDFETCH_CLIENT_ID', '').strip()
    if not api_key:
        return jsonify({'error': 'Brandfetch is not configured'}), 503
    domain = (request.args.get('domain') or '').strip().lower()
    if '://' in domain:
        domain = urlparse(domain).hostname or ''
    domain = domain.removeprefix('www.').split('/')[0]
    if not domain or '.' not in domain:
        return jsonify({'error': 'A valid website domain is required'}), 400
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    if client_id:
        headers['X-Client-Id'] = client_id
    try:
        response = requests.get(f'https://api.brandfetch.io/v2/brands/domain/{domain}', headers=headers, timeout=20)
        if response.status_code == 404:
            return jsonify({'error': f'No Brandfetch profile was found for {domain}'}), 404
        response.raise_for_status()
        return jsonify(_extract_brandfetch(response.json(), domain))
    except requests.RequestException as exc:
        detail = ''
        if getattr(exc, 'response', None) is not None:
            detail = (exc.response.text or '')[:300]
        return jsonify({'error': 'Brandfetch request failed', 'detail': detail}), 502


@app.post('/api/generate-business-description')
def generate_business_description():
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    if not api_key:
        return jsonify({'error': 'OpenAI is not configured. Add OPENAI_API_KEY in Render.'}), 503
    data = request.get_json(force=True) or {}
    urls = [str(u).strip() for u in (data.get('urls') or []) if str(u).strip()]
    if not urls:
        return jsonify({'error': 'At least one website URL is required'}), 400
    client = str(data.get('client') or '').strip()
    industry = str(data.get('industry') or '').strip()
    geography = str(data.get('geo') or '').strip()
    brand = data.get('brandfetch') or {}
    prompt = (
        'Research the business using these official website URLs: ' + ', '.join(urls) + '.\n'
        'Write a concise, client-ready business description for a digital media insertion order.\n'
        'Use 2 to 4 sentences and plain language. Explain what the business does, its main products or services, who it serves, and its geographic focus when supported by the website.\n'
        'Do not invent awards, years in business, locations, claims, or services. Do not include citations or URLs in the final description.\n'
        f'Known intake details:\nClient name: {client}\nIndustry: {industry}\nGeographic target: {geography}\n'
        f'Brandfetch description: {brand.get("description", "") if isinstance(brand, dict) else ""}\n'
        'Return only the finished description.'
    )
    payload = {
        'model': os.getenv('OPENAI_MODEL', 'gpt-5-mini'),
        'input': prompt,
        'tools': [{'type': 'web_search'}],
    }
    try:
        response = requests.post(
            'https://api.openai.com/v1/responses',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        parts = []
        for item in result.get('output') or []:
            for content in item.get('content') or []:
                if content.get('type') in ('output_text', 'text') and content.get('text'):
                    parts.append(content['text'])
        description = '\n'.join(parts).strip()
        if not description:
            return jsonify({'error': 'OpenAI returned no description'}), 502
        return jsonify({'description': description})
    except requests.RequestException as exc:
        detail = ''
        if getattr(exc, 'response', None) is not None:
            detail = (exc.response.text or '')[:500]
        return jsonify({'error': 'OpenAI description request failed', 'detail': detail}), 502

@app.post('/api/cloudinary-signature')
def cloudinary_signature():
    cfg = cloudinary.config()
    if not cfg.cloud_name or not cfg.api_key or not cfg.api_secret:
        return jsonify({'error': 'Cloudinary is not configured'}), 503
    data = request.get_json(force=True) or {}
    allowed = {'timestamp', 'folder', 'tags', 'context'}
    params = {k: data[k] for k in allowed if k in data and data[k] not in (None, '')}
    if 'timestamp' not in params:
        return jsonify({'error': 'timestamp is required'}), 400
    signature = cloudinary.utils.api_sign_request(params, cfg.api_secret)
    return jsonify({'signature': signature, 'api_key': cfg.api_key, 'cloud_name': cfg.cloud_name})




_ORDER_LOCK = threading.Lock()

def _order_counter_path():
    return Path(os.environ.get("ORDER_COUNTER_FILE", "/var/data/smart1_order_counter.json"))

def _next_order_number():
    """Return the next persistent order number, starting with 10200."""
    path = _order_counter_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _ORDER_LOCK:
        current = 10199
        if path.exists():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
                current = int(stored.get("last_order_number", current))
            except Exception:
                logger.exception("Unable to read order counter; using starting value")
        next_number = current + 1
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps({"last_order_number": next_number}), encoding="utf-8")
        temp.replace(path)
        return str(next_number)

@app.post("/api/next-order-number")
def next_order_number():
    try:
        return jsonify({"ok": True, "order_number": _next_order_number()})
    except Exception as exc:
        logger.exception("Order number allocation failed")
        return jsonify({"ok": False, "error": str(exc)}), 500

def _safe_filename(value):
    cleaned = ''.join(ch if ch.isalnum() or ch in (' ', '-', '_') else ' ' for ch in str(value or '')).strip()
    return ' '.join(cleaned.split()) or 'Client'


def _fetch_image_bytes(url):
    if not url:
        return None
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return BytesIO(r.content)
    except Exception:
        return None


def _p(text, style):
    return Paragraph(xml_escape(str(text or '')).replace('\n', '<br/>'), style)


def _build_requirements_pdf(data, doc_type):
    client = _safe_filename(data.get('client'))
    order_number = _safe_filename(data.get('orderNumber') or 'No Order')
    title = f'S1M Internal - {order_number} - {client}' if doc_type == 'internal' else f'S1M - {order_number} - {client}'
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=0.5*inch, leftMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch, title=title)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='S1Title', parent=styles['Title'], textColor=colors.HexColor('#14284b'), fontSize=20, leading=24, spaceAfter=12))
    styles.add(ParagraphStyle(name='S1H2', parent=styles['Heading2'], textColor=colors.HexColor('#14284b'), fontSize=13, leading=16, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name='S1Body', parent=styles['BodyText'], fontSize=9, leading=12, spaceAfter=5))
    styles.add(ParagraphStyle(name='S1Small', parent=styles['BodyText'], fontSize=7.5, leading=9.5, textColor=colors.HexColor('#53657a')))
    story=[Paragraph(xml_escape(title), styles['S1Title'])]
    story.append(_p('Campaign and Product Requirements', styles['S1Body']))
    meta=[
        ['Order Number', data.get('orderNumber','')],
        ['Smart 1 Contact', f"{data.get('salesContact','')} - {data.get('salesEmail','')}"],
        ['Business Website', data.get('url','')],
        ['Campaign Dates', f"{data.get('start','')} to {data.get('end','')}" if data.get('sameDates') else 'Dates vary by product'],
        ['Creative', data.get('creativeSource','To be confirmed')],
        ['Monthly Spend', data.get('monthlySpendFormatted','')],
        ['Total Campaign Budget', data.get('totalCampaignBudgetFormatted','')],
    ]
    t=Table(meta, colWidths=[1.45*inch, 5.55*inch])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#eef3f8')),('TEXTCOLOR',(0,0),(0,-1),colors.HexColor('#14284b')),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#d5dee9')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story += [t, Spacer(1,10)]

    # Brandfetch section near beginning
    b=data.get('brandfetch') or {}
    if any([b.get('name'), b.get('description'), b.get('logo'), b.get('colors'), b.get('links')]):
        story.append(Paragraph('Brand Information', styles['S1H2']))
        brand_rows=[]
        logo_flow=''
        logo_bytes=_fetch_image_bytes(b.get('logo'))
        if logo_bytes:
            try:
                img=RLImage(logo_bytes, width=1.2*inch, height=0.8*inch, kind='proportional')
                logo_flow=[img, Paragraph(f'<link href="{xml_escape(b.get('logo'))}">Open full logo</link>', styles['S1Small'])]
            except Exception:
                logo_flow=_p(b.get('logo'), styles['S1Small'])
        elif b.get('logo'):
            logo_flow=_p(b.get('logo'), styles['S1Small'])
        if logo_flow: brand_rows.append(['Logo', logo_flow])
        if b.get('name'): brand_rows.append(['Brand Name', _p(b.get('name'), styles['S1Body'])])
        if b.get('domain'): brand_rows.append(['Domain', _p(b.get('domain'), styles['S1Body'])])
        if b.get('description'): brand_rows.append(['Description', _p(b.get('description'), styles['S1Body'])])
        cols=[]
        for c in b.get('colors') or []:
            try:
                sw=Table([['']], colWidths=[0.18*inch], rowHeights=[0.18*inch]); sw.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),colors.HexColor(c)),('BOX',(0,0),(0,0),0.5,colors.grey)]))
                cols.append([sw, _p(c, styles['S1Small'])])
            except Exception:
                cols.append([_p(c, styles['S1Small'])])
        if cols:
            color_table=Table(cols, colWidths=[0.6*inch]*len(cols))
            color_table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER')]))
            brand_rows.append(['Colors', color_table])
        if b.get('fonts'): brand_rows.append(['Fonts', _p(', '.join(b.get('fonts') or []), styles['S1Body'])])
        links=[]
        for link in b.get('links') or []:
            if isinstance(link, dict):
                url=link.get('url',''); name=link.get('name') or url
            else: url=str(link); name=url
            if url: links.append(f'<link href="{xml_escape(url)}">{xml_escape(name)}</link>')
        if links: brand_rows.append(['Brand Links', Paragraph('<br/>'.join(links), styles['S1Small'])])
        bt=Table(brand_rows, colWidths=[1.1*inch,5.9*inch])
        bt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#d5dee9')),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#f3f6f9')),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        story += [bt, Spacer(1,10)]

    # Uploaded creative section with thumbnails
    assets=data.get('creativeAssets') or []
    if assets:
        story.append(Paragraph('Creative Assets', styles['S1H2']))
        rows=[['Preview','Product','File / Status','Evergreen','Asset Link']]
        for a in assets:
            preview='-'
            url=a.get('url','')
            rtype=(a.get('resourceType') or '').lower()
            fname=(a.get('fileName') or '').lower()
            if url and (rtype=='image' or fname.endswith(('.jpg','.jpeg','.png','.gif','.webp'))):
                ib=_fetch_image_bytes(url)
                if ib:
                    try: preview=RLImage(ib,width=0.65*inch,height=0.5*inch,kind='proportional')
                    except Exception: preview='Image'
            link=Paragraph(f'<link href="{xml_escape(url)}">Open asset</link>' if url else '-', styles['S1Small'])
            product=a.get('productLabel') or a.get('product') or ''
            rows.append([preview,_p(product,styles['S1Small']),_p(f"{a.get('fileName','')}\n{a.get('status','')}",styles['S1Small']),_p('Yes' if a.get('evergreen') else 'No',styles['S1Small']),link])
        at=Table(rows,colWidths=[0.65*inch,1.45*inch,2.25*inch,0.65*inch,1.8*inch],repeatRows=1)
        at.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#14284b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#d5dee9')),('FONTSIZE',(0,0),(-1,-1),7.5),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story += [at, Spacer(1,10)]


    if doc_type == 'internal':
        warnings = data.get('internalWarnings') or []
        if warnings:
            story.append(Paragraph('Internal Warnings', styles['S1H2']))
            for warning in warnings:
                story.append(_p('⚠ ' + str(warning), styles['S1Body']))

    if doc_type == 'client':
        story.append(Paragraph('What We Need From You', styles['S1H2']))
        for line in data.get('customerRequirements') or []:
            story.append(_p('• '+line, styles['S1Body']))
    else:
        story.append(Paragraph('Internal Product Requirements', styles['S1H2']))
        for section in data.get('internalRequirements') or []:
            story.append(Paragraph(xml_escape(section.get('title','Product')), styles['S1H2']))
            for item in section.get('items') or []:
                story.append(_p('• '+item, styles['S1Body']))
    doc.build(story)
    return buf.getvalue(), title


@app.post('/api/generate-requirements-pdf')
def generate_requirements_pdf():
    cfg = cloudinary.config()
    if not cfg.cloud_name or not cfg.api_key or not cfg.api_secret:
        return jsonify({'error': 'Cloudinary is not configured'}), 503
    data = request.get_json(force=True) or {}
    doc_type = str(data.get('documentType') or 'client').lower()
    if doc_type not in ('client','internal'):
        return jsonify({'error':'documentType must be client or internal'}), 400
    try:
        pdf_bytes, title = _build_requirements_pdf(data, doc_type)
        client = _safe_filename(data.get('client'))
        start = _safe_filename(data.get('start') or 'no start date')
        folder = f"smart1_campaigns/{client}/{start}/documents"
        result = cloudinary.uploader.upload(
            BytesIO(pdf_bytes),
            resource_type='image',
            format='pdf',
            public_id=title,
            folder=folder,
            overwrite=True,
            unique_filename=False,
            tags=[client, start, 'smart1_requirements_pdf', doc_type],
        )
        return jsonify({'url': result.get('secure_url'), 'public_id': result.get('public_id'), 'filename': title + '.pdf'})
    except Exception as exc:
        logger.exception('PDF generation failed')
        return jsonify({'error':'PDF generation failed','detail':str(exc)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8000')), debug=False)


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    logger.exception('Unhandled application error')
    return jsonify({'error': 'Internal server error', 'type': type(exc).__name__, 'message': str(exc)}), 500


@app.post("/api/submit-io")
def submit_io():
    """Send a completed IO record to Smart 1 Suite / GoHighLevel."""
    webhook_url = os.environ.get("GHL_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return jsonify({"ok": False, "error": "GHL_WEBHOOK_URL is not configured on the server."}), 500

    data = request.get_json(silent=True) or {}
    client_pdf_url = str(data.get("client_pdf_url") or "").strip()
    internal_pdf_url = str(data.get("internal_pdf_url") or "").strip()

    if not client_pdf_url or not internal_pdf_url:
        return jsonify({
            "ok": False,
            "error": "Both the client PDF URL and internal PDF URL are required before the IO can be submitted."
        }), 400

    # Keep the full record, while also exposing commonly mapped fields at the top level.
    payload = {
        "event": "smart1_io_completed",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "io_type": data.get("ioType"),
        "client_name": data.get("client"),
        "client_website": data.get("url"),
        "sales_contact": data.get("salesContact"),
        "sales_contact_email": data.get("salesEmail"),
        "media_partner": data.get("partner"),
        "campaign_start_date": data.get("start"),
        "campaign_end_date": data.get("end"),
        "campaign_goals": data.get("objectives", []),
        "kpis": data.get("kpis", []),
        "geographic_target": data.get("geo"),
        "audiences": data.get("audiences", []),
        "income_targets": data.get("incomes", data.get("income", [])),
        "dayparting": data.get("dayparting"),
        "creative_source": data.get("creativeSource"),
        "exclusions_negative_keywords": data.get("exclusions"),
        "landing_page_mode": data.get("landingPageMode"),
        "shared_landing_page": data.get("landingPage"),
        "products": data.get("items", []),
        "creative_assets": data.get("creativeUploads", []),
        "brandfetch": data.get("brandfetch", {}),
        "client_pdf_url": client_pdf_url,
        "internal_pdf_url": internal_pdf_url,
        "cloudinary_documents": data.get("documents", {}),
        "campaign_data": data
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
    except requests.RequestException as exc:
        return jsonify({"ok": False, "error": f"Webhook request failed: {exc}"}), 502

    if response.status_code >= 400:
        return jsonify({
            "ok": False,
            "error": "Smart 1 Suite webhook returned an error.",
            "status_code": response.status_code,
            "response": response.text[:1000]
        }), 502

    return jsonify({
        "ok": True,
        "status_code": response.status_code,
        "message": "The completed IO was sent to Smart 1 Suite.",
        "client_pdf_url": client_pdf_url,
        "internal_pdf_url": internal_pdf_url
    })
