import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. Page Config
st.set_page_config(page_title="SF Streets: Maintenance", page_icon="🚧", layout="wide")

# --- NO CRAWL & STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .stMarkdown p { font-size: 0.9rem; margin-bottom: 0px; }
        div.stButton > button { width: 100%; }
    </style>
    <meta name="robots" content="noindex, nofollow">
""", unsafe_allow_html=True)

# 2. Session State for "Load More"
if 'limit' not in st.session_state:
    st.session_state.limit = 800

# Header
st.header("SF Citywide: Planned Maintenance Cancellations")
st.write("Visualizing 311 reports closed as 'Cancelled - Planned Maintenance' by Public Works (Citywide).")
st.markdown("---")

# 3. Date & API Setup
# 18 months lookback
eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# 4. Query
# UPDATES:
# - REMOVED: analysis_neighborhood = 'South of Market'
# - KEPT: closed_date > 18 months ago, Media exists, Cancelled Maintenance, Agency is PW
params = {
    "$where": f"closed_date > '{eighteen_months_ago}' AND media_url IS NOT NULL AND status_notes = 'Cancelled - Planned Maintenance' AND responsible_agency LIKE '%PW%'",
    "$order": "closed_date DESC",
    "$limit": st.session_state.limit
}

# 5. Fetch Data
@st.cache_data(ttl=300)
def get_data(query_limit):
    try:
        r = requests.get(base_url, params=params)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        else:
            return pd.DataFrame()
    except:
        return pd.DataFrame()

df = get_data(st.session_state.limit)

# 6. Helper: Identify Image vs Portal Link
def get_image_info(media_item):
    if not media_item: return None, False
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not url: return None, False
    clean_url = url.split('?')[0].lower()
    
    # Case A: Standard Image (Public Cloud)
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return url, True
        
    # Case B: Verint Portal or other Web Links
    return url, False

# 7. Display Feed
if not df.empty:
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        full_url, is_viewable = get_image_info(row.get('media_url'))
        
        # STRICT FILTER: Only show records with viewable images
        if full_url and is_viewable:
            col_index = display_count % 4
            
            with cols[col_index]:
                with st.container(border=True):
                    
                    # --- STANDARD IMAGE COMPONENT ---
                    st.image(full_url, use_container_width=True)

                    # Metadata
                    if 'closed_date' in row:
                        date_str = pd.to_datetime(row['closed_date']).strftime('%b %d, %Y')
                    else:
                        date_str = "Open"
                    
                    # Neighborhood label (useful since we removed the global filter)
                    neighborhood = row.get('analysis_neighborhood', 'Unknown Neighborhood')
                    address = row.get('address', 'Location N/A')
                    short_address = address.split(',')[0] 
                    map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
                    
                    st.markdown(f"**{neighborhood}**")
                    st.markdown(f"Closed: {date_str} | [{short_address}]({map_url})")
                    st.caption(f"ID: {row.get('service_request_id', 'N/A')}")
            
            display_count += 1
            
    if display_count == 0:
        st.info("No viewable images found for these criteria.")
    
    # Load More Button
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button(f"Load More Records (Current: {st.session_state.limit})"):
            st.session_state.limit += 300
            st.rerun()

else:
    st.info("No records found matching 'Cancelled - Planned Maintenance' in the last 18 months.")

# Footer & Methodology
st.markdown("---")
st.caption("Data source: [DataSF | Open Data Portal](https://data.sfgov.org/City-Infrastructure/311-Cases/vw6y-z8j6/about_data)")

with st.expander("Methodology & Notes"):
    st.markdown("""
    **Filters Applied:**
    * **Neighborhood:** Citywide (All Neighborhoods).
    * **Status:** Closed within the last 18 months.
    * **Agency:** Public Works (PW).
    * **Resolution:** 'Cancelled - Planned Maintenance'.
    
    **Note:** This feed only shows reports that include user-submitted images.
    """)
