import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURATION & CONSTANTS ---
st.set_page_config(page_title="SF Streets: Maintenance", page_icon="🚧", layout="wide")

API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"

SUPERVISOR_MAP = {
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

# --- 2. STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.2rem; }
        .metric-container {
            background-color: #0E1117; /* Dark theme background */
            border: 1px solid #303030;
            border-radius: 5px;
            padding: 15px;
            text-align: center;
            margin-bottom: 20px;
        }
        .metric-text {
            font-size: 1.1rem;
            color: #FFFFFF;
            line-height: 1.6;
        }
        /* Make images fill their container nicely */
        div[data-testid="stImage"] > img {
            object-fit: cover; 
            height: 200px; /* Enforce uniform height */
            width: 100%;
        }
    </style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---

def get_supervisor_options():
    return ["Citywide"] + list(SUPERVISOR_MAP.values())

def get_reverse_supervisor_map():
    rev = {v: k for k, v in SUPERVISOR_MAP.items()}
    rev["Citywide"] = "Citywide"
    return rev

@st.cache_data(ttl=300)
def load_data(district_id):
    # Logic: 18 months rolling window
    eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
    
    # [cite_start]Select only columns defined in the schema [cite: 60]
    select_cols = (
        "service_request_id, requested_datetime, closed_date, "
        "service_details, status_notes, address, media_url, supervisor_district"
    )

    # [cite_start]Filtering for specific tree basin tasks [cite: 60]
    details_filter = "(service_details = 'backfill_tree_basin' OR service_details = 'empty_tree_basin')"
    
    params = {
        "$select": select_cols,
        "$where": f"closed_date > '{eighteen_months_ago}' AND agency_responsible LIKE '%PW%' AND {details_filter}",
        "$limit": 50000,
        "$order": "closed_date DESC"
    }

    if district_id != "Citywide":
        # Schema lists supervisor_district as Number, but quotes often safe in SoQL
        params["$where"] += f" AND supervisor_district = '{district_id}'"

    try:
        r = requests.get(API_URL, params=params)
        r.raise_for_status()
        df = pd.DataFrame(r.json())
        
        if df.empty:
            return pd.DataFrame()

        # Vectorized Date Conversion
        df['requested_datetime'] = pd.to_datetime(df['requested_datetime'], errors='coerce')
        df['closed_date'] = pd.to_datetime(df['closed_date'], errors='coerce')
        return df

    except Exception as e:
        st.error(f"Data loading error: {e}")
        return pd.DataFrame()

def get_valid_image_url(media_item):
    [cite_start]"""Parses media_url column [cite: 60] to find valid images."""
    if not media_item: return None
    
    # Handle case where API returns a dictionary wrapper vs raw string
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    
    if not url: return None
        
    clean_url = url.split('?')[0].lower()
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        return url
    return None

# --- 4. MAIN APP ---

def main():
    st.header("SF Citywide: Planned Maintenance Cancellations")
    st.write("Visualizing 311 reports closed as 'Cancelled - Planned Maintenance' by Public Works.")
    
    # --- Sidebar / URL Params ---
    query_params = st.query_params
    url_district = query_params.get("district", "Citywide")
    
    # Validate URL param
    if url_district not in SUPERVISOR_MAP and url_district != "Citywide":
        url_district = "Citywide"

    current_label = SUPERVISOR_MAP.get(url_district, "Citywide")
    rev_map = get_reverse_supervisor_map()

    col_filter, _ = st.columns([1, 3])
    with col_filter:
        selected_label = st.selectbox(
            "Filter by Supervisor District:", 
            get_supervisor_options(),
            index=get_supervisor_options().index(current_label)
        )

    # Sync Selection with URL
    selected_id = rev_map[selected_label]
    if selected_id == "Citywide":
        if "district" in st.query_params:
            del st.query_params["district"]
    else:
        st.query_params["district"] = selected_id

    st.markdown("---")

    # --- Data Loading ---
    with st.spinner("Fetching data..."):
        df = load_data(selected_id)

    # --- Stats Calculation ---
    if df.empty:
        st.warning("No records found matching criteria.")
        return

    # 1. Total Denominator (All backfill/empty tree basins in range)
    total_records = len(df)
    
    # 2. Numerator (Cancelled only)
    # Ensure status_notes is string before comparison
    df['status_notes'] = df['status_notes'].astype(str)
    cancelled_mask = df['status_notes'] == 'Cancelled - Planned Maintenance'
    cancelled_df = df[cancelled_mask].copy()
    cancelled_count = len(cancelled_df)
    
    percentage = (cancelled_count / total_records * 100) if total_records > 0 else 0

    # 3. Visual Feed Count (Cancelled + Has Image)
    # We apply the image validator now to get the count for the third stat line
    cancelled_df['valid_image'] = cancelled_df['media_url'].apply(get_valid_image_url)
    display_df = cancelled_df.dropna(subset=['valid_image'])
    display_count = len(display_df)

    # --- Stats Display ---
    st.markdown(
        f"""
        <div class='metric-container'>
            <span class='metric-text'>
                Found <b>{total_records:,}</b> records total (backfill/empty basin only).<br>
                <b>{cancelled_count:,}</b> were "Cancelled - Planned Maintenance" ({percentage:.1f}% of total).<br>
                <span style="font-size: 0.95rem; opacity: 0.8;">Showing <b>{display_count:,}</b> records that have photos.</span>
            </span>
        </div>
        """, 
        unsafe_allow_html=True
    )

    if display_df.empty:
        st.info("No images available for these cancelled requests.")
        return

    # --- Image Grid ---
    st.markdown("---")
    
    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(display_df.iterrows()):
        col = cols[i % COLS_PER_ROW]
        
        with col:
            with st.container(border=True):
                # Display the image
                st.image(row['valid_image'], use_container_width=True)
                
                # --- Card Details ---
                opened_str = row['requested_datetime'].strftime('%m/%d/%y') if pd.notnull(row['requested_datetime']) else "?"
                closed_str = row['closed_date'].strftime('%m/%d/%y') if pd.notnull(row['closed_date']) else "?"
                
                days_open = "?"
                if pd.notnull(row['requested_datetime']) and pd.notnull(row['closed_date']):
                    days_open = (row['closed_date'] - row['requested_datetime']).days

                ticket_id = row['service_request_id']
                ticket_url = f"https://mobile311.sfgov.org/tickets/{ticket_id}"
                
                addr_clean = row.get('address', 'Location N/A')
                short_addr = addr_clean.split(',')[0]
                map_url = f"https://www.google.com/maps/search/?api=1&query={addr_clean.replace(' ', '+')}"

                # Text Content
                st.markdown(f"**[{short_addr}]({map_url})**")
                st.caption(f"Opened: {opened_str} | Closed: {closed_str}")
                st.caption(f"Days Open: {days_open}")
                
                # Link to Ticket
                st.markdown(f"[View Ticket {ticket_id}]({ticket_url})")

if __name__ == "__main__":
    main()
