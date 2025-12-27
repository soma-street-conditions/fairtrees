import streamlit as st
import pandas as pd
import requests
import re
import base64
import io
from PIL import Image
from urllib.parse import urlparse, parse_qs
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

# --- 2. STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0rem; }
        .card-text { font-family: "Source Sans Pro", sans-serif; font-size: 13px; line-height: 1.4; color: #E0E0E0; margin: 0px; }
        .note-text { font-family: "Source Sans Pro", sans-serif; font-size: 11px; line-height: 1.2; color: #9E9E9E; margin-top: 4px; }
        div[data-testid="stImage"] > img { object-fit: cover; height: 180px; width: 100%; border-radius: 4px; }
        a { color: #58A6FF; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
""", unsafe_allow_html=True)

# --- 3. THE "HEIST" FUNCTION ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_verint_image_v3(wrapper_url):
    """
    Attempts to download/decode Verint images. Returns None on failure.
    """
    if not isinstance(wrapper_url, str) or "verint" not in wrapper_url:
        return None

    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://mobile311.sfgov.org/",
        }

        # 1. SYNC ID
        parsed = urlparse(wrapper_url)
        qs = parse_qs(parsed.query)
        url_case_id = qs.get('caseid', [None])[0]
        if not url_case_id: return None

        # 2. VISIT PAGE
        r_page = session.get(wrapper_url, headers=headers, timeout=5)
        if r_page.status_code != 200: return None
        html = r_page.text

        formref_match = re.search(r'"formref"\s*:\s*"([^"]+)"', html)
        if not formref_match: return None
        formref = formref_match.group(1)
        
        csrf_match = re.search(r'name="_csrf_token"\s+content="([^"]+)"', html)
        csrf_token = csrf_match.group(1) if csrf_match else None

        # 3. HANDSHAKE
        try:
            citizen_url = "https://sanfrancisco.form.us.empro.verintcloudservices.com/api/citizen?archived=Y&preview=false&locale=en"
            headers["Referer"] = r_page.url
            headers["Origin"] = "https://sanfrancisco.form.us.empro.verintcloudservices.com"
            if csrf_token: headers["X-CSRF-TOKEN"] = str(csrf_token)
            
            r_handshake = session.get(citizen_url, headers=headers, timeout=5)
            if 'Authorization' in r_handshake.headers:
                headers["Authorization"] = str(r_handshake.headers['Authorization'])
        except: pass

        # 4. LIST FILES
        api_base = "https://sanfrancisco.form.us.empro.verintcloudservices.com/api/custom"
        headers["Content-Type"] = "application/json"
        
        nested_payload = {
            "data": {"caseid": str(url_case_id), "formref": str(formref)},
            "name": "download_attachments",
            "email": "", "xref": "", "xref1": "", "xref2": ""
        }
        
        r_list = session.post(
            f"{api_base}?action=get_attachments_details&actionedby=&loadform=true&access=citizen&locale=en",
            json=nested_payload, headers=headers, timeout=5
        )
        
        if r_list.status_code != 200: return None
        
        files_data = r_list.json()
        filename_str = ""
        if 'data' in files_data and 'formdata_filenames' in files_data['data']:
            filename_str = files_data['data']['formdata_filenames']
            
        if not filename_str: return None
        raw_files = filename_str.split(';')

        # 5. FILTER MAPS
        target_filename = None
        for fname in raw_files:
            fname = fname.strip()
            if not fname: continue
            
            f_lower = fname.lower()
            if f_lower.endswith('m.jpg') or f_lower.endswith('_map.jpg') or f_lower.endswith('_map.jpeg'):
                continue
            if f_lower.endswith(('.jpg', '.jpeg', '.png')):
                target_filename = fname
                break
        
        if not target_filename: return None

        # 6. DOWNLOAD
        download_payload = nested_payload.copy()
        download_payload["data"]["filename"] = target_filename
        
        r_image = session.post(
            f"{api_base}?action=download_attachment&actionedby=&loadform=true&access=citizen&locale=en",
            json=download_payload, headers=headers, timeout=8
        )
        
        if r_image.status_code == 200:
            try:
                # 7. UNWRAP & VALIDATE
                response_json = r_image.json()
                if 'data' in response_json and 'txt_file' in response_json['data']:
                    b64_data = response_json['data']['txt_file']
                    if "," in b64_data: b64_data = b64_data.split(",")[1]
                    
                    img_bytes = base64.b64decode(b64_data)
                    
                    # Validate image bytes to ensure st.image can handle them
                    try:
                        with Image.open(io.BytesIO(img_bytes)) as img:
                            img.verify()
                        return img_bytes
                    except:
                        return None
            except:
                return None
            
    except Exception: return None
    return None

# --- 4. DATA LOADING ---
@st.cache_data(ttl=600)
def load_data_v13(district_id):
    eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
    
    select_cols = "service_request_id, requested_datetime, closed_date, service_details, status_notes, address, media_url, supervisor_district"
    where_clause = f"closed_date > '{eighteen_months_ago}' AND agency_responsible LIKE '%PW%' AND (upper(service_details) LIKE '%TREE_BASIN%')"

    if district_id != "Citywide":
        where_clause += f" AND supervisor_district = '{district_id}'"

    params = {"$select": select_cols, "$where": where_clause, "$limit": 5000, "$order": "closed_date DESC"}

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

def get_category(note):
    if not isinstance(note, str) or note.lower() == 'nan': return "Unknown"
    clean = note.strip().lower()
    if "duplicate" in clean: return "Duplicate"
    if "insufficient info" in clean: return "Insufficient Info"
    if "transferred" in clean: return "Transferred"
    if "administrative" in clean: return "Administrative Closure"
    if clean.startswith("case "): clean = clean[5:].strip()
    return clean.split(' ')[0].title()

# --- 5. MAIN APP ---

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

    # --- Load Data ---
    df = load_data_v13(selected_id)

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
        st.dataframe(stats, width=700, hide_index=True)
    
    st.markdown("---")

    # --- 2. IMAGE GALLERY ---
    
    display_df = df.dropna(subset=['media_url'])
    display_df = display_df[~display_df['status_notes'].str.contains("duplicate", case=False, na=False)]
    display_df = display_df.drop_duplicates(subset=['media_url'])
    
    if display_df.empty:
        st.info("No images found.")
        return

    subset_df = display_df.head(100)
    
    image_count = len(subset_df)
    st.markdown(f"#### 📸 Showing {image_count} recent cases with images")

    COLS_PER_ROW = 4
    cols = st.columns(COLS_PER_ROW)

    for i, (index, row) in enumerate(subset_df.iterrows()):
        raw_url = row['media_url']
        
        # --- PERMISSIVE LOGIC START ---
        # 1. Start with the raw URL. If it's a JPG, it stays this way.
        image_to_show = raw_url 
        
        # 2. Only if it's Verint, try to upgrade it to bytes.
        if isinstance(raw_url, str) and "verintcloudservices" in raw_url:
            decoded_bytes = fetch_verint_image_v3(raw_url)
            # 3. If upgrade worked, use bytes. If not, STAY WITH RAW URL.
            if decoded_bytes:
                image_to_show = decoded_bytes
        # --- PERMISSIVE LOGIC END ---
        
        with cols[i % COLS_PER_ROW]:
            with st.container(border=True):
                # 4. Render whatever we have. 
                # If bytes -> works. 
                # If valid URL -> works.
                # If broken Verint URL -> shows broken image icon (Standard Browser Behavior).
                st.image(image_to_show, width="stretch")
                    
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
                    <p class="card-text">{service}</p>
                    <p class="note-text">Note: <a href="{ticket_url}" target="_blank">{notes}</a></p>
                """, unsafe_allow_html=True)

    # --- 3. FOOTER ---
    st.markdown("---")
    st.caption(f"""
        **Methodology & Sources:**
        * **Data Source:** [SF Open Data - 311 Cases](https://data.sfgov.org/City-Infrastructure/311-Cases/vw6y-z8j6)
        * **Image Resolution:** Protected Verint images are securely resolved via direct session handshake.
        * **Filtering:** Duplicate cases (text-based) are excluded from the image feed but included in statistics.
        * **Date Range:** Showing records from the last 18 months.
    """)

if __name__ == "__main__":
    main()
