
import os, random, string, base64, hashlib, requests, time
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Saxo Live Portfolio — Direct API", layout="wide")

# --- Secrets ---
APP_KEY   = st.secrets.get("SAXO_APP_KEY", "")
REDIRECT  = st.secrets.get("SAXO_REDIRECT_URI", "")
ENV       = st.secrets.get("SAXO_ENV", "SIM").upper()   # "SIM" or "LIVE"
if not APP_KEY or not REDIRECT:
    st.error("Missing secrets: Please set SAXO_APP_KEY and SAXO_REDIRECT_URI in Streamlit Secrets.")
    st.stop()

AUTH_BASE = "https://sim.logonvalidation.net" if ENV == "SIM" else "https://www.saxobank.com"
TOKEN_URL = f"{AUTH_BASE}/token"
AUTH_URL  = f"{AUTH_BASE}/authorize"
API_BASE  = "https://gateway.saxobank.com/sim/openapi" if ENV == "SIM" else "https://gateway.saxobank.com/openapi"

st.title("📈 Saxo Live Portfolio — Direct API")
st.caption(f"Environment: {ENV} • PKCE OAuth (resilient flow)")

# ---------- Resilient PKCE store (server-side) ----------
@st.cache_resource
def _flow_store():
    # flow_id -> {"verifier": str, "ts": float}
    return {}

def _gen(n=64):
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(random.choice(alphabet) for _ in range(n))

def _challenge_from(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

def build_authorize_url():
    store = _flow_store()
    flow_id = _gen(32)              # will be sent as OAuth "state"
    verifier = _gen(64)
    store[flow_id] = {"verifier": verifier, "ts": time.time()}
    challenge = _challenge_from(verifier)
    return (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={APP_KEY}"
        f"&redirect_uri={REDIRECT}"
        f"&scope=read"
        f"&code_challenge={challenge}"
        f"&code_challenge_method=S256"
        f"&state={flow_id}"
    )

# ---------- Parse query params ----------
params = st.query_params
auth_code  = params.get("code")
auth_state = params.get("state")

# ---------- Start flow ----------
if not auth_code:
    st.success("1) Tap to connect your Saxo account.")
    if st.button("🔐 Connect to Saxo"):
        st.markdown(f"[Continue to Saxo Login]({build_authorize_url()})")
    st.stop()

# ---------- Exchange code for token ----------
st.info("2) Exchanging authorization code for access token…")
store = _flow_store()
if not auth_state or auth_state not in store:
    st.error("Could not find PKCE verifier for this login (state missing/expired). Go back and tap 'Connect to Saxo' again.")
    st.stop()

verifier = store.pop(auth_state)["verifier"]  # one-time use
payload = {
    "grant_type": "authorization_code",
    "code": auth_code,
    "redirect_uri": REDIRECT,
    "client_id": APP_KEY,
    "code_verifier": verifier,
}
headers = {"Content-Type": "application/x-www-form-urlencoded"}
resp = requests.post(TOKEN_URL, data=payload, headers=headers)
if resp.status_code != 200:
    st.error(f"Token exchange failed: {resp.status_code} {resp.text}")
    st.stop()

tokens = resp.json()
access_token = tokens.get("access_token")
if not access_token:
    st.error("No access_token returned.")
    st.stop()

st.success("3) Connected! Fetching your positions…")

# ---------- Fetch positions ----------
pos_url = f"{API_BASE}/port/v1/netpositions/me?$top=200&FieldGroups=DisplayAndFormat,NetPositionView"
api_headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
r = requests.get(pos_url, headers=api_headers)
if r.status_code != 200:
    st.error(f"Positions fetch failed: {r.status_code} {r.text}")
    st.stop()

items = r.json().get("Data", []) or r.json().get("data", [])
rows = []
for it in items:
    disp = it.get("DisplayAndFormat", {})
    view = it.get("NetPositionView", {})
    symbol = disp.get("Symbol") or it.get("NetPositionId", "")
    qty    = view.get("NetPositionAmount")
    avg    = view.get("AverageOpenPrice")
    last   = view.get("CurrentMarketPrice")
    value  = view.get("Exposure")
    pl     = view.get("ProfitLossOnTrade") or view.get("ProfitLoss")
    rows.append({"Symbol": symbol, "Qty": qty, "Avg Price": avg, "Last": last, "Value": value, "P/L": pl})

df = pd.DataFrame(rows)
if df.empty:
    st.warning("No positions returned for this account.")
else:
    c1, c2 = st.columns(2)
    c1.metric("Total Value", f"${df['Value'].fillna(0).sum():,.0f}")
    c2.metric("P/L", f"${df['P/L'].fillna(0).sum():,.0f}")
    st.subheader("Your Saxo Positions")
    st.dataframe(
        df, use_container_width=True,
        column_config={
            "Qty":       st.column_config.NumberColumn(format="%,d"),
            "Avg Price": st.column_config.NumberColumn(format="$%.2f"),
            "Last":      st.column_config.NumberColumn(format="$%.2f"),
            "Value":     st.column_config.NumberColumn(format="$%,.0f"),
            "P/L":       st.column_config.NumberColumn(format="$%,.0f"),
        },
    )
