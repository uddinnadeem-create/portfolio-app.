
# Live Portfolio App — v2 (Equities + Options, Google Sheets integration)

Features:
- **Google Sheets CSV URLs** as live data source (or file upload)
- **Equities**: Ticker / Shares / AvgBuy → live prices via yfinance → P/L, allocation, movers
- **Options**: optional CSV with Underlying / Expiry / Strike / C/P / Side / Qty (+ premiums) → basic P&L
- **Benchmarks**: SPY & QQQ YTD for context
- **Auto-refresh** every N seconds (default 60)
- Dubai timezone friendly

## Schemas
**Equities CSV**
```
Ticker,Shares,AvgBuy
SOFI,3096,8.40
AAPL,50,150
NVDA,10,120
```

**Options CSV (optional)**
```
Underlying,Expiry,Strike,C/P,Side,Qty,PremiumOpen,PremiumCurrent
NVDA,Jan-2026,125,C,Long,1,20.50,24.10
HOOD,Oct-2025,110,P,Short,-2,3.20,1.85
```

## Google Sheets as live source
1. In your Sheet (Equities or Options), create a tab with the schema above.
2. **File → Share → Publish to web** → select tab → **Comma-separated values (.csv)** → copy link.
3. Paste the CSV link(s) into the app sidebar inputs.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Cloud)
- Push these files to a GitHub repo.
- On share.streamlit.io, create an app pointing to `app.py`.
- (Optional) set env vars: `REFRESH_SECONDS=60`, `APP_TIMEZONE=Asia/Dubai`, and `EQUITIES_CSV_URL`, `OPTIONS_CSV_URL`.
