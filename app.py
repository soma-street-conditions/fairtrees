import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. Page Config
st.set_page_config(page_title="SF 311 Status Tracker", page_icon="🌳", layout="wide")

# --- STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .stMarkdown p { font-size: 0.9rem; margin-bottom: 0px; }
        div.stButton > button { width: 100%; }
    </style>
    <meta name="robots" content="noindex, nofollow">
""", unsafe_allow_html=True)

# 2. Session State
if 'limit' not in st.session_state:
    st.session_state.limit = 400

# Header
st.header("Bureau of Urban Forestry: 311 Case Closure Feed")
st.markdown("""
**Data Source:** Live feed of 'Empty Tree Basin' requests closed by the Department of Public Works.
""")
st.markdown("---")

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filters")

# District Filter
district_options = ["Citywide"] + [str(i) for i in range(1, 12)]
selected_district = st.sidebar.selectbox("Supervisor District", district_options, index=0)

# Limit Slider
st.sidebar.markdown("---")
st.session_state.limit = st.sidebar.slider("Max Records to Load", 100, 2000, 400, step=100)


# 3. Date & API Setup
two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# 4. Query Construction
# Base Where Clause
where_clause = f"service_details = 'empty_tree_basin' AND status = 'Closed' AND requested_datetime > '{two_years_ago}' AND media_url IS NOT NULL"

# Add District Logic
if selected_district != "Citywide":
    where_clause += f" AND supervisor_district = '{selected_district}'"

params = {
    "$where": where_clause,
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

# Pass params directly to function so caching works correctly when filters change
df = get_data(params)

# 6. Helper: Identify Image vs Portal Link
def get_image_info(media_item):
    if not media_item: return None, False
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not url: return None, False
    
    # Only allow Cloudinary (Public) images. 
    if 'cloudinary' in url:
        return url, True
        
    return url, False

# 7. Display Feed
if not df.empty:
    st.write(f"Showing **{len(df)}** most recently closed reports for **{selected_district}**.")
    
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        # Get the actual data fields
        notes = str(row.get('status_notes', 'No notes provided'))
        
        full_url, is_viewable = get_image_info(row.get('media_url'))
        
        # STRICT FILTER: Only show records with viewable images
        if full_url and is_viewable:
            col_index = display_count % 4
            
            with cols[col_index]:
                with st.container(border=True):
                    
                    # IMAGE
                    st.image(full_url, use_container_width=True)

                    # METADATA
                    if 'closed_date' in row:
                        closed_str = pd.to_datetime(row['closed_date']).strftime('%b %d, %Y')
                    else:
                        closed_str = "Unknown"
                    
                    address = row.get('address', 'Location N/A')
                    short_address = address.split(',')[0] 
                    map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
                    
                    # District Badge (if Citywide view)
                    dist_badge = ""
                    if selected_district == "Citywide":
                        d_val = row.get('supervisor_district', '?')
                        dist_badge = f" [D{d_val}]"

                    # The Data Fields
                    st.markdown(f"**📍 [{short_address}]({map_url})**{dist_badge}")
                    st.markdown(f"Closed: {closed_str}")
                    
                    # DYNAMIC STATUS NOTE
                    st.caption("Official Closure Reason:")
                    st.code(notes, language="text")
            
            display_count += 1
            
    if display_count == 0:
        st.info("No publicly viewable images found in this batch.")
    
    # Load More Button logic moved to sidebar slider for cleaner UI
    
else:
    st.info("No records found matching these criteria.")

# Footer
st.markdown("---")
st.caption("Data source: DataSF | 311 Cases")
