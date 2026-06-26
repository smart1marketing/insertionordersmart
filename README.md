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


## Version 10 additions

### Guardrail warnings
The browser recalculates warnings for:
- Product budget below an identifiable listed minimum/base rate
- Campaign term below a stated minimum contract term
- CPM/CPV materially outside the rate-card value
- Budget too small for the selected geography
- Too many products splitting a small monthly budget
- Estimated frequency likely below 1.5 per month
- Search budget below $1,500 monthly
- Missing management fee
- Missing creative fee when Smart 1 is building creative

These are operational warnings, not hard blocks.

### AI media mix
The new `/api/media-mix-recommendation` route uses the configured OpenAI Responses API model and receives goals, industry, geography, budgets, duration, audiences, creative availability, landing-page reviews, selected products, and the product catalog. The salesperson can accept suggested allocations for matching selected products or keep the original plan.

### Tracking plan
The conversational flow collects primary and secondary conversions, GA4, GTM, call tracking, thank-you page status, offline conversion import, and the person responsible for verification.

### Product trafficking cards
Each selected product receives a self-contained trafficking card with budget, dates, audience, geography, landing page, creative files, tracking, frequency cap, dayparting, exclusions, KPIs, instructions, owner, and generated naming conventions.

### Naming conventions
Generated names include:
- Campaign: `S1M_Order_Client_Product_Market_StartDate`
- Ad group: `Order_Client_Objective_Market_YYYY-MM`
- Creative: `Order_Client_Platform_SIZE_V1`
- Cloudinary folder by order, client, date, and product


## Version 11 order-number fix

Order numbers no longer require a Render persistent disk at `/var/data`.

The counter is stored as a small raw JSON system asset in the configured Cloudinary account:

`smart1_system/order_counter.json`

The first new IO receives order **10200**, followed by 10201, 10202, and so on. The counter survives Render restarts and deployments.

Optional Render environment variable:

- `ORDER_COUNTER_CLOUDINARY_ID=smart1_system/order_counter.json`

When Cloudinary is unavailable, the app uses `/tmp/smart1_order_counter.json` only as an emergency fallback and adds an internal warning because temporary storage can reset.

## Corrected workflow update
- Flask routes now register before the server starts.
- ZIP-radius lookup runs without blocking the intake and its status is visible at final review.
- Landing-page reviews are deferred until final review and do not block questions.
- Business descriptions are capped at 600 characters.
- Product detail entry includes Cancel Product.
- Empty/not-applicable visible values use X.
- Campaign, ad-group, creative, and Cloudinary naming fields were removed from trafficking cards and webhook data.
- Customer and internal PDF links remain visible after generation.
- Final submission uses the working requirements-PDF endpoint, preserves a local draft, returns a reference on failure, and displays Smart 1 Suite webhook status.
## Smart 1 Suite category

The obsolete **PROGRAMMATIC CAMPAIGN — Select Tactics - Comes with Retargeting** entry has been removed.

The **SMART 1 SUITE** category contains:

- **Consulting / Strategy / Reporting** — collects a monthly billing amount only.
- **Smart 1 Suite** — collects a monthly billing amount only and requests official connector access to all applicable social platforms and Google Business Profile (GMB).

These monthly services do not request CPM, CPV, delivery estimates, or mid-campaign budget schedules.


## Current corrective update
- Removed the PROGRAMMATIC CAMPAIGN category and its Select Tactics product.
- Renamed the DISPLAY category to SOCIAL.
- Added SMART 1 SUITE with Consulting / Strategy / Reporting and Smart 1 Suite monthly-billing products.
- Added cancel controls during category selection and product setup.
- Corrected customer PDF requirement generation.
- Added OpenAI connection diagnostics and more robust Responses API text extraction.
- Added request timeouts, ZIP and landing-page retry controls, and clearer Cloudinary upload status.
- Corrected product editor columns to Product, Start Date, End Date, Monthly Budget, and CPM-CPV.

## Build 2026.06.26-v4 deployment check

After deployment, the page header must show `Build 2026.06.26-v4`. The server now sends no-cache headers so an older JavaScript bundle cannot keep producing the removed `customerItemsForProduct is not defined` error.

The tracking-verification question now offers only `Client` or `Smart 1`.
