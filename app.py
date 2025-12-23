import streamlit as st
import pandas as pd
import requests
import concurrent.futures
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="SF Tree Basin Maintenance", page_icon="🌳", layout="wide")

# Source of Truth: Open311 API
OPEN311_URL = "https://mobile311.sfgov.org/open311/v2/requests.json"
SERVICE_CODE = "PW:BUF:Tree Maintenance" # The specific ID for Tree Basin work

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

# --- 3. BULK DATA FETCHING ---

def fetch_batch(page_number):
    """
    Fetches a single page of 50 records. 
    We request 'extensions=true' to get the full image data.
    """
    # 18 Months ago
    start_date = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    params = {
        "service_code": SERVICE_CODE,
        "status": "closed",
        "start_date": start_date, # Filter by date at the source
        "extensions": "true",     # Required for 'media_url' and 'extended_attributes'
        "page": page_number,
        "page_size": 50
    }
    
    try:
        r = requests.get(OPEN311_URL, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        return []
    return []

@st.cache_data(ttl=1800, show_spinner="Downloading 18 months of history from Open311...")
def load_full_history():
    """
    Aggressively fetches data using threading to overcome API pagination limits.
    """
    all_records = []
    max_pages = 100 # Safety limit (100 * 50 = 5000 records). Increase if needed.
    
    # We fetch pages 1-100 in parallel. 
    # This is much faster than waiting for page 1 to finish before asking for page 2.
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_batch, range(1, max_pages + 1)))
    
    # Flatten results
    for page in results:
        if page:
            all_records.extend(page)
            
    if not all_records:
        return pd.DataFrame()
        
    # --- PARSE & CLEAN ---
    # We map the Open311 Schema to a flat DataFrame
    clean_rows = []
    
    for item in all_records:
        # Filter: Ensure it's actually a Tree Basin request
        # Open311 mixes all "Tree Maintenance" together, so we check the attributes
        desc = str(item.get('description', '')).lower()
        
        # Check specific attributes (based on your JSON samples)
        attrs = item.get('attributes', [])
        is_basin = False
        
        # Method A: Check the 'Request type' attribute
        for a in attrs:
            if a.get('code') in ['empty_tree_basin', 'backfill_tree_basin']:
                is_basin = True
                break
        
        # Method B: Fallback to description text if attributes are missing
        if not is_basin and ("empty" in desc or "basin" in desc or "backfill" in desc):
            is_basin = True
            
        if is_basin:
            # IMAGE LOGIC: Prioritize the 'extended_attributes' photos
            # (This fixes the "stitch" map image issue)
            media_url = item.get('media_url')
            ext = item.get('extended_attributes', {})
            photos = ext.get('photos', [])
            
            if photos:
                # Take the last photo (user uploaded), skipping maps if possible
                for p in reversed(photos):
                    p_url = p.get('media_url', '')
                    if "cloudinary" in p_url and "_map" not in p_url:
                        media_url = p_url
                        break
            
            row = {
                "service_request_id": item.get('service_request_id'),
                "requested_datetime": item.get('requested_datetime'),
                "closed_date": item.get('updated_datetime'),
                "status_notes": item.get('status_notes'),
                "description": item.get('description'), # This replaces "service_details"
                "address": item.get('address'),
                "media_url": media_url,
                "lat": item.get('lat'),
                "long": item.get('long')
            }
            clean_rows.append(row)

    df = pd.DataFrame(clean_rows)
    
    if not df.empty:
        df['requested_datetime'] = pd.to_datetime(df['requested_datetime'])
        df['closed_date'] = pd.to_datetime(df['closed_date'])
        
    return df

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
    st.header("SF Tree Basin Maintenance Tracker (Full History)")
    
    # Load Data (Cached)
    df = load_full_history()

    if df.empty:
        st.error("No records found. The API might be timing out or the date range has no closed tickets.")
        return

    # --- FILTERING ---
    # Open311 does NOT return Supervisor District in the JSON.
    # We must join it or use a fallback. For now, we will disable the Supervisor Filter
    # unless we have a polygon map (too heavy for this).
    # Instead, we allow simple text filtering by Address for utility.
    
    search_term = st.text_input("Filter by Street Name or Address:", "")
    
    if search_term:
        df = df[df['address'].astype(str).str.contains(search_term, case=False)]

    # --- 1. STATISTICS ---
    unique_cases_df = df.drop_duplicates(subset=['service_request_id'])
    unique_count = len(unique_cases_df)
    
    if unique_count > 0:
        unique_cases_df['closure_reason'] = unique_cases_df['status_notes'].apply(get_category)
        
        stats = unique_cases_df['closure_reason'].value_counts().reset_index()
        stats.columns = ['Closure Reason', 'Count']
        stats['Percentage'] = (stats['Count'] / unique_count) * 100

        st.markdown(f"##### Closure Reasons ({unique_count:,} Cases)")
        
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

    # --- 2. IMAGE GALLERY ---
    # Filter A: Must have media
    display_df = df.dropna(subset=['media_url'])
    
    # Filter B: Remove "Duplicate" status from images
    display_df = display_df[~display_df['status_notes'].astype(str).str.contains("duplicate", case=False, na=False)]
    
    # Filter C: Deduplicate by Image URL
    display_df = display_df.drop_duplicates(subset=['media_url'])
    
    image_count = len(display_df)

    st.markdown(f"#### 📸 Showing {image_count} cases with images")

    if display_df.empty:
        st.info("No images found.")
        return

    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(display_df.iterrows()):
        with cols[i % COLS_PER_ROW]:
            with st.container(border=True):
                st.image(row['media_url'], use_container_width=True)
                
                opened = row['requested_datetime']
                closed = row['closed_date']
                
                opened_str = opened.strftime('%m/%d/%y') if pd.notnull(opened) else "?"
                closed_str = closed.strftime('%m/%d/%y') if pd.notnull(closed) else "?"
                days_diff = (closed - opened).days if (pd.notnull(opened) and pd.notnull(closed)) else "?"
                
                # Use Description instead of Service Details
                desc = str(row.get('description', 'Tree Basin'))
                # Clean up description (first 50 chars)
                type_label = desc[:50] + "..." if len(desc) > 50 else desc
                
                notes = str(row.get('status_notes', ''))
                
                addr = str(row['address']).split(',')[0]
                map_url = f"https://www.google.com/maps/search/?api=1&query={addr.replace(' ', '+')}+San+Francisco"
                ticket_url = f"https://mobile311.sfgov.org/tickets/{row['service_request_id']}"

                st.markdown(f"""
                    <p class="card-text"><b><a href="{map_url}" target="_blank">{addr}</a></b></p>
                    <p class="card-text" style="color: #9E9E9E;">{opened_str} ➔ {closed_str} ({days_diff} days)</p>
                    <p class="note-text">Note: <a href="{ticket_url}" target="_blank">{notes}</a></p>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
