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
    st.session_state.limit = 1000

# Header
st.header("SF Citywide: Planned Maintenance Cancellations")
st.write("Visualizing 311 reports closed as 'Cancelled - Planned Maintenance' by Public Works.")

# --- SUPERVISOR MAPPING ---
# Maps District ID -> Display Name
supervisor_map = {
    "1": "1 - Connie Chan",
    "2": "2 - Stephen Sherrill",
    "3": "3 - Danny Sauter",
    "4": "4 - Alan Wong",
    "5": "5 - Bilal Mahmood",
    "6": "6 - Matt Dorsey",
    "7": "7 - Myrna Melgar",
    "8": "8 - Rafael Mandelman",
    "9": "9 - Jackie Fielder",
    "10": "10 - Shamann Walton",
    "11": "11 - Chyanne Chen"
}

# Create a reverse map for lookups (Display Name -> District ID)
reverse_supervisor_map = {v: k for k, v in supervisor_map.items()}
reverse_supervisor_map["Citywide"] = "Citywide"

# Options for the dropdown
district_options = ["Citywide"] + list(supervisor_map.values())

# --- FILTER LOGIC ---

# 1. Check URL for existing selection (e.g. ?district=6)
query_params = st.query_params
url_district_id = query_params.get("district", "Citywide")

# 2. Determine the Label to show in the dropdown based on the ID in the URL
#    If ID is "6", we find "6 - Matt Dorsey". Default to "Citywide".
current_label = supervisor_map.get(url_district_id, "Citywide")

# 3. Create the Dropdown
col_filter, col_spacer = st.columns([1, 3])
with col_filter:
    selected_label = st.selectbox(
        "Filter by Supervisor District:", 
        district_options,
        index=district_options.index(current_label)
    )

# 4. Get the ID for the URL and API (e.g. "6 - Matt Dorsey" -> "6")
selected_id = reverse_supervisor_map.get(selected_label, "Citywide")

# 5. Update URL
if selected_id == "Citywide":
    if "district" in st.query_params:
        del st.query_params["district"]
else:
    st.query_params["district"] = selected_id

st.markdown("---")

# 3. Date Setup
eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# 4. API Query
# We filter by the ID (e.g., '6'), not the full name string
where_clause = f"closed_date > '{eighteen_months_ago}' AND media_url IS NOT NULL AND status_notes = 'Cancelled - Planned Maintenance' AND agency_responsible LIKE '%PW%'"

if selected_id != "Citywide":
    where_clause += f" AND supervisor_district = '{selected_id}'"

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
            df = pd.DataFrame(r.json())
            return df
        else:
            st.error(f"API Error {r.status_code}: {r.text}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame()

df = get_data(params)

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
    cols = st.columns(4)
    display_count = 0
    
    for index, row in df.iterrows():
        full_url, is_viewable = get_image_info(row.get('media_url'))
        
        if full_url and is_viewable:
            col_index = display_count % 4
            with cols[col_index]:
                with st.container(border=True):
                    st.image(full_url, use_container_width=True)

                    # --- DATA PROCESSING ---
                    # 1. Dates
                    try:
                        opened_dt = pd.to_datetime(row.get('requested_datetime'))
                        closed_dt = pd.to_datetime(row.get('closed_date'))
                        
                        opened_str = opened_dt.strftime('%m/%d/%y')
                        closed_str = closed_dt.strftime('%m/%d/%y')
                        
                        # Calculate days open
                        days_open = (closed_dt - opened_dt).days
                    except:
                        opened_str = "?"
                        closed_str = "?"
                        days_open = "?"

                    # 2. Details
                    # API field is often 'service_details' or 'request_details'
                    details = row.get('service_details', row.get('request_details', 'N/A'))
                    status_notes = row.get('status_notes', '')

                    # 3. Address
                    address = row.get('address', 'Location N/A')
                    short_address = address.split(',')[0]
                    map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"

                    # --- RENDER TEXT ---
                    st.markdown(f"Opened {opened_str}, Closed {closed_str}")
                    st.markdown(f"Open {days_open} days")
                    
                    # Using caption for dense text blocks to keep it clean
                    st.caption(f"**Request Details:** {details}")
                    st.caption(f"**Status Notes:** {status_notes}")
                    
                    st.markdown(f"[{short_address}]({map_url})")
            
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
    if selected_id != "Citywide":
        st.warning(f"No records found for Supervisor District {selected_label} matching these criteria.")
    else:
        st.warning("No records found matching 'Cancelled - Planned Maintenance' for PW in the last 18 months.")

# Footer
st.markdown("---")
st.caption("Data source: DataSF | Open Data Portal")
