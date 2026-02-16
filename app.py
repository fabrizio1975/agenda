import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, time, timedelta

st.set_page_config(page_title="Agenda Barbiere", layout="wide")
st.title("✂️ Agenda - Fabrizio & Gianluca")

BARBIERI = ["Fabrizio", "Gianluca"]
OPEN_WEEKDAYS = {1, 2, 3, 4, 5}  # Mar-Sab (Mon=0)

MATTINA_START = time(9, 0)
MATTINA_END   = time(13, 30)
POM_START     = time(14, 30)
POM_END       = time(19, 0)
SLOT_MIN      = 30

SHEET_ID = st.secrets.get("sheet_id", "").strip()
WORKSHEET_NAME = st.secrets.get("worksheet_name", "appointments").strip()
GOOGLE_CREDS = st.secrets.get("gcp_service_account")

REQUIRED_COLS = ["date", "slot", "barber", "customer"]

def generate_slots():
    slots = []
    def add_range(start_t, end_t):
        dt = datetime.combine(date.today(), start_t)
        dt_end = datetime.combine(date.today(), end_t)
        while dt < dt_end:
            slots.append(dt.strftime("%H:%M"))
            dt += timedelta(minutes=SLOT_MIN)
    add_range(MATTINA_START, MATTINA_END)
    add_range(POM_START, POM_END)
    return slots

SLOTS = generate_slots()

def working_days(year):
    d = date(year, 1, 1)
    out = []
    while d.year == year:
        if d.weekday() in OPEN_WEEKDAYS:
            out.append(d)
        d += timedelta(days=1)
    return out

def it_label(d):
    nomi = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    return f"{nomi[d.weekday()]} {d.strftime('%d/%m/%Y')}"

@st.cache_resource
def get_ws():
    if not SHEET_ID:
        st.error("Manca `sheet_id` nei Secrets di Streamlit Cloud.")
        st.stop()

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(GOOGLE_CREDS, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    return sh.worksheet(WORKSHEET_NAME)

@st.cache_data(ttl=5)
def read_all():
    ws = get_ws()
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame(columns=REQUIRED_COLS)

    headers = values[0]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=headers)

    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = ""

    df = df[REQUIRED_COLS].copy()
    for c in REQUIRED_COLS:
        df[c] = df[c].astype(str).str.strip()
    return df

def append_row(date_str, slot, barber, customer):
    ws = get_ws()
    ws.append_row([date_str, slot, barber, customer], value_input_option="USER_ENTERED")

def delete_one(date_str, slot, barber, customer):
    ws = get_ws()
    values = ws.get_all_values()
    if len(values) < 2:
        return

    headers = values[0]
    idx_date = headers.index("date")
    idx_slot = headers.index("slot")
    idx_barber = headers.index("barber")
    idx_customer = headers.index("customer")

    for i, row in enumerate(values[1:], start=2):
        if (row[idx_date] == date_str and row[idx_slot] == slot and
            row[idx_barber] == barber and row[idx_customer] == customer):
            ws.delete_rows(i)
            return

# ---- UI: scelta giorno solo Mar-Sab ----
st.sidebar.header("📅 Giorno (Mar–Sab)")
year = date.today().year
days = working_days(year)
labels = [it_label(d) for d in days]
label_map = {it_label(d): d for d in days}

today = date.today()
default_idx = labels.index(it_label(today)) if today in label_map.values() else 0

chosen_label = st.sidebar.selectbox("Scegli giorno:", labels, index=default_idx)
chosen_date = label_map[chosen_label]
day_str = chosen_date.isoformat()

st.subheader(f"🗓️ {chosen_label}")

df_all = read_all()
df_day = df_all[df_all["date"] == day_str].copy()

# ---- Nuovo appuntamento ----
st.sidebar.divider()
st.sidebar.header("➕ Nuovo appuntamento")

with st.sidebar.form("new_appt", clear_on_submit=True):
    barber = st.selectbox("Barbiere:", BARBIERI)
    slot = st.selectbox("Orario:", SLOTS)
    customer = st.text_input("Cliente:")
    ok = st.form_submit_button("Salva")

if ok:
    customer = customer.strip()
    if not customer:
        st.error("Inserisci il nome del cliente.")
    else:
        conflict = (
            (df_all["date"] == day_str) &
            (df_all["barber"] == barber) &
            (df_all["slot"] == slot)
        ).any()

        if conflict:
            st.error("Orario già occupato.")
        else:
            append_row(day_str, slot, barber, customer)
            st.cache_data.clear()
            st.success("✅ Salvato.")
            st.rerun()

# ---- Griglia ----
st.markdown("### 📋 Agenda del giorno")
grid = pd.DataFrame({"Ora": SLOTS})
for b in BARBIERI:
    grid[b] = ""

for _, r in df_day.iterrows():
    grid.loc[grid["Ora"] == r["slot"], r["barber"]] = r["customer"]

st.dataframe(grid, use_container_width=True, hide_index=True)

# ---- Elimina ----
st.markdown("### 🧹 Elimina appuntamento")
if df_day.empty:
    st.info("Nessun appuntamento.")
else:
    df_day["label"] = df_day.apply(lambda r: f"{r['slot']} • {r['barber']} • {r['customer']}", axis=1)
    pick = st.selectbox("Seleziona:", df_day["label"].tolist())

    if st.button("Elimina"):
        row = df_day[df_day["label"] == pick].iloc[0]
        delete_one(row["date"], row["slot"], row["barber"], row["customer"])
        st.cache_data.clear()
        st.success("🗑️ Eliminato.")
        st.rerun()
