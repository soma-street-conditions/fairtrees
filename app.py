import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURATION & CONSTANTS ---
st.set_page_config(page_title="SF Tree Basin Maintenance", page_icon="🌳", layout="wide")

API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"

SUPERVISOR_MAP = {
    "1": "1 - Connie Chan",
    "2": "2 - Stephen Sherrill",
    "3": "3 - Danny Sauter",
    "4": "4 - Alan Wong",
    "5": "5 - Bilal Mahmood",
    "6": "6 - Matt Dorsey",
    "7": "7 - Myrna Melgar",
    "8": "8 - Rafael Mandelman",
    "9": "9 - Jackie Fielder",
    "10": "10 - Shamann Walton",
    "11": "11 - Chyanne Chen"
}

# --- 2. STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .metric-container {
            background-color: #0E1117; 
            border: 1px solid #303030;
            border-radius: 5px;
            padding: 15px;
            text-align: center;
            margin-bottom: 20px;
        }
        .metric-text {
            font-size: 1.1rem;
            color: #FFFFFF;
        }
        /* Enforce uniform image heights for a clean grid */
        div[data-testid="stImage"] > img {
            object-fit: cover; 
            height: 200px; 
            width: 100%;
        }
    </style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---

@st.cache_data(ttl=300)
def load_data(district_id):
    """Fetches all Tree Basin records closed by PW in the last 18 months."""
    eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
    
    select_cols = (
        "service_request_id, requested_datetime, closed_date, "
        "service_details, status_notes, address, media_url, supervisor_district"
    )
    
    # Filter: Specifically targeting Tree Basin reports handled by Public Works
    where_clause = (
        f"closed_date > '{eighteen_months_ago}' "
        "AND agency_responsible LIKE '%PW%' "
        "AND (upper(service_details) LIKE '%TREE_BASIN%')"
    )

    if district_id != "Citywide":
        where_clause += f" AND supervisor_district = '{district_id}'"

    params = {
        "$select": select_cols,
        "$where": where_clause,
        "$limit": 5000,
        "$order": "closed_date DESC"
    }

    try:
        r = requests.get(API_URL, params=params)
        r.raise_for_status()
        df = pd.DataFrame(r.json())
        if df.empty: return pd.DataFrame()

        df['requested_datetime'] = pd.to_datetime(df['requested_datetime'], errors='coerce')
        df['closed_date'] = pd.to_datetime(df['closed_date'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Data loading error: {e}")
        return pd.DataFrame()

def get_valid_image_url(media_item):
    if not media_item: return None
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not isinstance(url, str): return None
    clean_url = url.split('?')[0].lower()
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        return url
    return None

# --- 4. MAIN APP LOGIC ---

def main():
    st.header("SF Tree Basin Maintenance Tracker")
    st.write("Visualizing all 311 tree basin reports (backfill/empty) closed by Public Works.")
    
    # --- Filter Logic ---
    query_params = st.query_params
    url_district = query_params.get("district", "Citywide")
    
    # Validation
    if url_district not in SUPERVISOR_MAP and url_district != "Citywide":
        url_district = "Citywide"

    col_filter, _ = st.columns([1, 3])
    with col_filter:
        selected_label = st.selectbox(
            "Filter by Supervisor District:", 
            ["Citywide"] + list(SUPERVISOR_MAP.values()),
            index=(["Citywide"] + list(SUPERVISOR_MAP.values())).index(SUPERVISOR_MAP.get(url_district, "Citywide"))
        )

    # Sync URL with Selection
    rev_map = {v: k for k, v in SUPERVISOR_MAP.items()}
    rev_map["Citywide"] = "Citywide"
    selected_id = rev_map[selected_label]
    st.query_params["district"] = selected_id

    st.markdown("---")

    with st.spinner("Fetching 311 records..."):
        df = load_data(selected_id)

    if df.empty:
        st.warning("No closed tree basin records found for this selection.")
        return

    # --- Stats Display ---
    total_count = len(df)
    # Calculate average resolution time
    df['days_to_close'] = (df['closed_date'] - df['requested_datetime']).dt.days
    avg_days = df['days_to_close'].mean() if not df['days_to_close'].dropna().empty else 0

    st.markdown(
        f"""
        <div class='metric-container'>
            <span class='metric-text'>
                Showing <b>{total_count:,}</b> completed tree basin requests.<br>
                Average resolution time: <b>{avg_days:.1f} days</b>.
            </span>
        </div>
        """, 
        unsafe_allow_html=True
    )

    # --- Image Grid ---
    df['valid_image'] = df['media_url'].apply(get_valid_image_url)
    display_df = df.dropna(subset=['valid_image'])

    if display_df.empty:
        st.info("No photos available for these records.")
        return

    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(display_df.iterrows()):
        with cols[i % COLS_PER_ROW]:
            with st.container(border=True):
                st.image(row['valid_image'], use_container_width=True)
                
                # Metadata
                opened_str = row['requested_datetime'].strftime('%m/%d/%y') if pd.notnull(row['requested_datetime']) else "?"
                closed_str = row['closed_date'].strftime('%m/%d/%y') if pd.notnull(row['closed_date']) else "?"
                days_open = row['days_to_close'] if pd.notnull(row['days_to_close']) else "?"

                addr = row.get('address', 'Location N/A').split(',')[0]
                map_url = f"https://www.google.com/maps/search/?api=1&query={addr.replace(' ', '+')}+San+Francisco"
                
                ticket_id = row['service_request_id']
                ticket_url = f"https://mobile311.sfgov.org/tickets/{ticket_id}"

                st.markdown(f"**[{addr}]({map_url})**")
                st.caption(f"📅 {opened_str} ➔ {closed_str} ({days_open} days)")
                st.markdown(f"Ticket: [{ticket_id}]({ticket_url})")

if __name__ == "__main__":
    main()
