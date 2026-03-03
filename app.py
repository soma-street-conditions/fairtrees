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
st.set_page_config(page_title="FairTrees.org | SF Tree Basin Tracker", page_icon="🌳", layout="wide")

API_URL = "https://data.sfgov.org/resource/vw6y-z8j6.json"

SUPERVISOR_MAP = {
    "1": "1 - Connie Chan", "2": "2 - Catherine Stefani", "3": "3 - Danny Sauter",
    "4": "4 - Joel Engardio", "5": "5 - Bilal Mahmood", "6": "6 - Matt Dorsey",
    "7": "7 - Myrna Melgar", "8": "8 - Rafael Mandelman", "9": "9 - Hillary Ronen",
    "10": "10 - Shamann Walton", "11": "11 - Ahsha Safai"
}

# --- 2. STYLING ---
st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div { gap: 0.5rem; }
        
        .hero-text {
            font-size: 1.1rem;
            line-height: 1.6;
            margin-bottom: 1rem;
        }
        
        .card-text {
            font-family: "Source Sans Pro", sans-serif;
            font-size: 13px;
            line-height: 1.4;
            margin: 0px;
        }
        .note-text {
            font-family: "Source Sans Pro", sans-serif;
            font-size: 11px;
            line-height: 1.2;
            margin-top: 4px;
            opacity: 0.8;
        }
        
        div[data-testid="stImage"] > img {
            object-fit: cover; 
            height: 180px; 
            width: 100%;
            border-radius: 4px;
        }
        
        .custom-img {
            object-fit: cover; 
            height: 180px; 
            width: 100%; 
            border-radius: 4px; 
        }
        
        a { text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
""", unsafe_allow_html=True)

# --- 3. THE "HEIST" FUNCTION ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_verint_image_v3(wrapper_url):
    """Downloads and decodes a protected image from the SF 311 Verint system."""
    if not isinstance(wrapper_url, str) or "verint" not in wrapper_url:
        return None

    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://mobile311.sfgov.org/",
        }

        parsed = urlparse(wrapper_url)
        qs = parse_qs(parsed.query)
        url_case_id = qs.get('caseid', [None])[0]
        if not url_case_id: return None

        r_page = session.get(wrapper_url, headers=headers, timeout=5)
        if r_page.status_code != 200: return None
        html = r_page.text

        formref_match = re.search(r'"formref"\s*:\s*"([^"]+)"', html)
        if not formref_match: return None
        formref = formref_match.group(1)
        
        csrf_match = re.search(r'name="_csrf_token"\s+content="([^"]+)"', html)
        csrf_token = csrf_match.group(1) if csrf_match else None

        try:
            citizen_url = "https://sanfrancisco.form.us.empro.verintcloudservices.com/api/citizen?archived=Y&preview=false&locale=en"
            headers["Referer"] = r_page.url
            headers["Origin"] = "https://sanfrancisco.form.us.empro.verintcloudservices.com"
            if csrf_token: headers["X-CSRF-TOKEN"] = str(csrf_token)
            
            r_handshake = session.get(citizen_url, headers=headers, timeout=5)
            if 'Authorization' in r_handshake.headers:
                headers["Authorization"] = str(r_handshake.headers['Authorization'])
        except: pass

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

        download_payload = nested_payload.copy()
        download_payload["data"]["filename"] = target_filename
        
        r_image = session.post(
            f"{api_base}?action=download_attachment&actionedby=&loadform=true&access=citizen&locale=en",
            json=download_payload, headers=headers, timeout=8
        )
        
        if r_image.status_code == 200:
            try:
                response_json = r_image.json()
                if 'data' in response_json and 'txt_file' in response_json['data']:
                    b64_data = response_json['data']['txt_file']
                    if "," in b64_data: b64_data = b64_data.split(",")[1]
                    
                    img_bytes = base64.b64decode(b64_data)
                    
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
@st.cache_data(ttl=600, show_spinner="Loading Tree Tickets...")
def load_tree_tickets(district_id):
    eighteen_months_ago = (datetime.now() - timedelta(days=548)).strftime('%Y-%m-%dT%H:%M:%S')
    
    # Using the exact SoQL query structure for maximum efficiency and robust filtering
    soql_query = f"""
        SELECT service_request_id, requested_datetime, closed_date, service_details, status_notes, address, media_url, supervisor_district 
        WHERE (closed_date > '{eighteen_months_ago}' AND closed_date IS NOT NULL) 
        AND (upper(service_details) LIKE '%EMPTY_TREE_BASIN%')
    """

    # Dynamically append the district filter if not Citywide
    if district_id != "Citywide":
        soql_query += f" AND supervisor_district = '{district_id}'"
        
    # Order by newest first and bypass the 1,000 row default limit
    soql_query += " ORDER BY closed_date DESC LIMIT 5000"

    params = {"$query": soql_query}

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
    if "transferred" in clean: return "Transferred to Urban Forestry"
    if "administrative" in clean: return "Administrative Closure"
    if clean.startswith("case "): clean = clean[5:].strip()
    return clean.split(' ')[0].title()

# --- 5. MAIN APP ---

def main():
    # --- HERO SECTION & ADVOCACY MESSAGING ---
    st.title("San Francisco Empty Tree Basin Tracker")
    
    st.markdown("""
    <div class="hero-text">
        Empty tree wells across San Francisco are more than just an eyesore—they are active tripping hazards that attract litter and debris. Unmaintained craters can be up to 9 inches deep in the pedestrian right-of-way, creating city-wide liability risks, including 48 trip-and-fall lawsuits served to the City Attorney's office in 2025 alone.
        <br><br>
        <b>This community dashboard tracks 311 reports across all 11 Supervisor districts over the last 18 months.</b> By providing residents and city leaders with exact locations and photographic evidence, we can hold Public Works accountable and ensure urban forestry resources are directed where they are needed most.
    </div>
    """, unsafe_allow_html=True)
    
    st.info("**Take Action:** Over 820 residents have already signed the petition demanding Tree Equity. **[Join them and sign the petition today!](https://fairtrees.org/)**", icon="✍️")
    st.markdown("---")
    
    # --- FILTER LOGIC ---
    query_params = st.query_params
    url_district = query_params.get("district", "Citywide")
    district_list = ["Citywide"] + list(SUPERVISOR_MAP.values())
    
    current_sel = SUPERVISOR_MAP.get(url_district, "Citywide")
    if current_sel not in district_list: current_sel = "Citywide"
    
    st.markdown("### Filter Hazards by Supervisor District")
    col_filter, _ = st.columns([1, 2])
    with col_filter:
        selected_label = st.selectbox("Select Supervisor District:", district_list, index=district_list.index(current_sel), label_visibility="collapsed")

    rev_map = {v: k for k, v in SUPERVISOR_MAP.items()}
    rev_map["Citywide"] = "Citywide"
    selected_id = rev_map[selected_label]
    st.query_params["district"] = selected_id

    # --- LOAD DATA ---
    df = load_tree_tickets(selected_id)

    if df.empty:
        st.success(f"No recent empty tree basin reports found for {selected_label}. Help us find them and report them to 311!")
        return

    # --- 1. STATISTICS & METRICS ---
    unique_cases_df = df.drop_duplicates(subset=['service_request_id']).copy()
    unique_count = len(unique_cases_df)
    
    if unique_count > 0:
        unique_cases_df['closure_reason'] = unique_cases_df['status_notes'].apply(get_category)
        stats = unique_cases_df['closure_reason'].value_counts().reset_index()
        stats.columns = ['Closure Reason', 'Total Tickets']
        
        stats['Percentage'] = ((stats['Total Tickets'] / unique_count) * 100).round(0).astype(int).astype(str) + "%"

        st.markdown(f"#### Accountability Metrics: District {selected_id if selected_id != 'Citywide' else 'Overview'} (Past 18 Months)")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Hazardous Wells Reported", f"{unique_count:,}")
        
        top_reason = stats.iloc[0]['Closure Reason']
        top_count = stats.iloc[0]['Total Tickets']
        m2.metric(f"Most Common Result", top_reason)
        m3.metric(f"Tickets Marked '{top_reason}'", f"{top_count:,}")

        st.write("")
        st.markdown(f"##### Full Breakdown of 311 Responses")
        st.dataframe(stats, use_container_width=False, width=600, hide_index=True)
    
    st.markdown("---")

    # --- 2. IMAGE GALLERY ---
    display_df = df.dropna(subset=['media_url']).copy()
    display_df = display_df[~display_df['status_notes'].str.contains("duplicate", case=False, na=False)]
    
    display_df['media_url_str'] = display_df['media_url'].astype(str)
    display_df = display_df.drop_duplicates(subset=['media_url_str'])
    
    if display_df.empty:
        st.info("No images available for these reports.")
        return

    subset_df = display_df.head(100)
    image_count = len(subset_df)
    
    st.markdown(f"### 📸 Visual Evidence of Neglect")
    st.caption(f"Showing the {image_count} most recent closed cases with attached images.")
    st.write("")

    COLS_PER_ROW = 4
    
    for i in range(0, len(subset_df), COLS_PER_ROW):
        row_chunk = subset_df.iloc[i : i + COLS_PER_ROW]
        cols = st.columns(COLS_PER_ROW)
        
        for j, (index, row) in enumerate(row_chunk.iterrows()):
            raw = row['media_url']
            
            image_url = None
            if isinstance(raw, dict):
                image_url = raw.get('url', None)
            elif isinstance(raw, str):
                image_url = raw
                
            if not image_url: continue

            final_bytes = None
            if "verintcloudservices" in image_url:
                final_bytes = fetch_verint_image_v3(image_url)
            
            with cols[j]:
                with st.container(border=True):
                    if final_bytes:
                        st.image(final_bytes, use_container_width=True)
                    else:
                        st.markdown(f'''
                            <img src="{image_url}" class="custom-img">
                        ''', unsafe_allow_html=True)
                        
                    opened = row['requested_datetime']
                    closed = row['closed_date']
                    opened_str = opened.strftime('%b %d, %Y') if pd.notnull(opened) else "?"
                    closed_str = closed.strftime('%b %d, %Y') if pd.notnull(closed) else "?"
                    days_diff = (closed - opened).days if (pd.notnull(opened) and pd.notnull(closed)) else "?"
                    
                    service = str(row['service_details']).replace('_', ' ').title()
                    notes = str(row['status_notes'])
                    addr = str(row['address']).split(',')[0]
                    map_url = f"https://www.google.com/maps/search/?api=1&query={addr.replace(' ', '+')}+San+Francisco"
                    ticket_url = f"https://mobile311.sfgov.org/tickets/{row['service_request_id']}"

                    st.markdown(f"""
                        <p class="card-text"><b><a href="{map_url}" target="_blank">{addr}</a></b></p>
                        <p class="card-text" style="opacity: 0.8;">Opened: {opened_str} <br> Closed: {closed_str} ({days_diff} days)</p>
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
