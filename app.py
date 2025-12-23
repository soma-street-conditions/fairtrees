import streamlit as st
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="SF Tree Basin Maintenance", page_icon="🌳", layout="wide")

# Primary Data Source (Fast, Filterable, Historical)
API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"
# Secondary Lookup (For fixing broken images only)
OPEN311_URL = "https://mobile311.sfgov.org/open311/v2/requests.json"

SUPERVISOR_MAP = {
    "1": "1 - Connie Chan", "2": "2 - Stephen Sherrill", "3": "3 - Danny Sauter",
    "4": "4 - Alan Wong", "5": "5 - Bilal Mahmood", "6": "6 - Matt Dorsey",
    "7": "7 - Myrna Melgar", "8": "8 - Rafael Mandelman", "9": "9 - Jackie Fielder",
    "10": "10 - Shamann Walton", "11": "11 - Chyanne Chen"
}

# --- 2. STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0rem; }
        
        .card-text {
            font-family: "Source Sans Pro", sans-serif;
            font-size: 13px;
            line-height: 1.4;
            color: #E0E0E0;
            margin: 0px;
        }
        .note-text {
            font-family: "Source Sans Pro", sans-serif;
            font-size: 11px;
            line-height: 1.2;
            color: #9E9E9E;
            margin-top: 4px;
        }
        
        div[data-testid="stImage"] > img {
            object-fit: cover; 
            height: 180px; 
            width: 100%;
            border-radius: 4px;
        }
        
        a { color: #58A6FF; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
""", unsafe_allow_html=True)

# --- 3. ROBUST NETWORK SESSION ---
# Creates a session that auto-retries if the Open311 API hiccups
def get_retry_session():
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# --- 4. DATA LOADING (SOCRATA) ---

@st.cache_data(ttl=600)
def load_data_v11(district_id):
    eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
    
    select_cols = (
        "service_request_id, requested_datetime, closed_date, "
        "service_details, status_notes, address, media_url, supervisor_district"
    )
    
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
        
        cols = ['status_notes', 'media_url', 'service_details', 'address', 'service_request_id']
        for c in cols:
            if c not in df.columns: df[c] = None

        df['status_notes'] = df['status_notes'].astype(str)
        df['requested_datetime'] = pd.to_datetime(df['requested_datetime'], errors='coerce')
        df['closed_date'] = pd.to_datetime(df['closed_date'], errors='coerce')
        
        return df
    except Exception as e:
        st.error(f"Data Error: {e}")
        return pd.DataFrame()

# --- 5. IMAGE VALIDATION & FIXING ---

def get_valid_image_url(media_item):
    """
    Initial pass: Validates structure. 
    Explicitly ALLOWS Verint URLs so the fixer can handle them.
    """
    if not media_item: return None
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not isinstance(url, str): return None
    
    clean_url = url.split('?')[0].lower()
    
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
        return url
        
    if "verintcloudservices" in clean_url:
        return url
        
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def fix_verint_url(ticket_id, original_url):
    """
    Robustly resolves Verint links. 
    Returns None if resolution fails, effectively hiding the broken image.
    """
    if "verintcloudservices" not in str(original_url):
        return original_url

    try:
        session = get_retry_session()
        params = {"service_request_id": ticket_id, "extensions": "true"}
        r = session.get(OPEN311_URL, params=params, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                item = data[0]
                
                # 1. Check 'extended_attributes' -> 'photos' (Best Source)
                ext_attrs = item.get('extended_attributes', {})
                photos = ext_attrs.get('photos', [])
                
                if photos:
                    # Reverse loop: Prefer the last photo (user upload), ignore maps
                    for p in reversed(photos):
                        p_url = p.get('media_url', '')
                        if "cloudinary" in p_url and "_map" not in p_url:
                            return p_url
                    # Fallback to last available
                    return photos[-1].get('media_url')

                # 2. Check main 'media_url'
                primary_url = item.get('media_url')
                if primary_url and "cloudinary" in primary_url:
                    return primary_url
    except:
        pass
    
    # If we are here, we failed to resolve it.
    # Return None so the app knows to DROP this image.
    return None

def get_category(note):
    if not isinstance(note, str) or note.lower() == 'nan': return "Unknown"
    clean = note.strip().lower()
    
    if "duplicate" in clean: return "Duplicate"
    if "insufficient info" in clean: return "Insufficient Info"
    if "transferred" in clean: return "Transferred"
    if "administrative" in clean: return "Administrative Closure"
    
    if clean.startswith("case "): clean = clean[5:].strip()
        
    return clean.split(' ')[0].title()

# --- 6. MAIN APP ---

def main():
    st.header("SF Tree Basin Maintenance Tracker")
    
    # --- Filter Logic ---
    query_params = st.query_params
    url_district = query_params.get("district", "Citywide")
    district_list = ["Citywide"] + list(SUPERVISOR_MAP.values())
    
    current_sel = SUPERVISOR_MAP.get(url_district, "Citywide")
    if current_sel not in district_list: current_sel = "Citywide"
    
    col_filter, _ = st.columns([1, 3])
    with col_filter:
        selected_label = st.selectbox("Supervisor District:", district_list, index=district_list.index(current_sel))

    rev_map = {v: k for k, v in SUPERVISOR_MAP.items()}
    rev_map["Citywide"] = "Citywide"
    selected_id = rev_map[selected_label]
    st.query_params["district"] = selected_id

    # --- Load Data (Socrata) ---
    df = load_data_v11(selected_id)

    if df.empty:
        st.warning(f"No records found for {selected_label}.")
        return

    # --- 1. STATISTICS (Unique Tickets Only) ---
    unique_cases_df = df.drop_duplicates(subset=['service_request_id'])
    unique_count = len(unique_cases_df)
    
    if unique_count > 0:
        unique_cases_df['closure_reason'] = unique_cases_df['status_notes'].apply(get_category)
        
        stats = unique_cases_df['closure_reason'].value_counts().reset_index()
        stats.columns = ['Closure Reason', 'Count']
        stats['Percentage'] = (stats['Count'] / unique_count) * 100

        st.markdown(f"##### Closure Reasons ({selected_label})")
        st.caption(f"Denominator: {unique_count:,} unique tickets.")
        
        st.dataframe(
            stats,
            use_container_width=False,
            width=700,
            hide_index=True,
            column_config={
                "Closure Reason": st.column_config.TextColumn("Reason", width="medium"),
                "Count": st.column_config.NumberColumn("Cases", format="%d"),
                "Percentage": st.column_config.ProgressColumn(
                    "Share",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                ),
            }
        )
    
    st.markdown("---")

    # --- 2. IMAGE GALLERY PREP ---
    
    # Step A: Identify Potential Images
    df['valid_image'] = df['media_url'].apply(get_valid_image_url)
    display_df = df.dropna(subset=['valid_image'])
    
    # Step B: Remove "Duplicate" status (Logic Filter)
    display_df = display_df[~display_df['status_notes'].str.contains("duplicate", case=False, na=False)]
    
    # Step C: Deduplicate by Raw URL first
    display_df = display_df.drop_duplicates(subset=['valid_image'])
    
    if display_df.empty:
        st.info("No images found.")
        return

    # --- 3. RENDER LOOP ---
    # We resolve images on the fly. 
    # If resolution fails, we skip rendering that tile entirely.
    
    valid_tiles = []
    
    # Pre-calculate the cleaned URLs (up to a limit to prevent UI freezing)
    # We take the top 100 for immediate display to keep it fast
    subset_df = display_df.head(200) 
    
    for i, (index, row) in enumerate(subset_df.iterrows()):
        raw_url = row['valid_image']
        ticket_id = row['service_request_id']
        
        # Try to fix URL
        final_url = fix_verint_url(ticket_id, raw_url)
        
        # STRICT FILTER: If fixer returns None (failed) or it's still Verint (unresolved), SKIP IT.
        if final_url and "verintcloudservices" not in final_url:
            row['final_image_url'] = final_url
            valid_tiles.append(row)

    # Convert back to DF for rendering
    final_render_df = pd.DataFrame(valid_tiles)
    
    image_count = len(final_render_df)
    st.markdown(f"#### 📸 Showing {image_count} cases with resolved images")

    if final_render_df.empty:
        st.info("No valid images could be resolved.")
        return

    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(final_render_df.iterrows()):
        tile = cols[i % COLS_PER_ROW]
        with tile:
            with st.container(border=True):
                st.image(row['final_image_url'], use_container_width=True)
                
                opened = row['requested_datetime']
                closed = row['closed_date']
                
                opened_str = opened.strftime('%m/%d/%y') if pd.notnull(opened) else "?"
                closed_str = closed.strftime('%m/%d/%y') if pd.notnull(closed) else "?"
                days_diff = (closed - opened).days if (pd.notnull(opened) and pd.notnull(closed)) else "?"
                
                service = str(row['service_details']).replace('_', ' ').title()
                notes = str(row['status_notes'])
                
                addr = str(row['address']).split(',')[0]
                map_url = f"https://www.google.com/maps/search/?api=1&query={addr.replace(' ', '+')}+San+Francisco"
                ticket_url = f"https://mobile311.sfgov.org/tickets/{row['service_request_id']}"

                st.markdown(f"""
                    <p class="card-text"><b><a href="{map_url}" target="_blank">{addr}</a></b></p>
                    <p class="card-text" style="color: #9E9E9E;">{opened_str} ➔ {closed_str} ({days_diff} days)</p>
                    <p class="card
