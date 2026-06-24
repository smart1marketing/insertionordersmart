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
