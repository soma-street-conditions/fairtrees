import streamlit as st
import pandas as pd
import requests
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
        .block-container { padding-top: 2rem; }
        div[data-testid="column"] { background-color: #f9f9f9; border-radius: 8px; padding: 10px; }
        img { border-radius: 5px; }
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
    districts = ["Citywide"] + [str(i) for i in range(1, 12)]
    selected_district = st.selectbox("Supervisor District", districts, index=0)

with c2:
    # Limit Filter
    # I increased the defaults because we are filtering out so many private images
    limit = st.selectbox("Max Records to Check", [500, 1000, 2000, 5000], index=1)

# 4. DATA FETCHING
API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# Look back 2 years
lookback = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%S')

# Query Construction
where_query = f"service_details = 'empty_tree_basin' AND status = 'Closed' AND upper(status_notes) LIKE '%PLANNED%' AND closed_date > '{lookback}' AND media_url IS NOT NULL"

if selected_district != "Citywide":
    where_query += f" AND supervisor_district = '{selected_district}'"

params = {
    "$where": where_query,
    "$order": "closed_date DESC",
    "$limit": limit
}

@st.cache_data(ttl=300)
def fetch_and_clean_data(params):
    try:
        r = requests.get(API_URL, params=params)
        if r.status_code == 200:
            df = pd.DataFrame(r.json())
            
            # --- CRITICAL STEP: FILTER FOR CLOUDINARY ONLY ---
            if not df.empty and 'media_url' in df.columns:
                # Convert media_url column to string to handle dicts/json
                df['media_url'] = df['media_url'].astype(str)
                
                # Filter: Keep ONLY rows where URL contains "cloudinary"
                # This drops all Verint (private) and text-only rows
                clean_df = df[df['media_url'].str.contains("cloudinary", case=False, na=False)].copy()
                
                # Extract the clean URL
                # The API often returns: {'url': 'http...'} or just 'http...'
                # Since we know it contains 'cloudinary', we can just clean the string
                def extract_url(val):
                    # If it looks like a dict string, try to grab the url
                    if "'url':" in val or '"url":' in val:
                        # Quick dirty parse to avoid JSON overhead if possible
                        try:
                            return val.split("'url': '")[1].split("'")[0]
                        except:
                            try:
                                return val.split('"url": "')[1].split('"')[0]
                            except:
                                return val # Return as is if parse fails
                    return val
                
                clean_df['clean_image'] = clean_df['media_url'].apply(extract_url)
                return clean_df
            
            return pd.DataFrame() # Return empty if no columns matches
            
    except Exception as e:
        return pd.DataFrame()
    
    return pd.DataFrame()

# Load Data
with st.spinner(f"Scanning the last {limit} records for public images..."):
    df = fetch_and_clean_data(params)

# 5. MAIN DISPLAY
if not df.empty:
    st.success(f"Found **{len(df)}** publicly viewable images.")
    
    # Grid Layout (4 columns)
    cols = st.columns(4)
    
    for i, row in enumerate(df.itertuples()):
        col = cols[i % 4]
        with col:
            # Display Image
            st.image(row.clean_image, use_container_width=True)
            
            # Details
            closed_date = str(getattr(row, 'closed_date', ''))[:10]
            addr = str(getattr(row, 'address', 'SF')).split(',')[0]
            
            # Visual Flag for the "Purge" Dates
            if closed_date in ['2025-12-04', '2025-12-05']:
                st.markdown(f"**📍 {addr}**")
                st.error(f"PURGED: {closed_date}")
            else:
                st.markdown(f"**📍 {addr}**")
                st.caption(f"Closed: {closed_date}")

else:
    st.warning("No public images found.")
    st.markdown("""
    **Why?** It appears all recent tickets matching your criteria contain images hosted on the City's internal **Verint** system, which blocks public access. 
    
    Try increasing the **"Max Records"** filter to 2000+ to look further back in time for older Cloudinary images.
    """)
