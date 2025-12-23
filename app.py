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

# 2. Session State
if 'limit' not in st.session_state:
    st.session_state.limit = 2000  # Increased limit to ensure we catch enough rows before filtering

# Header
st.header("SF Citywide: Planned Maintenance Cancellations")
st.write("Visualizing 311 reports closed as 'Cancelled - Planned Maintenance' by Public Works (Citywide).")
st.markdown("---")

# 3. Date Setup
eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# 4. API Query (BROADER)
# We removed the strict 'status_notes' check from the API call.
# We fetch ALL closed reports with images from the last 18 months.
params = {
    "$where": f"closed_date > '{eighteen_months_ago}' AND media_url IS NOT NULL",
    "$order": "closed_date DESC",
    "$limit": st.session_state.limit
}

# 5. Fetch & Filter Data
@st.cache_data(ttl=300)
def get_data(query_limit):
    try:
        r = requests.get(base_url, params=params)
        if r.status_code == 200:
            raw_df = pd.DataFrame(r.json())
            
            if raw_df.empty:
                return pd.DataFrame()

            # --- PYTHON FILTERING (More Robust) ---
            # 1. Agency must contain 'PW'
            # 2. Status Notes must contain 'Planned Maintenance' (case insensitive)
            
            # Normalize columns to string to avoid errors
            raw_df['responsible_agency'] = raw_df['responsible_agency'].astype(str)
            raw_df['status_notes'] = raw_df['status_notes'].astype(str)

            filtered_df = raw_df[
                (raw_df['responsible_agency'].str.contains('PW', case=False, na=False)) & 
                (raw_df['status_notes'].str.contains('Planned Maintenance', case=False, na=False))
            ]
            
            return filtered_df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"API Error: {e}")
        return pd.DataFrame()

df = get_data(st.session_state.limit)

# 6. Helper: Identify Image
def get_image_info(media_item):
    if not media_item: return None, False
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not url: return None, False
    clean_url = url.split('?')[0].lower()
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return url, True
    return url, False

# 7. Display Feed
if not df.empty:
    st.success(f"Found {len(df)} records matching criteria.")
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        full_url, is_viewable = get_image_info(row.get('media_url'))
        
        if full_url and is_viewable:
            col_index = display_count % 4
            with cols[col_index]:
                with st.container(border=True):
                    st.image(full_url, use_container_width=True)

                    if 'closed_date' in row:
                        date_str = pd.to_datetime(row['closed_date']).strftime('%b %d, %Y')
                    else:
                        date_str = "Open"
                    
                    neighborhood = row.get('analysis_neighborhood', 'Unknown Neighborhood')
                    address = row.get('address', 'Location N/A')
                    short_address = address.split(',')[0] 
                    map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
                    
                    st.markdown(f"**{neighborhood}**")
                    st.markdown(f"Closed: {date_str}")
                    st.markdown(f"[{short_address}]({map_url})")
                    # Displaying the status note to confirm the match
                    st.caption(f"Note: {row.get('status_notes', '')[:50]}...")
            
            display_count += 1
            
    if display_count == 0:
        st.info("Records found, but no viewable images could be extracted.")
    
    # Load More
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button(f"Load More Records (Current Limit: {st.session_state.limit})"):
            st.session_state.limit += 500
            st.rerun()

else:
    st.warning("No records found. Try increasing the 'limit' in the code or check if the API is returning data.")

# Footer
st.markdown("---")
st.caption("Data source: DataSF | Open Data Portal")
