import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, time, timedelta

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="Agenda Barbiere", layout="wide")
st.title("✂️ Agenda - Fabrizio & Gianluca")

BARBIERI = ["Fabrizio", "Gianluca"]

# Apertura: Martedì-Sabato
OPEN_WEEKDAYS = {1, 2, 3, 4, 5}  # Tue..Sat

# Orari
MATTINA_START = time(9, 0)
MATTINA_END = time(13, 30)
POM_START = time(14, 30)
POM_END = time(19, 0)
SLOT_MIN = 30

SHEET_URL = "https://docs.google.com/spreadsheets/d/1JJGhVPq3PDO5OqrNM8YotzgywvVCqCdULUfWxwUkdgo/edit?usp=sharing/edit"
WORKSHEET = "appointments"

REQUIRED_COLS = ["date", "slot", "barber", "customer"]

# -----------------------------
# SLOT ORARI
# -----------------------------
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

# -----------------------------
# GIORNI LAVORATIVI ANNO
# -----------------------------
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

# -----------------------------
# GOOGLE SHEETS
# -----------------------------
if not SHEET_URL:
    st.error("Inserisci gsheets_url nei secrets di Streamlit Cloud.")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def read_data():
    df = conn.read(spreadsheet=SHEET_URL, worksheet=WORKSHEET)

    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLS)

    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = ""

    df = df[REQUIRED_COLS].copy()
    df["date"] = df["date"].astype(str)
    df["slot"] = df["slot"].astype(str)
    df["barber"] = df["barber"].astype(str)
    df["customer"] = df["customer"].astype(str)
    return df

def write_data(df):
    conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET, data=df)

# -----------------------------
# SELEZIONE GIORNO
# -----------------------------
st.sidebar.header("📅 Giorno (Mar–Sab)")

current_year = date.today().year
days = working_days(current_year)

labels = [it_label(d) for d in days]
label_map = {it_label(d): d for d in days}

today = date.today()
default_idx = 0
if today in label_map.values():
    default_idx = labels.index(it_label(today))

selected_label = st.sidebar.selectbox("Scegli giorno:", labels, index=default_idx)
selected_date = label_map[selected_label]
day_str = selected_date.isoformat()

st.subheader(f"🗓️ {selected_label}")

# -----------------------------
# CARICA DATI
# -----------------------------
df_all = read_data()
df_day = df_all[df_all["date"] == day_str]

# -----------------------------
# NUOVO APPUNTAMENTO
# -----------------------------
st.sidebar.divider()
st.sidebar.header("➕ Nuovo appuntamento")

with st.sidebar.form("new_appt", clear_on_submit=True):
    barber = st.selectbox("Barbiere:", BARBIERI)
    slot = st.selectbox("Orario:", SLOTS)
    customer = st.text_input("Cliente (nome):")
    submit = st.form_submit_button("Salva")

if submit:
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
            new_row = {
                "date": day_str,
                "slot": slot,
                "barber": barber,
                "customer": customer
            }
            df_all = pd.concat([df_all, pd.DataFrame([new_row])], ignore_index=True)
            df_all = df_all.sort_values(["date","slot","barber"]).reset_index(drop=True)

            write_data(df_all)
            st.cache_data.clear()
            st.success("Appuntamento salvato.")
            st.rerun()

# -----------------------------
# GRIGLIA
# -----------------------------
st.markdown("### 📋 Agenda del giorno")

grid = pd.DataFrame({"Ora": SLOTS})
for b in BARBIERI:
    grid[b] = ""

for _, r in df_day.iterrows():
    grid.loc[grid["Ora"] == r["slot"], r["barber"]] = r["customer"]

st.dataframe(grid, use_container_width=True, hide_index=True)

# -----------------------------
# ELIMINA
# -----------------------------
st.markdown("### 🧹 Elimina appuntamento")

if df_day.empty:
    st.info("Nessun appuntamento.")
else:
    df_day["label"] = df_day.apply(lambda r: f"{r['slot']} • {r['barber']} • {r['customer']}", axis=1)
    pick = st.selectbox("Seleziona:", df_day["label"].tolist())

    if st.button("Elimina"):
        to_del = df_day[df_day["label"] == pick].iloc[0]
        mask = ~(
            (df_all["date"] == to_del["date"]) &
            (df_all["slot"] == to_del["slot"]) &
            (df_all["barber"] == to_del["barber"]) &
            (df_all["customer"] == to_del["customer"])
        )
        df_all = df_all[mask]

        write_data(df_all)
        st.cache_data.clear()
        st.success("Eliminato.")
        st.rerun()




