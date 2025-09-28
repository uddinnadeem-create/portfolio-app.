
import os
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Live Portfolio (v2.2)", layout="wide")

# ---------- Config ----------
REFRESH_SECONDS = int(os.getenv("REFRESH_SECONDS", "60"))
DEFAULT_TZ = os.getenv("APP_TIMEZONE", "Asia/Dubai")

st.title("📈 Live Portfolio Dashboard — Equities + Options (v2.2)")
st.caption(f"Auto-refresh every {REFRESH_SECONDS}s • Timezone: {DEFAULT_TZ}")

# ---------- Sidebar: Data Sources ----------
st.sidebar.header("Data Sources")
source_choice = st.sidebar.radio("Choose input method", ["Google Sheets (CSV URLs)", "Upload CSV files"], index=0)

def load_csv(url_or_file):
    try:
        if isinstance(url_or_file, str):
            return pd.read_csv(url_or_file)
        else:
            return pd.read_csv(url_or_file)
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")
        return pd.DataFrame()

equities_df = pd.DataFrame()
options_df = pd.DataFrame()
sectors_df = pd.DataFrame()

if source_choice == "Google Sheets (CSV URLs)":
    st.sidebar.markdown("**Publish your Google Sheets to CSV** (File → Share → *Publish to web* → CSV).")
    eq_url = st.sidebar.text_input("Equities CSV URL", value=os.getenv("EQUITIES_CSV_URL",""))
    op_url = st.sidebar.text_input("Options CSV URL (optional)", value=os.getenv("OPTIONS_CSV_URL",""))
    sec_url = st.sidebar.text_input("Sectors CSV URL (optional)", value=os.getenv("SECTORS_CSV_URL",""))
    if eq_url:
        equities_df = load_csv(eq_url)
    if op_url:
        options_df = load_csv(op_url)
    if sec_url:
        sectors_df = load_csv(sec_url)
else:
    st.sidebar.write("Upload CSVs with these schemas:")
    st.sidebar.code("Equities: Ticker,Shares,AvgBuy\nOptions: Underlying,Expiry,Strike,C/P,Side,Qty,PremiumOpen,PremiumCurrent\nSectors: Ticker,Sector", language="text")
    eq_file = st.sidebar.file_uploader("Upload Equities CSV", type=["csv"])
    op_file = st.sidebar.file_uploader("Upload Options CSV (optional)", type=["csv"])
    sec_file = st.sidebar.file_uploader("Upload Sectors CSV (optional)", type=["csv"])
    if eq_file: equities_df = load_csv(eq_file)
    if op_file: options_df = load_csv(op_file)
    if sec_file: sectors_df = load_csv(sec_file)

# ---------- Sidebar: Pricing options ----------
st.sidebar.header("Pricing Options")
include_prepost = st.sidebar.checkbox("Include pre/after-hours (US)", value=True, help="Use extended-hours data when available on Yahoo Finance")
refresh_override = st.sidebar.number_input("Refresh seconds", min_value=10, max_value=600, value=REFRESH_SECONDS, step=5)
if refresh_override != REFRESH_SECONDS:
    REFRESH_SECONDS = int(refresh_override)

if equities_df.empty:
    st.info("Provide your **Equities CSV** to begin. (Ticker,Shares,AvgBuy). Example tickers: AAPL, NVDA, TSLA")
    st.stop()

# Normalise columns for equities
colmap = {c.lower(): c for c in equities_df.columns}
def getc(name): return colmap.get(name.lower())
req_cols = ["Ticker","Shares","AvgBuy"]
missing = [c for c in req_cols if getc(c) is None]
if missing:
    st.error(f"Equities CSV missing columns: {missing}. Expected columns: {', '.join(req_cols)}")
    st.stop()

eq = equities_df.rename(columns={getc("Ticker"):"Ticker", getc("Shares"):"Shares", getc("AvgBuy"):"AvgBuy"}).copy()

# Optional exchange prefix for Google-like tickers; we will strip for yfinance
ex_pref = st.sidebar.text_input("Exchange prefix (display only, optional, e.g., NASDAQ:)", value="")
eq["Symbol"] = eq["Ticker"].apply(lambda t: f"{ex_pref}{t}" if ex_pref else t)

# ---------- Live Prices via yfinance ----------
@st.cache_data(ttl=REFRESH_SECONDS-1 if REFRESH_SECONDS>1 else 1, show_spinner=False)
def fetch_last_prices(symbols, use_prepost=True):
    sym_map = {}
    for s in symbols:
        yfs = s.replace("NASDAQ:", "").replace("NYSE:", "").replace("LON:", "")
        sym_map[s] = yfs
    uniq = list(set(sym_map.values()))
    data = yf.download(uniq, period="1d", interval="1m", auto_adjust=False,
                       prepost=use_prepost, threads=True, progress=False)
    last_prices = {}
    if isinstance(data, pd.DataFrame) and not data.empty:
        if "Close" in data:
            close = data["Close"]
            if isinstance(close, pd.DataFrame):
                for col in close.columns:
                    s = close[col].dropna()
                    if not s.empty:
                        last_prices[col] = float(s.iloc[-1])
            else:
                s = close.dropna()
                if not s.empty and len(uniq)==1:
                    last_prices[uniq[0]] = float(s.iloc[-1])
    # fallback per symbol
    for yfs in uniq:
        if yfs not in last_prices:
            try:
                px = float(yf.Ticker(yfs).fast_info.get("last_price", np.nan))
                if np.isfinite(px):
                    last_prices[yfs] = px
            except Exception:
                pass
    out = {}
    for s,yfs in sym_map.items():
        out[s] = last_prices.get(yfs, np.nan)
    return out

prices = fetch_last_prices(eq["Symbol"].tolist(), use_prepost=include_prepost)
eq["Price"] = eq["Symbol"].map(prices)
eq["Value"] = eq["Price"] * eq["Shares"]
eq["Cost"]  = eq["AvgBuy"] * eq["Shares"]
eq["P/L"]   = eq["Value"] - eq["Cost"]
eq["P/L %"] = np.where(eq["Cost"]>0, eq["P/L"]/eq["Cost"], np.nan)

# ---------- Merge sectors if provided ----------
if not sectors_df.empty and "Ticker" in sectors_df.columns and "Sector" in sectors_df.columns:
    sectors_df["Ticker"] = sectors_df["Ticker"].astype(str).str.strip().str.upper()
    eq["Ticker"] = eq["Ticker"].astype(str).str.strip().str.upper()
    eq = eq.merge(sectors_df[["Ticker","Sector"]], on="Ticker", how="left")

# ---------- Options (optional) ----------
opt = pd.DataFrame()
if not options_df.empty:
    omap = {c.lower(): c for c in options_df.columns}
    oreq = ["Underlying","Expiry","Strike","C/P","Side","Qty"]
    missing_o = [c for c in oreq if omap.get(c.lower()) is None]
    if missing_o:
        st.warning(f"Options CSV missing: {missing_o}. Expected: {', '.join(oreq)}")
    opt = options_df.rename(columns={
        omap.get("Underlying".lower(), "Underlying"): "Underlying",
        omap.get("Expiry".lower(), "Expiry"): "Expiry",
        omap.get("Strike".lower(), "Strike"): "Strike",
        omap.get("C/P".lower(), "C/P"): "C/P",
        omap.get("Side".lower(), "Side"): "Side",
        omap.get("Qty".lower(), "Qty"): "Qty",
        omap.get("PremiumOpen".lower(), "PremiumOpen"): "PremiumOpen",
        omap.get("PremiumCurrent".lower(), "PremiumCurrent"): "PremiumCurrent",
    }).copy()
    if "PremiumOpen" in opt.columns and "PremiumCurrent" in opt.columns:
        try:
            opt["P/L (premium)"] = (opt["PremiumCurrent"].astype(float) - opt["PremiumOpen"].astype(float)) * opt["Qty"].astype(float) * 100.0
        except Exception:
            pass

# ---------- Totals & Header KPIs ----------
total_value = float(eq["Value"].sum(skipna=True))
total_cost  = float(eq["Cost"].sum(skipna=True))
total_pl    = float(eq["P/L"].sum(skipna=True))
total_pl_pct = (total_pl / total_cost) if total_cost else np.nan

c1,c2,c3,c4 = st.columns(4)
c1.metric("Total Value", f"${total_value:,.0f}")
c2.metric("Cost Basis", f"${total_cost:,.0f}")
c3.metric("P/L", f"${total_pl:,.0f}", delta=f"{(total_pl_pct*100):.2f}%")
c4.metric("Holdings", f"{len(eq)} equities")

st.markdown("---")
st.subheader("Equities")
st.dataframe(eq[["Ticker","Shares","AvgBuy","Price","Value","Cost","P/L","P/L %"] + ([ "Sector"] if "Sector" in eq.columns else [])]
             .sort_values("Value", ascending=False),
             use_container_width=True)

# Allocation chart
import plotly.express as px
alloc_fig = px.pie(eq, names="Ticker", values="Value", title="Allocation by Current Value")
st.plotly_chart(alloc_fig, use_container_width=True)

# Sector allocation chart if Sector present
if "Sector" in eq.columns:
    st.subheader("Sector Allocation")
    sec_fig = px.pie(eq.fillna({"Sector":"Unknown"}), names="Sector", values="Value", title="Allocation by Sector")
    st.plotly_chart(sec_fig, use_container_width=True)

# Movers
colA, colB = st.columns(2)
top_gainers = eq.sort_values("P/L %", ascending=False).head(10)[["Ticker","P/L %"]].set_index("Ticker")
top_losers  = eq.sort_values("P/L %", ascending=True).head(10)[["Ticker","P/L %"]].set_index("Ticker")
colA.bar_chart(top_gainers)
colB.bar_chart(top_losers)

# ---------- Benchmarks (same as v2.1) ----------
st.markdown("---")
st.subheader("Benchmarks")

@st.cache_data(ttl=REFRESH_SECONDS-1 if REFRESH_SECONDS>1 else 1)
def bench_ret(ticker, use_prepost=True):
    try:
        dfb = yf.download(ticker, period="ytd", interval="1d", prepost=use_prepost, progress=False)
        if dfb.empty: return np.nan
        start = float(dfb["Adj Close"].iloc[0])
        last  = float(dfb["Adj Close"].iloc[-1])
        return (last/start) - 1.0
    except Exception:
        return np.nan

b_spy = bench_ret("SPY", True)
b_qqq = bench_ret("QQQ", True)
bc1, bc2, bc3 = st.columns(3)
bc1.metric("Portfolio P/L % (vs Cost)", f"{(total_pl_pct*100):.2f}%")
bc2.metric("SPY YTD", f"{(b_spy*100):.2f}%")
bc3.metric("QQQ YTD", f"{(b_qqq*100):.2f}%")

# ---------- Futures Panel (same as v2.1) ----------
st.markdown("---")
st.subheader("Futures (live)")
default_futs = os.getenv("DEFAULT_FUTURES", "ES=F,NQ=F,CL=F,GC=F")
fut_symbols = st.text_input("Futures tickers (comma-separated)", value=default_futs, help="Examples: ES=F (S&P 500), NQ=F (Nasdaq 100), CL=F (WTI), GC=F (Gold)")
@st.cache_data(ttl=REFRESH_SECONDS-1 if REFRESH_SECONDS>1 else 1, show_spinner=False)
def fetch_futures(tickers, use_prepost=True):
    if not tickers: return pd.DataFrame()
    data = yf.download(tickers, period="1d", interval="1m", prepost=use_prepost, progress=False, threads=True)
    last = {}
    if isinstance(data, pd.DataFrame) and not data.empty and "Close" in data:
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            for col in close.columns:
                s = close[col].dropna()
                if not s.empty:
                    last[col] = float(s.iloc[-1])
        else:
            s = close.dropna()
            if not s.empty and isinstance(tickers, str):
                last[tickers] = float(s.iloc[-1])
    tick_list = tickers if isinstance(tickers, list) else [t.strip() for t in tickers.split(",")]
    for t in tick_list:
        if t not in last:
            try:
                px = float(yf.Ticker(t).fast_info.get("last_price", np.nan))
                if np.isfinite(px):
                    last[t] = px
            except Exception:
                pass
    if not last:
        return pd.DataFrame()
    out = pd.DataFrame.from_dict(last, orient="index", columns=["Last"]).rename_axis("Symbol").reset_index()
    return out

futures_df = pd.DataFrame()
if fut_symbols.strip():
    futures_df = fetch_futures([s.strip() for s in fut_symbols.split(",") if s.strip()], True)
    if not futures_df.empty:
        st.dataframe(futures_df, use_container_width=True)
    else:
        st.info("No futures data returned (check symbols or market hours).")

# ---------- Auto Refresh ----------
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=REFRESH_SECONDS*1000, limit=100000, key="refresh_key")
