import streamlit as st
import pandas as pd
import os
import sys
import shutil
import time
from datetime import timedelta
import base64
from glob import glob

# --- PATH SETUP ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.loader import DataLoader
from app.cleaner import DataCleaner
from app.matcher import DepositMatcher
from app.reporter import ReconReporter

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="NEON | Deposit Recon Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- ADVANCED CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Poppins:wght@600;800&display=swap');

    :root {
        --bg-dark: #0B0F1A;
        --card-bg: rgba(255, 255, 255, 0.04);
        --neon-cyan: #00F5FF;
        --neon-purple: #A855F7;
        --neon-green: #00FF9D;
        --neon-red: #FF4D4D;
        --glass-border: rgba(255, 255, 255, 0.08);
    }

    .stApp {
        background-color: var(--bg-dark);
        color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }

    /* Header */
    .main-header {
        text-align: center;
        padding: 3rem 0;
        background: radial-gradient(circle at center, rgba(0, 245, 255, 0.05) 0%, transparent 70%);
    }

    /* Cards */
    .glass-panel {
        background: var(--card-bg);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 2rem;
        backdrop-filter: blur(10px);
    }

    /* Processing Stages */
    .stage-card {
        background: rgba(255, 255, 255, 0.02);
        border-left: 4px solid var(--neon-cyan);
        padding: 10px 20px;
        margin: 5px 0;
        border-radius: 4px;
        font-size: 0.9rem;
    }

    /* Metrics */
    .metric-box {
        text-align: center;
        padding: 1.5rem;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid var(--glass-border);
        border-radius: 12px;
    }

    /* Download Buttons */
    .download-btn {
        display: inline-block;
        background: linear-gradient(45deg, var(--neon-green), var(--neon-cyan));
        color: #000 !important;
        padding: 12px 30px;
        border-radius: 50px;
        font-weight: 800;
        text-decoration: none;
        text-transform: uppercase;
        letter-spacing: 1px;
        box-shadow: 0 0 20px rgba(0, 255, 157, 0.3);
        transition: 0.3s;
        margin: 10px 0;
    }

    .download-btn:hover {
        transform: scale(1.05);
        box-shadow: 0 0 30px var(--neon-green);
    }

    /* Progress Customization */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, var(--neon-cyan), var(--neon-purple)) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
def get_base64_bin(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def save_uploaded_file(uploaded_file, directory):
    if not os.path.exists(directory): os.makedirs(directory)
    file_path = os.path.join(directory, uploaded_file.name)
    with open(file_path, "wb") as f: f.write(uploaded_file.getbuffer())
    return file_path

# --- APP START ---

# Initialize Session State
if 'processing_done' not in st.session_state:
    st.session_state.processing_done = False
    st.session_state.last_report = None
    st.session_state.last_stats = None
    st.session_state.uploader_key = 0

st.markdown("""
    <div class="main-header">
        <h1 style="font-family: 'Poppins', sans-serif; font-size: 3rem; font-weight: 800; margin:0; background: linear-gradient(90deg, #00F5FF, #A855F7); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            NEON RECON PRO
        </h1>
        <p style="color: rgba(255,255,255,0.4); letter-spacing: 3px; font-size: 0.8rem; margin-top: 5px;">AI-POWERED DEPOSIT MATCHING SYSTEM</p>
    </div>
""", unsafe_allow_html=True)

# --- 1. CONFIGURATION ---
input_dir = 'data/input'
bank_pdf_dir = os.path.join(input_dir, 'bank_pdf')
output_dir = 'data/output'

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    st.markdown("### 📊 Master Data (MIS)")
    # Using key from session_state to allow resetting
    mis_file = st.file_uploader("Upload MIS Excel (mis.xlsx)", type=["xlsx"], key=f"mis_{st.session_state.uploader_key}")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    st.markdown("### 🏦 Bank Statements")
    # Using key from session_state to allow resetting
    bank_files = st.file_uploader("Upload Bank PDFs", type=["pdf"], accept_multiple_files=True, key=f"bank_{st.session_state.uploader_key}")
    st.markdown('</div>', unsafe_allow_html=True)

# --- 2. EXECUTION ENGINE ---
if st.button("🚀 START RECONCILIATION PROCESS", use_container_width=True):
    if not mis_file or not bank_files:
        st.error("Please upload both MIS and Bank Statement files to proceed.")
    else:
        # Reset state for new run
        st.session_state.processing_done = False
        
        # Prepare workspace
        if os.path.exists(input_dir): shutil.rmtree(input_dir)
        os.makedirs(bank_pdf_dir)
        if not os.path.exists(output_dir): os.makedirs(output_dir)

        # Save files
        save_uploaded_file(mis_file, input_dir)
        os.rename(os.path.join(input_dir, mis_file.name), os.path.join(input_dir, "mis.xlsx"))
        for f in bank_files: save_uploaded_file(f, bank_pdf_dir)

        # Processing View
        st.markdown("---")
        st.markdown("### ⚙️ Engine Processing Stages")
        
        progress_bar = st.progress(0)
        log_area = st.empty()
        
        try:
            # Stage 1: Loaders
            progress_bar.progress(10)
            log_area.markdown('<div class="stage-card">INIT: Mounting Financial Data Adapters...</div>', unsafe_allow_html=True)
            loader = DataLoader(input_dir=input_dir)
            cleaner = DataCleaner()
            matcher = DepositMatcher()
            reporter = ReconReporter(output_dir=output_dir)
            time.sleep(0.5)

            # Stage 2: PDF Extraction (Optimized)
            progress_bar.progress(30)
            log_area.markdown('<div class="stage-card">EXTRACT: OCR & PDF Text Extraction in progress...</div>', unsafe_allow_html=True)
            mis_df = loader.load_mis_excel("mis.xlsx")
            
            mis_cols = {c.lower().replace(' ', ''): c for c in mis_df.columns}
            m_date_col = mis_cols.get('date') or mis_df.columns[0]
            mis_dates = mis_df[m_date_col].apply(cleaner.clean_date).dropna()
            
            if not mis_dates.empty:
                start_date = mis_dates.min() - timedelta(days=2)
                end_date = mis_dates.max() + timedelta(days=2)
                st.info(f"📅 Target Range: {start_date.date()} to {end_date.date()}")
                bank_df = loader.load_bank_statements(subdir='bank_pdf', start_date=start_date, end_date=end_date)
            else:
                bank_df = loader.load_bank_statements(subdir='bank_pdf')
            
            # Stage 3: Cleaning
            progress_bar.progress(50)
            log_area.markdown('<div class="stage-card">CLEAN: Normalizing bank descriptions & amounts...</div>', unsafe_allow_html=True)
            mis_df, bank_df = cleaner.prepare_dataframes(mis_df, bank_df)

            # Stage 4: Matching
            progress_bar.progress(75)
            log_area.markdown('<div class="stage-card">MATCH: Running Neural Cross-Reference Logic...</div>', unsafe_allow_html=True)
            result_df, bank_result_df = matcher.match(mis_df, bank_df)

            # Stage 5: Reporting
            progress_bar.progress(95)
            log_area.markdown('<div class="stage-card">FINAL: Compiling Reconciled Intelligence Report...</div>', unsafe_allow_html=True)
            final_report_path = reporter.generate_report(result_df, bank_result_df, filename='final_report.xlsx')
            
            # Save results to session state
            st.session_state.last_report = final_report_path
            st.session_state.last_stats = {
                'total': len(result_df),
                'matched': len(result_df[result_df['date_matched']])
            }
            st.session_state.processing_done = True
            # Increment key to clear uploaders
            st.session_state.uploader_key += 1
            
            progress_bar.progress(100)
            log_area.empty()
            st.balloons()
            st.rerun() # Refresh to show cleared uploaders and stored result

        except Exception as e:
            st.error(f"Critical System Failure: {str(e)}")
            st.exception(e)

# --- 3. DISPLAY RESULTS FROM SESSION STATE ---
if st.session_state.processing_done:
    st.markdown("---")
    st.success("Reconciliation Completed Successfully!")
    
    report_path = st.session_state.last_report
    stats = st.session_state.last_stats
    
    m1, m2 = st.columns([2, 1])
    with m1:
        st.markdown(f"#### ✅ Latest Report: `{os.path.basename(report_path)}`")
        st.write("The file uploaders have been reset for your next batch.")
    with m2:
        b64 = get_base64_bin(report_path)
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="Final_Recon_Report.xlsx" class="download-btn">⬇️ DOWNLOAD REPORT</a>'
        st.markdown(href, unsafe_allow_html=True)

    # Stats
    total = stats['total']
    matched = stats['matched']
    unmatched = total - matched
    
    s1, s2, s3 = st.columns(3)
    with s1: st.markdown(f'<div class="metric-box"><div style="color:var(--neon-cyan)">TOTAL</div><h2>{total}</h2></div>', unsafe_allow_html=True)
    with s2: st.markdown(f'<div class="metric-box"><div style="color:var(--neon-green)">MATCHED</div><h2>{matched}</h2></div>', unsafe_allow_html=True)
    with s3: st.markdown(f'<div class="metric-box"><div style="color:var(--neon-red)">EXCEPTION</div><h2>{unmatched}</h2></div>', unsafe_allow_html=True)

# --- 3. REPORT ARCHIVE ---
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("### 📂 Historical Reports Archive")
archive_files = glob(os.path.join(output_dir, "*.xlsx"))

if not archive_files:
    st.info("No reports found in archive.")
else:
    for f_path in archive_files:
        fname = os.path.basename(f_path)
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown(f"**{fname}**")
            st.caption(f"Size: {os.path.getsize(f_path)//1024} KB")
        with col_b:
            b64_arch = get_base64_bin(f_path)
            st.markdown(f'<a href="data:application/octet-stream;base64,{b64_arch}" download="{fname}" style="color:var(--neon-cyan); text-decoration:none; border:1px solid; padding:5px 15px; border-radius:5px;">DOWNLOAD</a>', unsafe_allow_html=True)
        st.markdown("<hr style='margin:10px 0; opacity:0.1'>", unsafe_allow_html=True)

# Footer
st.markdown("""
    <div style="text-align: center; margin-top: 5rem; padding: 2rem; color: rgba(255,255,255,0.1); font-size: 0.7rem; border-top: 1px solid rgba(255,255,255,0.05);">
        NEON RECON PRO v5.0 // SECURE END-TO-END AUDIT // 2026
    </div>
""", unsafe_allow_html=True)
