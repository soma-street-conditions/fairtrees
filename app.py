import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="SF Tree Basin Maintenance", page_icon="🌳", layout="wide")

# Use the styling from your preferred display version
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .stMarkdown p { font-size: 0.9rem; margin-bottom: 0px; }
        div.stButton > button { width: 100%; }
    </style>
    <meta name="robots" content="noindex, nofollow">
""", unsafe_allow_html=True)

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

# --- 2. SESSION STATE & HELPERS ---
if 'limit' not in st.session_state:
    st.session_state.limit = 1000

def get_valid_image_url(media_item):
    """Safely extracts image URL and validates format."""
    if not media_item: 
        return None
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not isinstance(url, str):
        return None
    clean_url = url.split('?')[0].lower()
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        return url
    return None

@st.cache_data(ttl=300)
def load_data(district_id, limit):
    """Fetches tree basin records with specific PW criteria."""
    eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
    
    # Combined Logic: Tree Basin filter from version 1
    where_clause = (
        f"closed_date > '{eighteen_months_ago}' "
        "AND agency_responsible LIKE '%PW%' "
        "AND (upper(service_details) LIKE '%TREE_BASIN%') "
        "AND media_url IS NOT NULL"
    )

    if district_id != "Citywide":
        where_clause += f" AND supervisor_district = '{district_id}'"

    params = {
        "$select": "service_request_id, requested_datetime, closed_date, service_details, status_notes, address, media_url, supervisor_district, analysis_neighborhood",
        "$where": where_clause,
        "$limit": limit,
        "$order": "closed_date DESC"
    }

    try:
        r = requests.get(API_URL, params=params)
        r.raise_for_status()
        return pd.DataFrame(r.json())
    except Exception as e:
        st.error(f"Data loading error: {e}")
        return pd.DataFrame()

# --- 3. MAIN APP & FILTERING ---

def main():
    st.header("SF Tree Basin Maintenance")
    st.write("Visualizing 311 reports for tree basin maintenance closed by Public Works.")
    
    # Deep Linking Logic
    query_params = st.query_params
    url_district = query_params.get("district", "Citywide")
    
    district_options = ["Citywide"] + list(SUPERVISOR_MAP.keys())
    if url_district not in district_options:
        url_district = "Citywide"

    col_filter, _ = st.columns([1, 3])
    with col_filter:
        selected_id = st.selectbox(
            "Filter by Supervisor District:", 
            district_options,
            index=district_options.index(url_district),
            format_func=lambda x: SUPERVISOR_MAP.get(x, "Citywide")
        )

    st.query_params["district"] = selected_id
    st.markdown("---")

    # Data Loading
    df = load_data(selected_id, st.session_state.limit)

    if df.empty:
        st.warning("No records found matching criteria.")
        return

    # Filter for valid images
    df['valid_image'] = df['media_url'].apply(get_valid_image_url)
    display_df = df.dropna(subset=['valid_image'])

    # --- 4. PREFERRED IMAGE GRID DISPLAY ---
    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)
    
    for i, (index, row) in enumerate(display_df.iterrows()):
        col_index = i % COLS_PER_ROW
        with cols[col_index]:
            with st.container(border=True):
                # Image
                st.image(row['valid_image'], use_container_width=True)
                
                # Metadata (Using your preferred labels)
                neighborhood = row.get('analysis_neighborhood', 'Unknown Neighborhood')
                address = row.get('address', 'Unknown').split(',')[0]
                map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}+San+Francisco"
                
                closed_date = pd.to_datetime(row['closed_date']).strftime('%b %d, %Y') if pd.notnull(row['closed_date']) else "N/A"
                
                st.markdown(f"**{neighborhood}**")
                st.markdown(f"Closed: {closed_date}")
                st.markdown(f"[{address}]({map_url})")
                st.caption(f"ID: {row['service_request_id']}")

    # Load More Button
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button(f"Load More Records (Current Limit: {st.session_state.limit})"):
            st.session_state.limit += 500
            st.rerun()

if __name__ == "__main__":
    main()
