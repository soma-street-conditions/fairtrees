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
        
        /* Stats Text: White */
        .metric-text { 
            font-size: 1.1rem; 
            font-weight: 500; 
            color: white; 
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

# --- HELPER: ROBUST FILTERING ---
def filter_dataframe(df):
    """
    Python-side filtering to guarantee accuracy.
    Checks multiple potential column names for the request details.
    """
    if df.empty: return df
    
    # 1. Identify the 'Details' column
    # API usually uses 'service_details', but sometimes 'request_details' or 'service_subtype'
    possible_cols = ['service_details', 'request_details', 'service_subtype']
    target_col = next((c for c in possible_cols if c in df.columns), None)
    
    if not target_col:
        return pd.DataFrame() # Can't filter if column missing
    
    # 2. Convert to string and lowercase
    df[target_col] = df[target_col].astype(str).str.lower()
    
    # 3. Strict Inclusion List
    targets = ['backfill_tree_basin', 'empty_tree_basin']
    
    # Filter rows where the column contains either target string
    mask = df[target_col].isin(targets)
    return df[mask]

# 4. FETCH ALL STATS DATA (The Denominator)
# We fetch metadata for ALL matching cases (with/without images) to get the total count.
# We use a 'LIKE' query to be nice to the API, then strict filter in Python.
stats_where = (
    f"closed_date > '{eighteen_months_ago}' "
    f"AND agency_responsible LIKE '%PW%' "
    f"AND service_details LIKE '%tree_basin%'" # Efficient API pre-filter
)

if selected_id != "Citywide":
    stats_where += f" AND supervisor_district = '{selected_id}'"

@st.cache_data(ttl=300)
def get_stats_data(where_clause):
    # Fetch enough columns to filter and count status
    params = {
        "$select": "closed_date, status_notes, service_details, service_subtype",
        "$where": where_clause,
        "$limit": 50000 # Effectively no limit
    }
    try:
        r = requests.get(base_url, params=params)
        if r.status_code == 200:
            raw_df = pd.DataFrame(r.json())
            return filter_dataframe(raw_df)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

stats_df = get_stats_data(stats_where)

# --- CALCULATE STATS ---
total_records = 0
cancelled_count = 0
percentage = 0.0

if not stats_df.empty:
    total_records = len(stats_df)
    
    # Count specific cancellations
    # Normalize status_notes just in case
    if 'status_notes' in stats_df.columns:
        cancelled_mask = stats_df['status_notes'].astype(str) == 'Cancelled - Planned Maintenance'
        cancelled_count = len(stats_df[cancelled_mask])
    
    if total_records > 0:
        percentage = (cancelled_count / total_records) * 100

st.markdown(
    f"""
    <div class='metric-text'>
        Found <b>{total_records:,}</b> records total (backfill/empty basin only).<br>
        <b>{cancelled_count:,}</b> were "Cancelled - Planned Maintenance" ({percentage:.1f}% of total).
    </div>
    """, 
    unsafe_allow_html=True
)
st.markdown("---")

# 5. FETCH FEED DATA (The Images)
# Stricter query: Must be Cancelled AND have Image
feed_where = stats_where + " AND status_notes = 'Cancelled - Planned Maintenance' AND media_url IS NOT NULL"

@st.cache_data(ttl=300)
def get_feed_data(where_clause):
    params = {
        "$where": where_clause,
        "$order": "closed_date DESC",
        "$limit": 50000 # No pagination
    }
    try:
        r = requests.get(base_url, params=params)
        if r.status_code == 200:
            raw_df = pd.DataFrame(r.json())
            return filter_dataframe(raw_df)
        else:
            st.error(f"API Error {r.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

df = get_feed_data(feed_where)

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
    
    # Identify the correct column for details again for display
    possible_cols = ['service_details', 'request_details', 'service_subtype']
    details_col = next((c for c in possible_cols if c in df.columns), 'service_details')

    for index, row in df.iterrows():
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
        st.info("Records found, but no viewable images could be extracted.")
    
else:
    if selected_id != "Citywide":
        st.warning(f"No records found for Supervisor District {selected_label} matching these criteria.")
    else:
        st.warning("No records found matching criteria.")

# Footer
st.markdown("---")
st.caption("Data source: DataSF | Open Data Portal")
