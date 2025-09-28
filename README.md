
# Live Portfolio App — v2.3
**Fix:** Reads config from Streamlit `st.secrets` (with env fallback) so your Options URL in Secrets works.
Adds a small debug panel and formats the equities table.

## Deploy
pip install -r requirements.txt
streamlit run app.py

## Secrets (TOML)
EQUITIES_CSV_URL = "https://...output=csv"
OPTIONS_CSV_URL  = "https://...output=csv"
SECTORS_CSV_URL  = "https://...output=csv"
REFRESH_SECONDS  = "60"
APP_TIMEZONE     = "Asia/Dubai"
DEFAULT_FUTURES  = "ES=F,NQ=F,CL=F,GC=F"
