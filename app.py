import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURATION & CONSTANTS ---
st.set_page_config(page_title="SF Tree Basin Maintenance", page_icon="🌳", layout="wide")

API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"

SUPERVISOR_MAP = {
    "1": "1 - Connie Chan", "2": "2 - Stephen Sherrill", "3": "3 - Danny Sauter",
    "4": "4 - Alan Wong", "5": "5 - Bilal Mahmood", "6": "6 - Matt Dorsey",
    "7": "7 - Myrna Melgar", "8": "8 - Rafael Mandelman", "9": "9 - Jackie Fielder",
    "10": "10 - Shamann Walton", "11": "11 - Chyanne Chen"
}

# --- 2. STYLING ---
st.markdown("""
    <style>
        /* Tighten vertical spacing */
        div[data-testid="stVerticalBlock"] > div { gap: 0.1rem; }
        
        /* Unified font for card text */
        .card-text {
            font-family: "Source Sans Pro", sans-serif;
            font-size: 0.85rem;
            line-height: 1.3;
            color: #FAFAFA;
            margin: 0px;
        }
        
        /* Enforce uniform image heights */
        div[data-testid="stImage"] > img {
            object-fit: cover; 
            height: 200px; 
            width: 100%;
            border-radius: 4px;
        }
        
        /* Metrics/Table container styling */
        .metric-container {
            background-color: #0E1117; 
            border: 1px solid #303030;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---

@st.cache_data(ttl=600)
def load_data(district_id):
    eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
    
    select_cols = (
        "service_request_id, requested_datetime, closed_date, "
        "service_details, status_notes, address, media_url"
    )
    
    # Filter: Closed, PW, Tree Basin
    where_clause = (
        f"closed_date > '{eighteen_months_ago}' "
        "AND agency_responsible LIKE '%PW%' "
        "AND (upper(service_details) LIKE '%TREE_BASIN%')"
    )

    if district_id != "Citywide":
        where_clause += f" AND supervisor_district = '{district_id}'"

    params = {
        "$select": select_cols,
        "$where": where_clause,
        "$limit": 5000,
        "$order": "closed_date DESC"
    }

    try:
        r = requests.get(API_URL, params=params)
        r.raise_for_status()
        df = pd.DataFrame(r.json())
        if df.empty: return pd.DataFrame()

        df['requested_datetime'] = pd.to_datetime(df['requested_datetime'], errors='coerce')
        df['closed_date'] = pd.to_datetime(df['closed_date'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

def get_valid_image_url(media_item):
    if not media_item: return None
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not isinstance(url, str): return None
    clean_url = url.split('?')[0].lower()
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
        return url
    return None

def get_category(note):
    """Parses the first meaningful word from the status note."""
    if not isinstance(note, str):
        return "Unknown"
    
    note = note.strip()
    note_lower = note.lower()
    
    # specific handling to split 'Case' into useful buckets
    if note_lower.startswith("case is a duplicate"):
        return "Duplicate"
    if note_lower.startswith("case resolved"):
        return "Resolved"
    if note_lower.startswith("case transferred"):
        return "Transferred"
        
    # Default: take the first word (e.g., "Cancelled", "Administrative")
    return note.split(' ')[0].title()

# --- 4. MAIN APP ---

def main():
    st.header("SF Tree Basin Maintenance Tracker")
    
    # Filter Logic
    query_params = st.query_params
    url_district = query_params.get("district", "Citywide")
    
    district_list = ["Citywide"] + list(SUPERVISOR_MAP.values())
    default_idx = district_list.index(SUPERVISOR_MAP.get(url_district, "Citywide"))

    col_filter, _ = st.columns([1, 3])
    with col_filter:
        selected_label = st.selectbox("Supervisor District:", district_list, index=default_idx)

    rev_map = {v: k for k, v in SUPERVISOR_MAP.items()}
    rev_map["Citywide"] = "Citywide"
    selected_id = rev_map[selected_label]
    st.query_params["district"] = selected_id

    df = load_data(selected_id)

    if df.empty:
        st.warning("No records found.")
        return

    # --- Closure Reason Statistics ---
    # Apply category logic
    df['closure_reason'] = df['status_notes'].apply(get_category)
    
    # Group and Calculate
    stats = df['closure_reason'].value_counts().reset_index()
    stats.columns = ['Closure Reason', 'Count']
    stats['% of Cases'] = (stats['Count'] / len(df) * 100).map('{:.1f}%'.format)
    
    # Display Stats
    st.markdown("##### Closure Reasons Summary")
    with st.container():
        # Using a dataframe with hidden index for a cleaner look
        st.dataframe(
            stats, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Closure Reason": st.column_config.TextColumn("Reason"),
                "Count": st.column_config.NumberColumn("Total Cases"),
                "% of Cases": st.column_config.TextColumn("Percentage"),
            }
        )
    st.markdown("---")

    # --- Image Grid ---
    df['valid_image'] = df['media_url'].apply(get_valid_image_url)
    display_df = df.dropna(subset=['valid_image'])

    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(display_df.iterrows()):
        with cols[i % COLS_PER_ROW]:
            with st.container(border=True):
                # Image
                st.image(row['valid_image'], use_container_width=True)
                
                # Calculations
                opened = row['requested_datetime']
                closed = row['closed_date']
                
                opened_str = opened.strftime('%m/%d/%y') if pd.notnull(opened) else "?"
                closed_str = closed.strftime('%m/%d/%y') if pd.notnull(closed) else "?"
                
                days_diff = "?"
                if pd.notnull(opened) and pd.notnull(closed):
                    days_diff = (closed - opened).days
                
                # Text Content
                service = str(row.get('service_details', 'N/A')).replace('_', ' ').title()
                notes = str(row.get('status_notes', 'N/A'))
                
                addr = row.get('address', 'Location N/A').split(',')[0]
                map_url = f"https://www.google.com/maps/search/?api=1&query={addr.replace(' ', '+')}+San+Francisco"
                
                ticket_id = row['service_request_id']
                ticket_url = f"https://mobile311.sfgov.org/tickets/{ticket_id}"

                # Dense Text Block
                st.markdown(f"""
                    <p class="card-text"><b><a href="{map_url}" target="_blank" style="color: #60B4FF; text-decoration: none;">{addr}</a></b></p>
                    <p class="card-text">{opened_str} ➔ {closed_str} ({days_diff} days)</p>
                    <p class="card-text">Type: {service}</p>
                    <p class="card-text">Closure note: <a href="{ticket_url}" target="_blank" style="color: #60B4FF; text-decoration: none;">{notes}</a></p>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
