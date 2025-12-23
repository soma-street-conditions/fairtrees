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
    st.session_state.limit = 2000

# Header
st.header("SF Citywide: Planned Maintenance Cancellations")
st.write("Visualizing 311 reports closed as 'Cancelled - Planned Maintenance' by Public Works (Citywide).")
st.markdown("---")

# 3. Date Setup
eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# 4. API Query
# Broad fetch: Get closed items with images. We will filter the rest in Python.
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

            # --- SMART COLUMN DETECTION ---
            # The API column names can vary. We search for the right ones.
            
            # 1. Find the 'Agency' column (looks for 'agency' in column name)
            agency_col = next((col for col in raw_df.columns if 'agency' in col.lower()), None)
            
            # 2. Find the 'Status Notes' column (looks for 'notes' in column name)
            notes_col = next((col for col in raw_df.columns if 'notes' in col.lower()), 'status_notes')

            if not agency_col:
                st.error(f"Could not find an 'Agency' column. Available columns: {raw_df.columns.tolist()}")
                return pd.DataFrame()

            # --- PYTHON FILTERING ---
            # Ensure columns are strings to avoid errors
            raw_df[agency_col] = raw_df[agency_col].astype(str)
            raw_df[notes_col] = raw_df[notes_col].astype(str)

            # Filter: 
            # 1. Agency has 'PW' (Matches 'PW - Urban Forestry' from your CSV)
            # 2. Notes has 'Planned Maintenance'
            filtered_df = raw_df[
                (raw_df[agency_col].str.contains('PW', case=False, na=False)) & 
                (raw_df[notes_col].str.contains('Planned Maintenance', case=False, na=False))
            ]
            
            # Save the detected column names to the dataframe for display loop to use
            filtered_df._agency_col_name = agency_col
            filtered_df._notes_col_name = notes_col
            
            return filtered_df
        else:
            st.error(f"API Request Failed: {r.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Detailed Error: {e}")
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
    
    # Retrieve the detected column names (defaults if lost)
    notes_col = getattr(df, '_notes_col_name', 'status_notes')
    
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
                    
                    # Display the note we filtered on
                    note_text = row.get(notes_col, '')
                    st.caption(f"Note: {note_text[:60]}...")
            
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
    st.warning("No records found. If this persists, the API might be temporarily down or returning empty data.")

# Footer
st.markdown("---")
st.caption("Data source: DataSF | Open Data Portal")
