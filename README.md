
# Live Portfolio App — v2.2
Adds **Sector mapping** support and a **Sector Allocation** chart.
Also includes all features from v2.1 (pre/after-hours toggle, futures panel).

## Run
pip install -r requirements.txt
streamlit run app.py

## Environment variables (optional)
- REFRESH_SECONDS=60
- APP_TIMEZONE=Asia/Dubai
- EQUITIES_CSV_URL=...
- OPTIONS_CSV_URL=...
- SECTORS_CSV_URL=...   # <--- new
- DEFAULT_FUTURES="ES=F,NQ=F,CL=F,GC=F"
