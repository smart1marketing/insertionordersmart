import os
import logging
from pathlib import Path
from flask import Flask, render_template, request, jsonify
import cloudinary
import cloudinary.utils
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8000')), debug=False)


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    logger.exception('Unhandled application error')
    return jsonify({'error': 'Internal server error', 'type': type(exc).__name__, 'message': str(exc)}), 500
