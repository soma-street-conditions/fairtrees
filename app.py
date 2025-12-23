import streamlit as st
import pandas as pd
import requests
import ast # Safer than json for fixing single-quote dictionaries
from datetime import datetime, timedelta

# 1. Page Configuration
st.set_page_config(
    page_title="SF 311: The Purge Visualizer", 
    page_icon="🌳", 
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

# 3. FILTERS
c1, c2 = st.columns([1, 1])
with c1:
    districts = ["Citywide"] + [str(i) for i in range(1, 12)]
    selected_district = st.selectbox("Supervisor District", districts, index=0)
with c2:
    limit = st.selectbox("Max Records to Check", [500, 1000, 2000, 5000], index=1)

# 4. DATA FETCHING
API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"
lookback = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%S')

# Query: Empty Basin + Closed + Planned + Has Media
where_query = f"service_details = 'empty_tree_basin' AND status = 'Closed' AND upper(status_notes) LIKE '%PLANNED%' AND closed_date > '{lookback}' AND media_url IS NOT NULL"

if selected_district != "Citywide":
    where_query += f" AND supervisor_district = '{selected_district}'"

params = {
    "$where": where_query,
    "$order": "closed_date DESC",
    "$limit": limit
}

# --- THE FIX: BULLETPROOF IMAGE PARSER ---
def extract_clean_url(media_item):
    """
    Parses the messy media_url field into a clean string.
    Handles: Dicts, JSON strings, Python-string-dicts, and plain URLs.
    """
    if not media_item: 
        return None

    raw_url = None

    # Case 1: It's already a dictionary (Standard JSON response)
    if isinstance(media_item, dict):
        raw_url = media_item.get('url', None)

    # Case 2: It's a string (The messy part)
    elif isinstance(media_item, str):
        # Is it a stringified dictionary like "{'url': '...'}"?
        if media_item.strip().startswith('{') and 'url' in media_item:
            try:
                # ast.literal_eval handles single quotes (json.loads does not)
                parsed = ast.literal_eval(media_item)
                raw_url = parsed.get('url')
            except:
                # Fallback: Brute force split if eval fails
                try:
                    # Finds http... until the next quote
                    import re
                    match = re.search(r'(http[^"\']+)', media_item)
                    if match:
                        raw_url = match.group(1)
                except:
                    pass
        else:
            # It's just a plain URL string
            raw_url = media_item

    # FILTER: Public Images Only
    # We only return the URL if it is Cloudinary (Public).
    # We explicitly skip Verint (Private) to avoid broken image icons.
    if raw_url and "cloudinary" in raw_url.lower():
        return raw_url
        
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
with st.spinner("Fetching data..."):
    df = fetch_data(params)

# 5. MAIN DISPLAY
if not df.empty:
    
    # Apply the Parser
    df['clean_image'] = df['media_url'].apply(extract_clean_url)
    
    # Filter: Keep ONLY rows that successfully parsed a valid image
    viewable_df = df[df['clean_image'].notna()].copy()
    
    st.success(f"Found **{len(viewable_df)}** viewable images out of {len(df)} records.")
    
    if not viewable_df.empty:
        # Grid Layout
        cols = st.columns(4)
        for i, row in enumerate(viewable_df.itertuples()):
            col = cols[i % 4]
            with col:
                st.image(row.clean_image, use_container_width=True)
                
                # Details
                date = str(getattr(row, 'closed_date', ''))[:10]
                addr = str(getattr(row, 'address', 'SF')).split(',')[0]
                
                if date in ['2025-12-04', '2025-12-05']:
                    st.error(f"PURGED: {date}")
                else:
                    st.caption(f"Closed: {date}")
                
                st.markdown(f"**{addr}**")
    else:
        st.warning("Records found, but all images were hidden/private (Verint links).")
else:
    st.info("No records found.")
