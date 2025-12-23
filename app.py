import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. Page Config
st.set_page_config(page_title="SF Urban Forestry Audit", page_icon="🌳", layout="wide")

# --- STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .stMarkdown p { font-size: 0.9rem; margin-bottom: 0px; }
        div.stButton > button { width: 100%; }
        .status-highlight {
            background-color: #f0f2f6;
            border-left: 3px solid #ff4b4b;
            padding: 4px 8px;
            font-family: monospace;
            font-size: 0.85rem;
            color: #31333F;
        }
    </style>
""", unsafe_allow_html=True)

# 2. Session State
if 'limit' not in st.session_state:
    st.session_state.limit = 500

# Header
st.header("Bureau of Urban Forestry: Case Closure Audit")
st.write("Live audit of 'Empty Tree Basin' requests administratively closed with the status 'Planned Maintenance'.")
st.markdown("---")

# 3. FILTERS
c1, c2 = st.columns([1, 1])

with c1:
    # District Filter
    # Map display name to API value
    dist_map = {"All Districts": None}
    for i in range(1, 12):
        dist_map[f"District {i}"] = str(float(i)) # API often stores these as "1.0", "2.0"
    
    selected_dist_label = st.selectbox("Supervisor District", list(dist_map.keys()), index=0)
    selected_dist_val = dist_map[selected_dist_label]

with c2:
    limit_opts = [500, 1000, 2000, 5000]
    limit = st.selectbox("Max Records to Audit", limit_opts, index=1)

# 4. API SETUP (The Fix: Using the SODA 2.1 Endpoint)
# This endpoint accepts a full SQL string ("SoQL") which is more robust
BASE_URL = "https://data.sfgov.org/api/v3/views/vw6y-z8j6/query.json"

# Calculate Lookback (2 Years)
lookback_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%S')

# Construct the SQL Query
# Note: We select specific columns to keep the payload light
query_cols = "service_request_id, closed_date, status_notes, media_url, address, supervisor_district"

# Base WHERE Clause
where_sql = f"""
    service_details = 'empty_tree_basin' 
    AND status = 'Closed' 
    AND closed_date > '{lookback_date}' 
    AND media_url IS NOT NULL
    AND (lower(status_notes) LIKE '%planned%' OR lower(status_notes) LIKE '%prop-e%')
"""

if selected_dist_val:
    # Handle the weird float/int formatting in SF data (e.g. '6' vs '6.0')
    where_sql += f" AND (supervisor_district = '{selected_dist_val}' OR supervisor_district = '{selected_dist_val}.0')"

# Final Query String
soql_query = f"SELECT {query_cols} WHERE {where_sql} ORDER BY closed_date DESC LIMIT {limit}"

# 5. FETCH DATA
@st.cache_data(ttl=300)
def get_data(query_string):
    try:
        # Pass the SoQL query in the 'query' parameter
        r = requests.get(BASE_URL, params={'query': query_string})
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        else:
            st.error(f"API Error: {r.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame()

df = get_data(soql_query)

# 6. IMAGE HELPER (Adapted from SOMA Streets)
def get_image_info(media_item):
    """
    Robust parser to handle the messy media_url field.
    Returns: (clean_url, is_viewable_boolean)
    """
    if not media_item: return None, False
    
    url = None
    
    # 1. Handle Dictionary Objects (Common in SODA 2.1)
    if isinstance(media_item, dict):
        url = media_item.get('url')
    
    # 2. Handle Strings (and stringified JSON)
    elif isinstance(media_item, str):
        # Check if it's a stringified dict: "{'url': '...'}"
        if media_item.strip().startswith('{') and 'url' in media_item:
            try:
                import ast
                parsed = ast.literal_eval(media_item)
                url = parsed.get('url')
            except:
                pass
        
        # If parsing failed or it wasn't a dict, assume it's a direct link
        if not url:
            url = media_item

    if not url: return None, False

    # 3. Clean and Validate
    clean_url = url.split('?')[0].lower()
    
    # FILTER: Public Images Only
    # Verint links require a password, so we hide them to avoid broken images.
    # Cloudinary links are public.
    if 'cloudinary' in clean_url:
        return url, True
        
    return url, False

# 7. DISPLAY FEED
if not df.empty:
    st.write(f"Found **{len(df)}** records matching query.")
    
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        full_url, is_viewable = get_image_info(row.get('media_url'))
        
        # STRICT FILTER: Only show records with viewable (Cloudinary) images
        if full_url and is_viewable:
            col_index = display_count % 4
            
            with cols[col_index]:
                with st.container(border=True):
                    
                    # IMAGE
                    st.image(full_url, use_container_width=True)

                    # METADATA
                    closed_date = row.get('closed_date', 'Unknown')[:10]
                    address = row.get('address', 'Location N/A').split(',')[0]
                    map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
                    
                    st.markdown(f"**[{address}]({map_url})**")
                    st.caption(f"Closed: {closed_date}")
                    
                    # Status Note Highlight
                    note = row.get('status_notes', '')
                    # Truncate really long notes for UI cleanliness
                    if len(note) > 100:
                        note = note[:97] + "..."
                    
                    if note:
                        st.markdown(f"<div class='status-highlight'>{note}</div>", unsafe_allow_html=True)
            
            display_count += 1
    
    if display_count == 0:
        st.warning("Records found, but all images were hosted on the private Verint portal (cannot be displayed publicly).")
        st.caption("Try increasing the record limit to look further back for older Mobile app submissions.")

else:
    st.info("No records found matching these criteria.")

# Footer
st.markdown("---")
st.caption(f"Data source: DataSF | 311 Cases | Query: {soql_query}")
