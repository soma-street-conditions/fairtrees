import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. Page Config
st.set_page_config(page_title="SF Streets: Maintenance", page_icon="🚧", layout="wide")

# --- STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .stMarkdown p { font-size: 0.9rem; margin-bottom: 0px; }
        div.stButton > button { width: 100%; }
        .stCaption a { text-decoration: underline; color: #1f77b4; }
        
        /* Stats Text: Enforce White Color */
        .metric-container {
            background-color: transparent;
            padding: 10px 0px;
        }
    </style>
    <meta name="robots" content="noindex, nofollow">
""", unsafe_allow_html=True)

# 2. Header
st.header("SF Citywide: Planned Maintenance Cancellations")
st.write("Visualizing 311 reports closed as 'Cancelled - Planned Maintenance' by Public Works.")
st.caption("Filters: 'backfill_tree_basin' and 'empty_tree_basin' only.")

# --- SUPERVISOR MAPPING ---
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

reverse_supervisor_map = {v: k for k, v in supervisor_map.items()}
reverse_supervisor_map["Citywide"] = "Citywide"
district_options = ["Citywide"] + list(supervisor_map.values())

# --- FILTER UI ---
query_params = st.query_params
url_district_id = query_params.get("district", "Citywide")
current_label = supervisor_map.get(url_district_id, "Citywide")

col_filter, col_spacer = st.columns([1, 3])
with col_filter:
    selected_label = st.selectbox(
        "Filter by Supervisor District:", 
        district_options,
        index=district_options.index(current_label)
    )

selected_id = reverse_supervisor_map.get(selected_label, "Citywide")

if selected_id == "Citywide":
    if "district" in st.query_params:
        del st.query_params["district"]
else:
    st.query_params["district"] = selected_id

st.markdown("---")

# 3. Setup
eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
base_url = "https://data.sfgov.org/resource/vw6y-z8j6.json"

# --- API QUERY ---
# Logic: Fetch ALL closed cases for 'tree_basin' regardless of status.
# We use strict equality in the API to ensure we get exactly what we want.
details_filter = "(service_details = 'backfill_tree_basin' OR service_details = 'empty_tree_basin')"

params = {
    "$where": f"closed_date > '{eighteen_months_ago}' AND agency_responsible LIKE '%PW%' AND {details_filter}",
    "$limit": 50000, # Fetch everything
    "$order": "closed_date DESC"
}

if selected_id != "Citywide":
    params["$where"] += f" AND supervisor_district = '{selected_id}'"

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

# --- CALCULATE STATS ---
total_records = 0
cancelled_count = 0
percentage = 0.0

if not df.empty:
    total_records = len(df)
    
    # Identify Cancellations
    # We look for "Cancelled - Planned Maintenance" in the status notes
    if 'status_notes' in df.columns:
        cancelled_mask = df['status_notes'].astype(str) == 'Cancelled - Planned Maintenance'
        cancelled_count = len(df[cancelled_mask])
        
        # Filter the DataFrame for display (User likely only wants to see the cancelled ones in the grid)
        # If you want to see ALL rows in the grid, comment out the next line.
        display_df = df[cancelled_mask].copy() 
    else:
        display_df = pd.DataFrame()

    if total_records > 0:
        percentage = (cancelled_count / total_records) * 100
else:
    display_df = pd.DataFrame()

# --- DISPLAY STATS (White Text) ---
st.markdown(
    f"""
    <div class='metric-container'>
        <span style='font-size: 1.1rem; font-weight: 500; color: #FFFFFF !important;'>
            Found <b>{total_records:,}</b> records total (backfill/empty basin only).<br>
            <b>{cancelled_count:,}</b> were "Cancelled - Planned Maintenance" ({percentage:.1f}% of total).
        </span>
    </div>
    """, 
    unsafe_allow_html=True
)
st.markdown("---")

# 4. Helper: Identify Image
def get_image_info(media_item):
    if not media_item: return None, False
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not url: return None, False
    clean_url = url.split('?')[0].lower()
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
        return url, True
    return url, False

# 5. Display Feed
if not display_df.empty:
    cols = st.columns(4)
    display_count = 0
    
    # Identify the details column
    possible_cols = ['service_details', 'request_details', 'service_subtype']
    details_col = next((c for c in possible_cols if c in display_df.columns), 'service_details')

    for index, row in display_df.iterrows():
        full_url, is_viewable = get_image_info(row.get('media_url'))
        
        if full_url and is_viewable:
            col_index = display_count % 4
            with cols[col_index]:
                with st.container(border=True):
                    st.image(full_url, use_container_width=True)

                    # --- DATA PROCESSING ---
                    try:
                        opened_dt = pd.to_datetime(row.get('requested_datetime'))
                        closed_dt = pd.to_datetime(row.get('closed_date'))
                        opened_str = opened_dt.strftime('%m/%d/%y')
                        closed_str = closed_dt.strftime('%m/%d/%y')
                        days_open = (closed_dt - opened_dt).days
                    except:
                        opened_str, closed_str, days_open = "?", "?", "?"

                    details = row.get(details_col, 'N/A')
                    status_notes = row.get('status_notes', 'Closed')
                    
                    # Link Generation
                    ticket_id = row.get('service_request_id')
                    if ticket_id:
                        ticket_url = f"https://mobile311.sfgov.org/tickets/{ticket_id}"
                        notes_display = f"[{status_notes}]({ticket_url})"
                    else:
                        notes_display = status_notes

                    address = row.get('address', 'Location N/A')
                    short_address = address.split(',')[0]
                    map_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"

                    # --- RENDER TEXT ---
                    st.markdown(f"[{short_address}]({map_url})")
                    
                    st.markdown(f"Opened {opened_str}, Closed {closed_str}")
                    st.markdown(f"Open {days_open} days")
                    
                    st.caption(f"**Request Details:** {details}")
                    st.caption(f"**Status Notes:** {notes_display}")
            
            display_count += 1
            
    if display_count == 0:
        st.info("No viewable images found for the cancelled records.")
    
else:
    if selected_id != "Citywide":
        st.warning(f"No records found for Supervisor District {selected_label} matching these criteria.")
    else:
        st.warning("No records found matching criteria.")

# Footer
st.markdown("---")
st.caption("Data source: DataSF | Open Data Portal")
