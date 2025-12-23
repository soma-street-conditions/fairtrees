import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. Page Config
st.set_page_config(page_title="SF 311: The Purge Tracker", page_icon="📉", layout="wide")

# --- STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .stMarkdown p { font-size: 0.9rem; margin-bottom: 0px; }
        div.stButton > button { width: 100%; }
        .purge-stat { font-size: 2rem; font-weight: bold; color: #d32f2f; }
    </style>
""", unsafe_allow_html=True)

# 2. Session State
if 'limit' not in st.session_state:
    st.session_state.limit = 500

# Header
st.header("Bureau of Urban Forestry: The 'Planned Maintenance' Wall")
st.markdown("""
**Visualizing the Backlog:** This feed displays citizen reports of **Empty Tree Basins** that were closed with the status "Planned Maintenance".
""")
st.markdown("---")

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filters")
district_options = ["Citywide"] + [str(i) for i in range(1, 12)]
selected_district = st.sidebar.selectbox("Supervisor District", district_options, index=0)

# Limit Slider
st.sidebar.markdown("---")
st.session_state.limit = st.sidebar.slider("Records to Fetch", 100, 2000, 500, step=100)

# 3. Date & API Setup
# Look back 2 years to capture the full scope of the backlog that was purged
lookback_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# 4. ROBUST QUERY CONSTRUCTION
# We use SODA 2.0 syntax (SoQL)
# Key check: closed_date > lookback AND status contains "PLANNED"
where_clauses = [
    f"closed_date > '{lookback_date}'",
    "service_details = 'empty_tree_basin'",
    "upper(status_notes) LIKE '%PLANNED%'",
    "media_url IS NOT NULL"  # Ensure we only get rows with photos
]

# Add District Logic
if selected_district != "Citywide":
    where_clauses.append(f"supervisor_district = '{selected_district}'")

# Combine clauses
full_where = " AND ".join(where_clauses)

params = {
    "$where": full_where,
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
            st.error(f"API Error: {r.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame()

df = get_data(params)

# 6. Helper: Identify Image vs Portal Link
def get_image_info(media_item):
    if not media_item: return None, False
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not url: return None, False
    
    # Cloudinary = Publicly Viewable
    # Verint = Password Protected (Hidden)
    if 'cloudinary' in url:
        return url, True
    return url, False

# 7. Display Feed
if not df.empty:
    # --- STATISTICS SECTION ---
    # Calculate how many were part of the "Purge" (Dec 4-5)
    if 'closed_date' in df.columns:
        df['closed_dt'] = pd.to_datetime(df['closed_date'])
        purge_count = len(df[df['closed_dt'].dt.strftime('%Y-%m-%d').isin(['2025-12-04', '2025-12-05'])])
    else:
        purge_count = 0
        
    st.write(f"Showing **{len(df)}** closed reports with images.")
    if purge_count > 0:
        st.info(f"🚨 **{purge_count}** of these displayed tickets were closed during the December 4-5 Mass Purge.")

    # --- THE WALL ---
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        full_url, is_viewable = get_image_info(row.get('media_url'))
        
        # Display only if we have a valid, public image
        if full_url and is_viewable:
            col_index = display_count % 4
            
            with cols[col_index]:
                with st.container(border=True):
                    
                    # IMAGE
                    st.image(full_url, use_container_width=True)

                    # DATA
                    closed_date = row.get('closed_date', 'Unknown')[:10] # Get YYYY-MM-DD
                    address = row.get('address', 'Location N/A').split(',')[0]
                    map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
                    
                    st.markdown(f"**📍 [{address}]({map_url})**")
                    st.markdown(f"**Closed:** {closed_date}")
                    
                    # Highlight "Purge" dates visually
                    if closed_date in ['2025-12-04', '2025-12-05']:
                        st.markdown(":rotating_light: **BATCH CLOSED**")
                    
                    with st.expander("Details"):
                         st.caption(row.get('status_notes', ''))
            
            display_count += 1
            
    if display_count == 0:
        st.warning("Data found, but no images were publicly viewable (Most links are internal Verint links).")
        st.write("Raw Data Preview:", df.head())

else:
    st.info("No records found. Try increasing the 'Records to Fetch' slider or switching District to 'Citywide'.")
    st.caption(f"Debug Query: {full_where}")

# Footer
st.markdown("---")
st.caption("Data source: DataSF | 311 Cases")
