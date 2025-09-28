
import os, random, string, base64, hashlib, requests
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
st.caption(f"Environment: {ENV} • PKCE OAuth (no Google Sheets)")

# --- PKCE helpers ---
def _gen_verifier(n=64):
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(random.choice(alphabet) for _ in range(n))

def _challenge_from(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

# Read query params (for OAuth return)
params = st.experimental_get_query_params()
auth_code = (params.get("code") or [None])[0]

# Keep verifier/state in session
if "pkce_verifier" not in st.session_state:
    st.session_state.pkce_verifier = None
if "oauth_state" not in st.session_state:
    st.session_state.oauth_state = None

def build_authorize_url():
    st.session_state.pkce_verifier = _gen_verifier()
    challenge = _challenge_from(st.session_state.pkce_verifier)
    st.session_state.oauth_state = _gen_verifier(24)
    return (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={APP_KEY}"
        f"&redirect_uri={REDIRECT}"
        f"&scope=read"
        f"&code_challenge={challenge}"
        f"&code_challenge_method=S256"
        f"&state={st.session_state.oauth_state}"
    )

# --- Connect flow ---
if not auth_code:
    st.success("1) Tap to connect your Saxo account.")
    if st.button("🔐 Connect to Saxo"):
        auth_url = build_authorize_url()
        st.markdown(f"[Continue to Saxo Login]({auth_url})")
    st.stop()

# --- Exchange code for token ---
st.info("2) Exchanging authorization code for access token…")
if not st.session_state.get("pkce_verifier"):
    st.error("Missing PKCE verifier. Go back to the app home and tap 'Connect to Saxo' again.")
    st.stop()

token_payload = {
    "grant_type": "authorization_code",
    "code": auth_code,
    "redirect_uri": REDIRECT,
    "client_id": APP_KEY,
    "code_verifier": st.session_state.pkce_verifier,
}
headers = {"Content-Type": "application/x-www-form-urlencoded"}

resp = requests.post(TOKEN_URL, data=token_payload, headers=headers)
if resp.status_code != 200:
    st.error(f"Token exchange failed: {resp.status_code} {resp.text}")
    st.stop()

tokens = resp.json()
access_token = tokens.get("access_token")
refresh_token = tokens.get("refresh_token")
if not access_token:
    st.error("No access_token returned.")
    st.stop()

st.success("3) Connected! Fetching your positions…")

# --- Fetch positions ---
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
    rows.append({
        "Symbol": symbol, "Qty": qty, "Avg Price": avg,
        "Last": last, "Value": value, "P/L": pl
    })

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
