import streamlit as st
import pandas as pd
import requests
import ast
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
        .purge-badge { color: red; font-weight: bold; border: 1px solid red; padding: 2px 6px; border-radius: 4px; }
    </style>
""", unsafe_allow_html=True)

# 2. Header
st.title("Bureau of Urban Forestry: The 'Planned Maintenance' Wall")
st.markdown("Visualizing **Empty Tree Basin** requests that were administratively closed without work.")
st.markdown("---")

# 3. FILTERS
c1, c2 = st.columns([1, 1])
with c1:
    # District Filter
    districts = ["All Districts"] + [str(i) for i in range(1, 12)]
    selected_district = st.selectbox("Supervisor District", districts, index=0)
with c2:
    limit = st.selectbox("Max Records to Check", [500, 1000, 2000, 5000], index=1)

# 4. DATA FETCHING
API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"
lookback = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%S')

# --- STRATEGY CHANGE: BROAD FETCH, PYTHON FILTER ---
# We removed the 'status_notes' filter from the API query because it causes SODA errors.
# We fetch ALL closed empty tree basins and filter in memory.
where_clauses = [
    "service_details = 'empty_tree_basin'",
    "status = 'Closed'",
    f"closed_date > '{lookback}'",
    "media_url IS NOT NULL"
]

if selected_district != "All Districts":
    where_clauses.append(f"supervisor_district = '{selected_district}'")

params = {
    "$where": " AND ".join(where_clauses),
    "$order": "closed_date DESC",
    "$limit": limit
}

@st.cache_data(ttl=300)
def fetch_data(params):
    try:
        r = requests.get(API_URL, params=params)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        else:
            st.error(f"API Connection Error: {r.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# 5. IMAGE PARSER
def get_clean_url(val):
    """
    Robust parser for the messy media_url field.
    """
    if not val: return None
    url = None
    
    # Handle Dicts (API often returns objects)
    if isinstance(val, dict):
        url = val.get('url')
    # Handle Strings
    elif isinstance(val, str):
        if 'http' in val:
            # Try to grab the URL if it's buried in a string representation
            if val.startswith('{') and "'url'" in val:
                try:
                    # Safe eval for stringified dicts
                    parsed = ast.literal_eval(val)
                    url = parsed.get('url')
                except:
                    pass
            
            # Fallback: Just take the string if it looks like a URL
            if not url and val.startswith('http'):
                url = val

    # FINAL FILTER: Public Images Only
    # Verint links (internal) do not render publicly. Cloudinary does.
    if url and 'cloudinary' in url.lower():
        # Clean up any trailing junk
        return url.split("'")[0].split('"')[0]
        
    return None

# Load Data
with st.spinner(f"Fetching {limit} records..."):
    df = fetch_data(params)

# 6. MAIN DISPLAY LOGIC
if not df.empty:
    
    # --- PYTHON FILTERING ---
    # 1. Filter by Status Note (The "Planned Maintenance" check)
    # We do this here instead of the API to be safe against case-sensitivity issues
    if 'status_notes' in df.columns:
        filtered_df = df[df['status_notes'].astype(str).str.contains("PLANNED", case=False, na=False)].copy()
    else:
        filtered_df = pd.DataFrame() # Should not happen, but safety first

    # 2. Parse Images
    if not filtered_df.empty:
        filtered_df['clean_image'] = filtered_df['media_url'].apply(get_clean_url)
        
        # 3. Filter for Valid Images
        viewable_df = filtered_df[filtered_df['clean_image'].notna()].copy()
        
        st.success(f"Found **{len(viewable_df)}** public images matching 'Planned Maintenance'.")
        
        if not viewable_df.empty:
            cols = st.columns(4)
            for i, row in enumerate(viewable_df.itertuples()):
                col = cols[i % 4]
                with col:
                    st.image(row.clean_image, use_container_width=True)
                    
                    # Metadata
                    date = str(getattr(row, 'closed_date', ''))[:10]
                    addr = str(getattr(row, 'address', 'SF')).split(',')[0]
                    
                    # The Purge Highlight
                    if date in ['2025-12-04', '2025-12-05']:
                         st.markdown(f"**📍 {addr}**")
                         st.markdown(":rotating_light: <span class='purge-badge'>BATCH PURGED</span>", unsafe_allow_html=True)
                         st.caption(f"Date: {date}")
                    else:
                         st.markdown(f"**📍 {addr}**")
                         st.caption(f"Closed: {date}")
        else:
            st.warning("Records found, but all contained private (Verint) links which cannot be displayed.")
    else:
        st.warning("No 'Planned Maintenance' closures found in the fetched batch.")
else:
    st.info("No records found matching filters.")
