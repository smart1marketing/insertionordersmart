# SMART1 Campaign Builder with Cloudinary uploads

## Security
The Cloudinary API secret stays on the server. It is never embedded in the HTML or sent to the browser.

## Run locally
1. Install Python 3.10+.
2. In this folder run: `pip install -r requirements.txt`
3. Set the `CLOUDINARY_URL` environment variable in your hosting platform or terminal.
4. Run: `python app.py`
5. Open: `http://localhost:8000`

## Windows PowerShell example
`$env:CLOUDINARY_URL="cloudinary://YOUR_API_KEY:YOUR_API_SECRET@YOUR_CLOUD_NAME"`
`python app.py`

## Deployment
Deploy this folder to any Python host that supports environment variables (Render, Railway, Azure App Service, AWS, Google Cloud Run, etc.). Add `CLOUDINARY_URL` as a secret environment variable.

The upload manager supports multiple files, product assignment, creative-coming-later status, dimension/file-size checks, Cloudinary tags, and returned secure asset URLs.


## Brandfetch
Set `BRANDFETCH_API_KEY` and `BRANDFETCH_CLIENT_ID` as server environment variables. The builder uses the business website entered during intake to retrieve the brand name, description, logo, colors, fonts, company data and brand links. These details are included in JSON exports, the customer checklist/PDF and the printable campaign report.

## Landing pages
The intake asks whether the campaign uses one shared landing page or product-specific landing pages. Product-specific URLs are saved with each media-plan line item.


## Render diagnostics
After deployment, open `/health`. It should return `status: ok` and `template_exists: true`. If false, confirm `templates/index.html` is committed beside `app.py` and Render Root Directory is blank.


## AI business descriptions
Add `OPENAI_API_KEY` in Render. The optional `OPENAI_MODEL` defaults to `gpt-5-mini`. The server uses the OpenAI Responses API with web search to review the supplied business website and create a factual business description.

## Product selection
The UI first shows the all-caps rate-card categories and then shows only the products in the selected category.


## v4 UX update
- The chat input stays pinned at the bottom of the chat column.
- Multi-answer questions use checkboxes and a Continue button; typing DONE is no longer required.
- Typing X is retained as a legacy fallback when a text input is visible.

## v5 PDF and document updates
- All campaign start/end questions use browser date pickers and default to today's date.
- Internal and customer requirements are generated as true PDFs on the secure Flask server.
- PDFs are automatically uploaded to Cloudinary and the returned URL is saved in the campaign data.
- Customer filename: `S1M - <client name>.pdf`
- Internal filename: `S1M Internal - <client name>.pdf`
- Both PDFs include a Brandfetch section, brand color swatches, linked logo, brand links on separate lines, and uploaded creative image thumbnails with asset links.
- The Print IO view includes the same enhanced brand and creative presentation.


## Smart 1 Suite / GoHighLevel Webhook

Add this Render environment variable:

- `GHL_WEBHOOK_URL` — the GoHighLevel inbound webhook URL.

When the salesperson selects **Submit Finished IO**, the app:

1. Generates or confirms the customer PDF in Cloudinary.
2. Generates or confirms the internal PDF in Cloudinary.
3. Sends the complete campaign record to GoHighLevel.
4. Includes top-level `client_pdf_url` and `internal_pdf_url` fields for easy workflow mapping.
5. Includes the full campaign record in `campaign_data`.

Do not place the webhook URL directly in the browser HTML.


## Order number sequence

New IOs request the next order number from `/api/next-order-number`, beginning with **10200**.

For the sequence to survive deploys and restarts, the Render service must have a persistent disk mounted at:

- Mount path: `/var/data`
- Environment variable: `ORDER_COUNTER_FILE=/var/data/smart1_order_counter.json`

The included `render.yaml` defines a 1 GB persistent disk. Render persistent disks may require a paid service plan.

## Variable monthly budgets

Each product can have a base monthly budget plus one or more dated budget-change periods. The app calculates:

- Current/base monthly spend by product
- Dated monthly budget schedule
- Prorated total campaign budget by product
- Total campaign budget across all products

## Creative warnings

Creative files can be marked evergreen. Any file that does not match a known specification creates:

- A SMART1Snap validation warning on the upload screen
- An internal warning in the campaign report
- An internal warning in the internal PDF
- A warning in the exported campaign data and webhook payload


## Geo targeting and landing-page review

The builder now supports:

- City/ZIP Code + Radius
- DMA
- Other geographic definitions

For radius targeting, the OpenAI Responses API with web search returns a comma-separated ZIP Code list. This is an AI-assisted operational list and should be reviewed before campaign trafficking; an LLM cannot mathematically guarantee every ZIP polygon intersection without an authoritative geospatial boundary dataset.

Every shared or product-specific landing page is reviewed through OpenAI. CTA and conversion recommendations are stored in `landingPageReviews`, displayed under Internal Needs, included in the internal PDF, exported with campaign data, and sent in the GoHighLevel webhook payload.
