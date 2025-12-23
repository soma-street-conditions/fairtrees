import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="SF Tree Basin Maintenance", page_icon="🌳", layout="wide")

API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"
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
        .error-text {
            font-family: "Source Sans Pro", sans-serif;
            font-size: 11px;
            color: #FF6B6B; /* Red for errors */
            font-weight: bold;
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

# --- 3. HELPER FUNCTIONS ---

@st.cache_data(ttl=600)
def load_data_v10(district_id):
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

def get_valid_image_url(media_item):
    if not media_item: return None
    url = media_item.get('url') if isinstance(media_item, dict) else media_item
    if not isinstance(url, str): return None
    
    clean_url = url.split('?')[0].lower()
    
    if clean_url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
        return url
        
    # Allow Verint links through so they can be fixed
    if "verintcloudservices" in clean_url:
        return url
        
    return None

# Renamed to v2 to FORCE clear previous cache
@st.cache_data(ttl=3600, show_spinner=False)
def resolve_verint_url_v2(ticket_id, original_url):
    """
    Looks up Cloudinary link via Open311.
    """
    # If it's already good, return it
    if "verintcloudservices" not in str(original_url):
        return original_url

    try:
        params = {"service_request_id": ticket_id, "extensions": "true"}
        # Increased timeout to 6 seconds to prevent random failures
        r = requests.get(OPEN311_URL, params=params, timeout=6)
        data = r.json()
        
        if data and len(data) > 0:
            item = data[0]
            
            # 1. Check photos array (User Photos usually live here)
            ext_attrs = item.get('extended_attributes', {})
            photos = ext_attrs.get('photos', [])
            
            if photos:
                # Walk backwards to find the last valid image (most recent)
                for p in reversed(photos):
                    p_url = p.get('media_url', '')
                    if "cloudinary" in p_url and "_map" not in p_url:
                        return p_url
                # Fallback to last item if we aren't sure
                return photos[-1].get('media_url')

            # 2. Check main media_url
            primary_url = item.get('media_url')
            if primary_url and "cloudinary" in primary_url:
                return primary_url
                    
    except:
        # If API fails/timeouts, we return original so app doesn't crash
        pass
    
    return original_url

def get_category(note):
    if not isinstance(note, str) or note.lower() == 'nan': return "Unknown"
    clean = note.strip().lower()
    
    if "duplicate" in clean: return "Duplicate"
    if "insufficient info" in clean: return "Insufficient Info"
    if "transferred" in clean: return "Transferred"
    if "administrative" in clean: return "Administrative Closure"
    
    if clean.startswith("case "): clean = clean[5:].strip()
        
    return clean.split(' ')[0].title()

# --- 4. MAIN APP ---

def main():
    st.header("SF Tree Basin Maintenance Tracker")
    
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

    # Load Data
    df = load_data_v10(selected_id)

    if df.empty:
        st.warning(f"No records found for {selected_label}.")
        return

    # --- 1. STATISTICS ---
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
    else:
        st.info("No stats available.")

    st.markdown("---")

    # --- 2. IMAGE GALLERY ---
    df['valid_image'] = df['media_url'].apply(get_valid_image_url)
    display_df = df.dropna(subset=['valid_image'])
    display_df = display_df[~display_df['status_notes'].str.contains("duplicate", case=False, na=False)]
    display_df = display_df.drop_duplicates(subset=['valid_image'])
    
    image_count = len(display_df)

    st.markdown(f"#### 📸 Showing {image_count} cases with images")

    if display_df.empty:
        st.info("No images found.")
        return

    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(display_df.iterrows()):
        tile = cols[i % COLS_PER_ROW]
        with tile:
            with st.container(border=True):
                # --- RESOLVE IMAGE ---
                raw_url = row['valid_image']
                ticket_id = row['service_request_id']
                
                # Call the V2 resolver
                final_image_url = resolve_verint_url_v2(ticket_id, raw_url)
                
                st.image(final_image_url, use_container_width=True)
                
                # Check if it failed
                if "verintcloudservices" in final_image_url:
                    st.markdown("<p class='error-text'>⚠️ Fix Failed (API Timeout)</p>", unsafe_allow_html=True)
                
                # Metadata
                opened = row['requested_datetime']
                closed = row['closed_date']
                
                opened_str = opened.strftime('%m/%d/%y') if pd.notnull(opened) else "?"
                closed_str = closed.strftime('%m/%d/%y') if pd.notnull(closed) else "?"
                days_diff = (closed - opened).days if (pd.notnull(opened) and pd.notnull(closed)) else "?"
                
                service = str(row['service_details']).replace('_', ' ').title()
                notes = str(row['status_notes'])
                addr = str(row['address']).split(',')[0]
                map_url = f"https://www.google.com/maps/search/?api=1&query={addr.replace(' ', '+')}+San+Francisco"
                ticket_url = f"https://mobile311.sfgov.org/tickets/{ticket_id}"

                st.markdown(f"""
                    <p class="card-text"><b><a href="{map_url}" target="_blank">{addr}</a></b></p>
                    <p class="card-text" style="color: #9E9E9E;">{opened_str} ➔ {closed_str} ({days_diff} days)</p>
                    <p class="card-text">{service}</p>
                    <p class="note-text">Note: <a href="{ticket_url}" target="_blank">{notes}</a></p>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
