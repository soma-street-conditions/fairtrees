import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="SF Tree Basin Maintenance", page_icon="🌳", layout="wide")

API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"

SUPERVISORS = {
    "1": "1 - Connie Chan", "2": "2 - Stephen Sherrill", "3": "3 - Danny Sauter",
    "4": "4 - Alan Wong", "5": "5 - Bilal Mahmood", "6": "6 - Matt Dorsey",
    "7": "7 - Myrna Melgar", "8": "8 - Rafael Mandelman", "9": "9 - Jackie Fielder",
    "10": "10 - Shamann Walton", "11": "11 - Chyanne Chen"
}

# --- 2. HELPER FUNCTIONS ---

@st.cache_data(ttl=300)
def load_data(district_id):
    """Fetches tree basin records closed in the last 18 months."""
    
    start_date = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')

    # Query: Any status, closed > 18 months ago, PW agency, tree_basin service details
    where_clause = (
        f"closed_date > '{start_date}' "
        "AND agency_responsible LIKE '%PW%' "
        "AND upper(service_details) LIKE '%TREE_BASIN%'"
    )

    if district_id != "Citywide":
        where_clause += f" AND supervisor_district = '{district_id}'"

    params = {
        "$select": "service_request_id, requested_datetime, closed_date, service_details, address, media_url, supervisor_district, status_notes",
        "$where": where_clause,
        "$limit": 2000,
        "$order": "closed_date DESC"
    }

    try:
        r = requests.get(API_URL, params=params)
        r.raise_for_status()
        df = pd.DataFrame(r.json())

        if not df.empty:
            df['requested_datetime'] = pd.to_datetime(df['requested_datetime'], errors='coerce')
            df['closed_date'] = pd.to_datetime(df['closed_date'], errors='coerce')
            df['status_notes'] = df['status_notes'].fillna("No notes available.")
            df['service_details'] = df['service_details'].fillna("")
        
        return df

    except Exception as e:
        st.error(f"API Connection Error: {e}")
        return pd.DataFrame()

def get_image_url(media_item):
    """Extracts and validates image URL."""
    if not media_item: return None
    url = media_item.get('url', '') if isinstance(media_item, dict) else str(media_item)
    clean_url = url.split('?')[0].lower()
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        return url
    return None

# --- 3. MAIN APP ---

def main():
    # --- UPDATED HEADERS ---
    st.header("SF Tree Basin Maintenance")
    st.write("Visualizing 311 reports for tree basin maintenance (backfill and empty) closed by Public Works.")

    # --- Sidebar & Filters ---
    qp = st.query_params
    default_dist = qp.get("district", "Citywide")
    if default_dist not in SUPERVISORS: default_dist = "Citywide"

    col_filter, _ = st.columns([1, 3])
    with col_filter:
        opts = ["Citywide"] + list(SUPERVISORS.keys())
        selected_id = st.selectbox(
            "Filter by Supervisor District:",
            options=opts,
            index=opts.index(default_dist),
            format_func=lambda x: SUPERVISORS.get(x, "Citywide")
        )

    if selected_id == "Citywide":
        if "district" in st.query_params: del st.query_params["district"]
    else:
        st.query_params["district"] = selected_id

    st.divider()

    # --- Load Data ---
    with st.spinner("Fetching data..."):
        df = load_data(selected_id)

    if df.empty:
        st.warning("No records found matching criteria.")
        return

    df['valid_image'] = df['media_url'].apply(get_image_url)
    display_df = df.dropna(subset=['valid_image'])
    
    # Updated text description
    st.write(f"Showing **{len(display_df)}** records with photos out of **{len(df)}** total closed requests.")

    if display_df.empty:
        st.info("No images available for these requests.")
        return

    st.divider()
    
    # --- Image Grid ---
    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(display_df.iterrows()):
        tile = cols[i % COLS_PER_ROW]
        
        with tile:
            with st.container(border=True):
                st.image(row['valid_image'], use_container_width=True)
                
                # --- Restored and formatted text ---
                addr_clean = row.get('address', 'Location N/A')
                short_addr = addr_clean.split(',')[0]
                map_url = f"https://www.google.com/maps/search/?api=1&query={addr_clean.replace(' ', '+')}"
                
                opened = row['requested_datetime'].strftime('%m/%d/%y') if pd.notnull(row['requested_datetime']) else "?"
                closed = row['closed_date'].strftime('%m/%d/%y') if pd.notnull(row['closed_date']) else "?"
                
                days_open = "?"
                if pd.notnull(row['requested_datetime']) and pd.notnull(row['closed_date']):
                    days_open = (row['closed_date'] - row['requested_datetime']).days

                st.markdown(f"**[{short_addr}]({map_url})**")
                st.caption(f"Opened {opened}, Closed {closed}")
                st.caption(f"Open {days_open} days")
                st.caption(f"Request Details: {row['service_details']}")

                # Clickable/Expandable Status Notes
                with st.expander("Status Notes"):
                    st.write(row['status_notes'])
                    ticket_id = row['service_request_id']
                    ticket_url = f"https://mobile311.sfgov.org/tickets/{ticket_id}"
                    st.markdown(f"[View Ticket {ticket_id}]({ticket_url})")

if __name__ == "__main__":
    main()
