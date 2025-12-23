import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURATION & CONSTANTS ---
st.set_page_config(page_title="SF Tree Basin: Planned Maintenance", page_icon="🌳", layout="wide")

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
    """Fetches tree basin records closed in the last 18 months."""
    eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
    
    select_cols = (
        "service_request_id, requested_datetime, closed_date, "
        "service_details, status_notes, address, media_url, supervisor_district"
    )
    
    # Logic from version 1: Focus on Backfill/Empty Tree Basins
    details_filter = "(upper(service_details) LIKE '%TREE_BASIN%')"
    
    params = {
        "$select": select_cols,
        "$where": f"closed_date > '{eighteen_months_ago}' AND agency_responsible LIKE '%PW%' AND {details_filter}",
        "$limit": 10000, # Increased limit for citywide stats
        "$order": "closed_date DESC"
    }

    if district_id != "Citywide":
        params["$where"] += f" AND supervisor_district = '{district_id}'"

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
    st.header("SF Tree Basins: Maintenance Cancellations")
    st.write("Visualizing tree basin requests closed as 'Cancelled - Planned Maintenance'.")
    
    # District Filter
    query_params = st.query_params
    url_district = query_params.get("district", "Citywide")
    if url_district not in SUPERVISOR_MAP and url_district != "Citywide":
        url_district = "Citywide"

    col_filter, _ = st.columns([1, 3])
    with col_filter:
        selected_label = st.selectbox(
            "Filter by Supervisor District:", 
            ["Citywide"] + list(SUPERVISOR_MAP.values()),
            index=(["Citywide"] + list(SUPERVISOR_MAP.values())).index(SUPERVISOR_MAP.get(url_district, "Citywide"))
        )

    # Update URL
    rev_map = {v: k for k, v in SUPERVISOR_MAP.items()}
    rev_map["Citywide"] = "Citywide"
    selected_id = rev_map[selected_label]
    st.query_params["district"] = selected_id

    st.markdown("---")

    with st.spinner("Fetching data..."):
        df = load_data(selected_id)

    if df.empty:
        st.warning("No records found matching criteria.")
        return

    # Stats Calculation
    df['status_notes'] = df['status_notes'].astype(str)
    cancelled_df = df[df['status_notes'] == 'Cancelled - Planned Maintenance'].copy()
    
    total_count = len(df)
    cancelled_count = len(cancelled_df)
    perc = (cancelled_count / total_count * 100) if total_count > 0 else 0

    st.markdown(
        f"""
        <div class='metric-container'>
            <span class='metric-text'>
                Found <b>{total_count:,}</b> tree basin records total.<br>
                <b>{cancelled_count:,}</b> were "Cancelled - Planned Maintenance" ({perc:.1f}%).
            </span>
        </div>
        """, 
        unsafe_allow_html=True
    )

    # Filter for Images
    cancelled_df['valid_image'] = cancelled_df['media_url'].apply(get_valid_image_url)
    display_df = cancelled_df.dropna(subset=['valid_image'])

    if display_df.empty:
        st.info("No images available for these cancelled requests.")
        return

    # Image Grid
    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(display_df.iterrows()):
        with cols[i % COLS_PER_ROW]:
            with st.container(border=True):
                st.image(row['valid_image'], use_container_width=True)
                
                # Dates & Calculations
                opened_str = row['requested_datetime'].strftime('%m/%d/%y') if pd.notnull(row['requested_datetime']) else "?"
                closed_str = row['closed_date'].strftime('%m/%d/%y') if pd.notnull(row['closed_date']) else "?"
                days_open = (row['closed_date'] - row['requested_datetime']).days if (pd.notnull(row['requested_datetime']) and pd.notnull(row['closed_date'])) else "?"

                # Address & Maps
                addr = row.get('address', 'Location N/A')
                short_addr = addr.split(',')[0]
                map_url = f"https://www.google.com/maps/search/?api=1&query={addr.replace(' ', '+')}"
                
                # Ticket Link
                ticket_id = row['service_request_id']
                ticket_url = f"https://mobile311.sfgov.org/tickets/{ticket_id}"

                st.markdown(f"**[{short_addr}]({map_url})**")
                st.caption(f"📅 {opened_str} ➔ {closed_str} ({days_open} days)")
                st.markdown(f"Ticket: [{ticket_id}]({ticket_url})")

if __name__ == "__main__":
    main()
