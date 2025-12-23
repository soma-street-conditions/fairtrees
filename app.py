import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
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

# --- 2. HELPER FUNCTIONS ---

def get_supervisor_options():
    return ["Citywide"] + list(SUPERVISOR_MAP.values())

def get_reverse_supervisor_map():
    rev = {v: k for k, v in SUPERVISOR_MAP.items()}
    rev["Citywide"] = "Citywide"
    return rev

def get_valid_image_url(media_item):
    """Safely extracts image URL and prevents AttributeError on non-string data."""
    if not media_item: 
        return None
    
    # Extract URL if it's a dictionary, otherwise use as is
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    
    # Crucial Fix: Ensure url is a string before calling .split() or .lower()
    if not isinstance(url, str):
        return None
        
    clean_url = url.split('?')[0].lower()
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        return url
    return None

def load_data(district_id):
    """Fetches tree basin records closed in the last 18 months."""
    eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
    
    where_clause = (
        f"closed_date > '{eighteen_months_ago}' "
        "AND agency_responsible LIKE '%PW%' "
        "AND (upper(service_details) LIKE '%TREE_BASIN%')"
    )

    if district_id != "Citywide":
        where_clause += f" AND supervisor_district = '{district_id}'"

    params = {
        "$select": "service_request_id, requested_datetime, closed_date, service_details, status_notes, address, media_url, supervisor_district",
        "$where": where_clause,
        "$limit": 2000,
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

# --- 3. MAIN APP ---

def main():
    st.header("SF Tree Basin Maintenance")
    st.write("Visualizing 311 reports for tree basin maintenance (backfill and empty) closed by Public Works.")
    
    # --- Sidebar / URL Params ---
    query_params = st.query_params
    url_district = query_params.get("district", "Citywide")
    
    if url_district not in SUPERVISOR_MAP and url_district != "Citywide":
        url_district = "Citywide"

    current_label = SUPERVISOR_MAP.get(url_district, "Citywide")
    rev_map = get_reverse_supervisor_map()

    col_filter, _ = st.columns([1, 3])
    with col_filter:
        selected_label = st.selectbox(
            "Filter by Supervisor District:", 
            get_supervisor_options(),
            index=get_supervisor_options().index(current_label)
        )

    selected_id = rev_map[selected_label]
    if selected_id == "Citywide":
        if "district" in st.query_params:
            del st.query_params["district"]
    else:
        st.query_params["district"] = selected_id

    st.markdown("---")

    # --- Data Loading ---
    with st.spinner("Fetching data..."):
        df = load_data(selected_id)

    if df.empty:
        st.warning("No records found matching criteria.")
        return

    # Process Images
    df['valid_image'] = df['media_url'].apply(get_valid_image_url)
    display_df = df.dropna(subset=['valid_image'])
    
    st.write(f"Showing **{len(display_df)}** records with photos out of **{len(df)}** total closed requests.")

    if display_df.empty:
        st.info("No images available for these requests.")
        return

    st.markdown("---")
    
    # --- Image Grid (Original Logic Restored) ---
    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(display_df.iterrows()):
        col = cols[i % COLS_PER_ROW]
        with col:
            with st.container(border=True):
                st.image(row['valid_image'], use_container_width=True)
                
                opened_str = row['requested_datetime'].strftime('%m/%d/%y') if pd.notnull(row['requested_datetime']) else "?"
                closed_str = row['closed_date'].strftime('%m/%d/%y') if pd.notnull(row['closed_date']) else "?"
                
                days_open = "?"
                if pd.notnull(row['requested_datetime']) and pd.notnull(row['closed_date']):
                    days_open = (row['closed_date'] - row['requested_datetime']).days

                ticket_id = row['service_request_id']
                ticket_url = f"https://mobile311.sfgov.org/tickets/{ticket_id}"
                
                addr_clean = row.get('address', 'Location N/A')
                short_addr = addr_clean.split(',')[0]
                map_url = f"https://www.google.com/maps/search/?api=1&query={addr_clean.replace(' ', '+')}"
                
                st.markdown(f"**[{short_addr}]({map_url})**")
                st.caption(f"Opened: {opened_str} | Closed: {closed_str}")
                st.caption(f"Days Open: {days_open}")
                st.markdown(f"[View Ticket {ticket_id}]({ticket_url})")

if __name__ == "__main__":
    main()
