import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta

# 1. Page Config
st.set_page_config(page_title="SF 311: The Visual Wall", page_icon="🧱", layout="wide")

# --- STYLING ---
st.markdown("""
    <style>
        /* Tighten up the grid */
        div[data-testid="stVerticalBlock"] > div { gap: 0.5rem; }
        .stMarkdown p { font-size: 0.85rem; margin-bottom: 0px; }
        /* Hide full screen buttons on images to make it look cleaner */
        button[title="View fullscreen"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# 2. Session State
if 'limit' not in st.session_state:
    st.session_state.limit = 400

# Header
st.header("Bureau of Urban Forestry: The 'Planned Maintenance' Wall")
st.markdown("""
**Visualizing the Backlog:** Every image below represents a resident report of an **Empty Tree Basin** that was closed without planting, cited as "Planned Maintenance".
""")
st.markdown("---")

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filters")
district_options = ["Citywide"] + [str(i) for i in range(1, 12)]
selected_district = st.sidebar.selectbox("Supervisor District", district_options, index=0)

# Limit Slider
st.sidebar.markdown("---")
st.session_state.limit = st.sidebar.slider("Records to Fetch", 100, 2000, 400, step=100)

# 3. API Setup
lookback_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# 4. Query Construction
where_clauses = [
    f"closed_date > '{lookback_date}'",
    "service_details = 'empty_tree_basin'",
    "upper(status_notes) LIKE '%PLANNED%'",
    "media_url IS NOT NULL"
]

if selected_district != "Citywide":
    where_clauses.append(f"supervisor_district = '{selected_district}'")

params = {
    "$where": " AND ".join(where_clauses),
    "$order": "closed_date DESC",
    "$limit": st.session_state.limit
}

# 5. Fetch Data
@st.cache_data(ttl=300)
def get_data(query_params):
    try:
        r = requests.get(base_url, params=query_params)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        else:
            return pd.DataFrame()
    except:
        return pd.DataFrame()

df = get_data(params)

# 6. ROBUST URL PARSER (The Fix)
def extract_clean_url(media_item):
    if not media_item:
        return None
    
    url = None
    
    # Case A: It's a dictionary object
    if isinstance(media_item, dict):
        url = media_item.get('url')
    
    # Case B: It's a string that LOOKS like a dictionary "{"url":...}"
    elif isinstance(media_item, str):
        try:
            # Try to fix double quotes if present
            if media_item.startswith('{'):
                # SODA sometimes returns stringified JSON
                data = json.loads(media_item)
                url = data.get('url')
            else:
                # It's just a plain URL string
                url = media_item
        except:
            # If parsing fails, treat the string as the url
            url = media_item

    # FILTER: Remove Verint (Private) links
    if url and "verintcloudservices" in url:
        return None # Skip these, they don't render
        
    return url

# 7. Display The Wall
if not df.empty:
    
    # Filter list down to only valid images FIRST
    valid_records = []
    for index, row in df.iterrows():
        clean_url = extract_clean_url(row.get('media_url'))
        if clean_url:
            row['clean_image_url'] = clean_url
            valid_records.append(row)
    
    st.write(f"Showing **{len(valid_records)}** viewable images.")
    
    # Grid Layout (4 columns)
    cols = st.columns(4)
    
    for i, row in enumerate(valid_records):
        col_index = i % 4
        with cols[col_index]:
            # The Image
            st.image(row['clean_image_url'], use_container_width=True)
            
            # Minimal Details
            closed_date = str(row.get('closed_date', ''))[:10]
            address = str(row.get('address', 'SF')).split(',')[0]
            
            # Caption
            st.caption(f"📍 {address} | 📅 Closed: {closed_date}")
            
else:
    st.info("No records found matching these criteria.")
