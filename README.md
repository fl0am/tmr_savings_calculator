# TMR Savings Calculator

Enter a prospect's fields, see yearly savings for buying a TinyLineMarker vs. Pay As You
Spray vs. painting by hand, and download a one-page TMR-branded PDF for the prospect.

## Change the numbers
Edit `savings_settings.toml` (list prices, PAYS rates, paint, hand-painting estimates),
commit, and the app updates. No code changes needed.

## Run it on your own computer
    pip install -r requirements.txt
    streamlit run app.py

## Files
- `app.py` - the page
- `savings_core.py` - the math and the PDF
- `savings_settings.toml` - all default numbers
- `assets/tmr_logo.png` - logo for the app and PDFs
