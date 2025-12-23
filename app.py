import streamlit as st
import pandas as pd
import requests
import ast
from datetime import datetime, timedelta

# 1. Page Configuration
st.set_page_config(
    page_title="SF 311: The Purge Visualizer", 
    page_icon="📸", 
    layout="wide"
)

# --- CSS STYLING ---
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; }
        div[data-testid="column"] { background-color: #f9f9f9; border-radius: 8px; padding: 10px; }
        img { border-radius: 5px; max-height: 250px; object-fit: cover; }
    </style>
""", unsafe_allow_html=True)

# 2. Header
st.title("Bureau of Urban Forestry: The 'Planned Maintenance' Wall")
st.markdown("Visualizing **Empty Tree Basin** requests that were administratively closed without work.")
st.markdown("---")

# 3. TOP ROW FILTERS
c1, c2 = st.columns([1, 1])

with c1:
    # District Filter
    # "All Districts" is just a UI label. In the query logic below, we check for it.
    districts = ["All Districts"] + [str(i) for i in range(1, 12)]
    selected_district = st.selectbox("Supervisor District", districts, index=0)

with c2:
    limit = st.selectbox("Max Records to Check", [500, 1000, 2000, 5000], index=1)

# 4. DATA FETCHING
API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"
lookback = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%S')

# Query Construction
# We start with the base requirements: Empty Basin, Closed, Planned Maintenance, Recent, Has Media
where_clauses = [
    "service_details = 'empty_tree_basin'",
    "status = 'Closed'",
    "upper(status_notes) LIKE '%PLANNED%'",
    f"closed_date > '{lookback}'",
    "media_url IS NOT NULL"
]

# LOGIC: Only add the district filter if the user DID NOT select "All Districts"
if selected_district != "All Districts":
    where_clauses.append(f"supervisor_district = '{selected_district}'")

# Join all clauses with AND
full_where_query = " AND ".join(where_clauses)

params = {
    "$where": full_where_query,
    "$order": "closed_date DESC",
    "$limit": limit
}

# --- IMAGE PARSER ---
def parse_image_url(val):
    """
    Extracts a clean http URL from the messy API response.
    Returns None if the link is private (Verint) or invalid.
    """
    if not val: return None
    
    url = None
    
    # Type 1: Dictionary
    if isinstance(val, dict):
        url = val.get('url')
    
    # Type 2: String
    elif isinstance(val, str):
        # Clean up stringified dicts if present
        if 'http' in val:
            # Simple extraction: Find the http part
            import re
            match = re.search(r'(https?://[^"\'>\s]+)', val)
            if match:
                url = match.group(1)
                
    # FILTER: Cloudinary Only
    # This is the "Eligible Case" check. If it's Verint, we can't show it.
    if url and 'cloudinary' in url.lower():
        # Clean any trailing characters that might break the link
        return url.split("'")[0].split('"')[0]
        
    return None

@st.cache_data(ttl=300)
def fetch_data(params):
    try:
        r = requests.get(API_URL, params=params)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
    except:
        pass
    return pd.DataFrame()

# Load Data
with st.spinner(f"Scanning the last {limit} records..."):
    df = fetch_data(params)

# 5. MAIN DISPLAY
if not df.empty:
    
    # Apply Parser
    df['clean_image'] = df['media_url'].apply(parse_image_url)
    
    # Keep only rows with valid images
    viewable_df = df[df['clean_image'].notna()].copy()
    
    st.success(f"Found **{len(viewable_df)}** viewable images out of {len(df)} records checked.")
    
    if not viewable_df.empty:
        cols = st.columns(4)
        for i, row in enumerate(viewable_df.itertuples()):
            col = cols[i % 4]
            with col:
                st.image(row.clean_image, use_container_width=True)
                
                # Metadata
                date = str(getattr(row, 'closed_date', ''))[:10]
                addr = str(getattr(row, 'address', 'SF')).split(',')[0]
                
                # Highlight the Purge
                if date in ['2025-12-04', '2025-12-05']:
                     st.markdown(f"**📍 {addr}**")
                     st.error(f"PURGED: {date}")
                else:
                     st.markdown(f"**📍 {addr}**")
                     st.caption(f"Closed: {date}")

    else:
        st.warning("Records found, but all contained private (Verint) links.")
else:
    st.info("No records found matching these filters.")
