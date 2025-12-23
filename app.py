import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="SF Tree Basin Maintenance", page_icon="🌳", layout="wide")

API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"

SUPERVISOR_MAP = {
    "1": "1 - Connie Chan", "2": "2 - Stephen Sherrill", "3": "3 - Danny Sauter",
    "4": "4 - Alan Wong", "5": "5 - Bilal Mahmood", "6": "6 - Matt Dorsey",
    "7": "7 - Myrna Melgar", "8": "8 - Rafael Mandelman", "9": "9 - Jackie Fielder",
    "10": "10 - Shamann Walton", "11": "11 - Chyanne Chen"
}

# --- 2. ADVANCED STYLING ---
st.markdown("""
    <style>
        /* Tighter vertical spacing globally */
        div[data-testid="stVerticalBlock"] > div { gap: 0rem; }
        
        /* CARD TEXT: Smaller and tighter */
        .card-text {
            font-family: "Source Sans Pro", sans-serif;
            font-size: 12px;
            line-height: 1.3;
            color: #E0E0E0;
            margin: 0px;
        }
        
        /* IMAGES: Uniform height */
        div[data-testid="stImage"] > img {
            object-fit: cover; 
            height: 180px; 
            width: 100%;
            border-radius: 4px;
        }
        
        /* TABLE: Modern Dashboard Style */
        .styled-table-container {
            display: flex;
            justify-content: center;
            margin-top: 10px;
            margin-bottom: 25px;
        }
        .styled-table {
            border-collapse: collapse;
            font-family: "Source Sans Pro", sans-serif;
            font-size: 13px;
            min-width: 500px;
            width: 60%;
            background-color: #161B22;
            border-radius: 6px;
            overflow: hidden;
            border: 1px solid #30363D;
        }
        .styled-table thead tr {
            background-color: #21262D;
            color: #8B949E;
            text-align: left;
            font-weight: 600;
        }
        .styled-table th, .styled-table td {
            padding: 8px 15px;
            border-bottom: 1px solid #30363D;
        }
        .styled-table tbody tr:hover {
            background-color: #1F242C;
        }
        .styled-table tbody tr:last-child td {
            border-bottom: none;
        }
        
        /* Link Styling */
        a { color: #58A6FF; text-decoration: none; }
        a:hover { text-decoration: underline; }
        
        /* Highlight Text */
        .highlight-text {
            font-size: 1.1rem;
            font-weight: 600;
            color: #FFFFFF;
            margin-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 3. LOGIC ---

@st.cache_data(ttl=600)
def load_data(district_id):
    eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
    
    select_cols = (
        "service_request_id, requested_datetime, closed_date, "
        "service_details, status_notes, address, media_url"
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
    if not isinstance(note, str): return "Unknown"
    note_lower = note.strip().lower()
    
    if note_lower.startswith("case is a duplicate"): return "Duplicate"
    if note_lower.startswith("case resolved"): return "Resolved"
    if note_lower.startswith("case transferred"): return "Transferred"
    if note_lower.startswith("insufficient info"): return "Insufficient Info"
    
    return note.split(' ')[0].title()

# --- 4. MAIN APP ---

def main():
    st.header("SF Tree Basin Maintenance Tracker")
    
    # Filter Setup
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

    # Load Full Data
    df = load_data(selected_id)

    if df.empty:
        st.warning("No records found.")
        return

    # --- PRE-CALCULATE IMAGE DATA ---
    # We do this early so we can display the count at the top
    df['valid_image'] = df['media_url'].apply(get_valid_image_url)
    display_df = df.dropna(subset=['valid_image'])
    # Deduplicate based on image URL
    display_df = display_df.drop_duplicates(subset=['valid_image'])
    image_count = len(display_df)

    # --- DISPLAY COUNT TEXT ---
    st.markdown(f"<p class='highlight-text'>Showing {image_count} cases with images</p>", unsafe_allow_html=True)

    # --- STATS TABLE (Uses Full Dataset) ---
    df['closure_reason'] = df['status_notes'].apply(get_category)
    stats = df['closure_reason'].value_counts().reset_index()
    stats.columns = ['Reason', 'Count']
    total_cases = len(df)
    
    table_rows = ""
    for _, row in stats.iterrows():
        pct = (row['Count'] / total_cases) * 100
        table_rows += f"""
            <tr>
                <td>{row['Reason']}</td>
                <td>{row['Count']:,}</td>
                <td>{pct:.1f}%</td>
            </tr>
        """

    st.markdown(f"""
        <div class="styled-table-container">
            <table class="styled-table">
                <thead>
                    <tr>
                        <th style="width: 40%;">Closure Reason</th>
                        <th style="width: 30%;">Cases ({total_cases:,})</th>
                        <th style="width: 30%;">%</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")

    # --- IMAGE GRID SECTION ---
    if display_df.empty:
        st.info("No unique images found for these records.")
        return

    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(display_df.iterrows()):
        with cols[i % COLS_PER_ROW]:
            with st.container(border=True):
                st.image(row['valid_image'], use_container_width=True)
                
                # Metadata
                opened = row['requested_datetime']
                closed = row['closed_date']
                opened_str = opened.strftime('%m/%d/%y') if pd.notnull(opened) else "?"
                closed_str = closed.strftime('%m/%d/%y') if pd.notnull(closed) else "?"
                days_diff = (closed - opened).days if (pd.notnull(opened) and pd.notnull(closed)) else "?"
                
                service = str(row.get('service_details', 'N/A')).replace('_', ' ').title()
                notes = str(row.get('status_notes', 'N/A'))
                if len(notes) > 60: notes = notes[:60] + "..."
                
                addr = row.get('address', 'Location N/A').split(',')[0]
                
                map_url = f"https://www.google.com/maps/search/?api=1&query={addr.replace(' ', '+')}+San+Francisco"
                ticket_url = f"https://mobile311.sfgov.org/tickets/{row['service_request_id']}"

                st.markdown(f"""
                    <p class="card-text"><b><a href="{map_url}" target="_blank">{addr}</a></b></p>
                    <p class="card-text" style="color: #8B949E;">{opened_str} ➔ {closed_str} ({days_diff} days)</p>
                    <p class="card-text">{service}</p>
                    <p class="card-text">Note: <a href="{ticket_url}" target="_blank">{notes}</a></p>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
