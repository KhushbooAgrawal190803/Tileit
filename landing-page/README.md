# Tileit Landing Page

A professional landing page for Google Ads campaigns showcasing roofing quotes and product information.

## Features

- **Quote Display**: Shows a sample roofing quote with detailed cost breakdown
- **Product Introduction**: Brief overview of Tileit's roofing solutions
- **Buy Now Form**: Collects email, ZIP code, and marketing consent
- **Area Availability Popup**: Displays message when service area is not available

## Structure

```
landing-page/
├── index.html      # Main landing page HTML
├── styles.css      # Styling and layout
├── script.js       # Form handling and popup logic
└── README.md       # This file
```

## Usage

1. Open `index.html` in a web browser
2. View the quote on the left side
3. Read product information on the right side
4. Click "Buy Now" to open the form
5. Fill in email, ZIP code, and optionally check marketing consent
6. Submit to see the "area not available" popup

## Customization

### Update Quote Data
Edit the quote information in `index.html` within the `.quote-section` div.

### Change Product Text
Modify the product introduction in `index.html` within the `.product-intro` section.

### Styling
Adjust colors, fonts, and layout in `styles.css`. The primary color is `#8B3A3A` (red).

### Form Submission
Currently, the form logs data to console. To integrate with a backend:
1. Update `handleBuyNow()` in `script.js`
2. Add API endpoint to send form data
3. Handle success/error responses

## Deployment

This is a static site that can be deployed to:
- GitHub Pages
- Netlify
- Vercel
- Any static hosting service

Simply upload the `landing-page` folder contents to your hosting service.

