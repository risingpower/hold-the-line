import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from services.day_service import ensure_day
from services.session_service import get_active_session, start_session, stop_session
from services.plan_service import get_plan_hit_rate, create_task, add_to_plan, get_daily_plan, set_completion
from services.log_service import submit_daily_log, log_exists
from services.scoring_service import calculate_daily_score
from services.db import get_connection

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="LIFE OS", 
    page_icon="💀", 
    layout="wide", 
    initial_sidebar_state="expanded" # <--- ADD THIS
)

# --- 2. THE "SHADCN" STYLE INJECTOR ---
def inject_custom_css():
    st.markdown("""
    <style>
        /* RESET & FONT */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
            background-color: #09090b; /* Zinc 950 */
            color: #e4e4e7; /* Zinc 200 */
        }
        
        /* HIDE STREAMLIT BLOAT (Corrected) */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        /* header {visibility: hidden;}  <-- THIS WAS THE CULPRIT. REMOVED. */
        
        /* Make the header transparent instead so the sidebar toggle remains clickable */
        header[data-testid="stHeader"] {
            background: transparent;
        }
        
        /* METRIC CARDS (Shadcn Style) */
        div[data-testid="stMetric"] {
            background-color: #18181b; /* Zinc 900 */
            border: 1px solid #27272a; /* Zinc 800 */
            border-radius: 0.5rem;
            padding: 1rem;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
        
        div[data-testid="stMetricLabel"] > label {
            color: #a1a1aa; /* Zinc 400 */
            font-size: 0.875rem;
            font-weight: 500;
        }
        
        div[data-testid="stMetricValue"] {
            font-size: 1.5rem;
            font-weight: 700;
            color: #f4f4f5; /* Zinc 100 */
        }

        /* DATAFRAME & TABLES */
        div.stDataFrame {
            border: 1px solid #27272a;
            border-radius: 0.5rem;
        }

        /* BUTTONS */
        div.stButton > button {
            background-color: #18181b;
            color: #e4e4e7;
            border: 1px solid #27272a;
            border-radius: 0.375rem;
            padding: 0.5rem 1rem;
            font-size: 0.875rem;
            font-weight: 500;
            transition: all 0.2s;
            width: 100%;
        }
        div.stButton > button:hover {
            border-color: #22c55e; /* Green 500 */
            color: #22c55e;
            background-color: #09090b;
        }
        div.stButton > button:active {
            background-color: #27272a;
        }

        /* INPUTS & SELECTBOXES */
        div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
            background-color: #18181b;
            border-color: #27272a;
            color: #e4e4e7;
            border-radius: 0.375rem;
        }

        /* SIDEBAR POLISH */
        section[data-testid="stSidebar"] {
            background-color: #09090b; /* Deep black match */
            border-right: 1px solid #27272a;
        }
        
        /* COMPACT LAYOUT */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            max-width: 95% !important;
        }
        
        hr {
            margin: 1.5em 0;
            border-color: #27272a;
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- HELPER: FORMAT TIME ---
def format_timestamp(ts):
    if not ts: return "--"
    return datetime.fromtimestamp(ts).strftime('%H:%M')

# --- 3. INITIALIZATION ---
if 'today' not in st.session_state:
    st.session_state.today = date.today()

try:
    ensure_day(st.session_state.today)
except Exception as e:
    st.error(f"System Failure: {e}")
    st.stop()

# --- 4. REACTIVE COMPONENT (THE FRAGMENT) ---
# This runs every 1s individually without reloading the whole page
@st.fragment(run_every=1)
def render_session_manager():
    active_session = get_active_session()
    
    st.caption("FOCUS CONTROL")
    
    if active_session:
        # Calculate live duration
        start_ts = active_session['start_ts']
        elapsed_sec = int(datetime.now().timestamp() - start_ts)
        hours, rem = divmod(elapsed_sec, 3600)
        minutes, seconds = divmod(rem, 60)
        time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
        
        # The "Active" Card
        st.markdown(f"""
        <div style="
            background-color: #18181b; 
            border: 1px solid #22c55e; 
            padding: 1.5rem; 
            border-radius: 0.5rem; 
            display: flex; 
            justify-content: space-between; 
            align-items: center;">
            <div>
                <span style="color: #22c55e; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.05em;">SESSION ACTIVE</span><br>
                <span style="color: #ffffff; font-size: 2rem; font-weight: 700; font-family: monospace;">{time_str}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("") # Spacer
        if st.button("🟥 TERMINATE SESSION", use_container_width=True):
            duration = stop_session(active_session['id'], evidence_url="Manual Stop")
            st.toast(f"Session Closed. +{duration} min logged.")
            st.rerun()
            
    else:
        # The "Idle" State
        todays_plan = get_daily_plan(st.session_state.today)
        # Filter for ENGINE tasks
        task_options = {t['title']: t['task_id'] for t in todays_plan if t['domain'] == 'ENGINE'}
        
        c1, c2 = st.columns([3, 1])
        with c1:
            selected_task = st.selectbox(
                "Select Target", 
                options=["Unplanned Deep Work"] + list(task_options.keys()), 
                label_visibility="collapsed"
            )
        with c2:
            if st.button("🚀 GO", key="start_btn"):
                t_id = task_options.get(selected_task)
                start_session(task_id=t_id, session_type='DEEP')
                st.rerun()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.caption("SYSTEM MENU")
    st.write(f"**{st.session_state.today.strftime('%A, %d %b')}**")
    
    c1, c2 = st.columns(2)
    if c1.button("← Prev"):
        st.session_state.today -= timedelta(days=1)
        st.rerun()
    if c2.button("Next →"):
        st.session_state.today += timedelta(days=1)
        st.rerun()
        
    if st.button("Jump to Today"):
        st.session_state.today = date.today()
        st.rerun()
        
    st.divider()
    mode = st.radio("INTERFACE", ["HUD", "PLANNING", "EVENING LOG"], label_visibility="collapsed")

# --- 6. VIEW: HUD ---
if mode == "HUD":
    # FETCH DATA
    conn = get_connection()
    score_row = pd.read_sql(f"SELECT * FROM daily_derived_latest WHERE date = '{st.session_state.today}'", conn)
    
    nps = score_row.iloc[0]['nps_score'] if not score_row.empty else 0.0
    vessel = score_row.iloc[0]['score_vessel'] if not score_row.empty else "--"
    resources = score_row.iloc[0]['score_resources'] if not score_row.empty else "--"
    hit_rate = get_plan_hit_rate(st.session_state.today)

    status_label = "WIN" if nps > 85 else ("HOLD" if nps > 50 else "FAIL")
    status_delta = f"NPS: {int(nps)}"
    
    # METRIC CARDS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("STATUS", status_label, status_delta)
    c2.metric("ENGINE", f"{hit_rate}%", "Hit Rate")
    c3.metric("VITALITY", f"{int(vessel) if vessel != '--' else '--'}", "Score")
    c4.metric("RESOURCES", f"£{int(resources) if resources != '--' else '--'}", "Spend")
    
    st.divider()
    
    # MAIN SPLIT
    left, right = st.columns([1.5, 1])
    
    with left:
        render_session_manager() # <--- THE REACTIVE COMPONENT
        
        st.write("")
        st.caption("PLAN EXECUTION")
        plan_tasks = get_daily_plan(st.session_state.today)
        
        if not plan_tasks:
            st.info("No plan for today.")
        else:
            for t in plan_tasks:
                is_done = t['completion_status'] == 'COMPLETE'
                # Custom Checkbox Styling Hack? No, keep it simple for v1.
                if st.checkbox(f"{t['title']}", value=is_done, key=f"chk_{t['task_id']}"):
                    if not is_done:
                        set_completion(st.session_state.today, t['task_id'], 'COMPLETE')
                        st.rerun()
                elif is_done:
                    set_completion(st.session_state.today, t['task_id'], 'PENDING')
                    st.rerun()

    with right:
        st.caption("RECENT LOGS")
        df = pd.read_sql("SELECT * FROM work_sessions ORDER BY id DESC LIMIT 5", conn)
        if not df.empty:
            df['start'] = df['start_ts'].apply(format_timestamp)
            df['end'] = df['end_ts'].apply(format_timestamp)
            st.dataframe(
                df[['start', 'duration_minutes', 'session_type']], 
                hide_index=True, 
                use_container_width=True
            )
        else:
            st.markdown("<div style='color: #52525b; font-size: 0.9em;'>No logs yet.</div>", unsafe_allow_html=True)

# --- 7. VIEW: PLANNING ---
elif mode == "PLANNING":
    st.caption(f"TACTICAL PLANNING // {st.session_state.today}")
    
    with st.expander("➕ NEW TASK", expanded=True):
        c1, c2 = st.columns([3, 1])
        title = c1.text_input("Task Title", placeholder="e.g. Deep Work: Q4 Strategy")
        domain = c2.selectbox("Domain", ["ENGINE", "VESSEL", "RESOURCES", "SYSTEM"])
        keystone = st.checkbox("Mark as Keystone (Priority 1)")
        
        if st.button("ADD TO PLAN"):
            if title:
                try:
                    t_id = create_task(title, domain)
                    add_to_plan(st.session_state.today, t_id, keystone)
                    st.success("Task committed.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.write("")
    st.caption("COMMITTED TASKS")
    plan = get_daily_plan(st.session_state.today)
    
    if not plan:
        st.markdown("<div style='color: #52525b; font-style: italic;'>No plan committed. Entropy wins.</div>", unsafe_allow_html=True)
    else:
        for t in plan:
            icon = "👑 " if t['is_keystone'] else "🔹 "
            st.markdown(f"""
            <div style="
                background-color: #18181b; 
                border: 1px solid #27272a; 
                padding: 10px; 
                border-radius: 5px; 
                margin-bottom: 8px; 
                display: flex; 
                justify-content: space-between; 
                align-items: center;">
                <div>
                    <span style="color: #a1a1aa; font-size: 0.75rem;">{t['domain']}</span><br>
                    <span style="color: #e4e4e7; font-weight: 500;">{icon}{t['title']}</span>
                </div>
                <span style="
                    font-size: 0.75rem; 
                    padding: 2px 8px; 
                    border-radius: 10px; 
                    background-color: { '#22c55e20' if t['completion_status']=='COMPLETE' else '#27272a' };
                    color: { '#22c55e' if t['completion_status']=='COMPLETE' else '#71717a' };">
                    {t['completion_status']}
                </span>
            </div>
            """, unsafe_allow_html=True)

# --- 8. VIEW: EVENING LOG ---
elif mode == "EVENING LOG":
    st.caption("EVENING DEBRIEF")
    
    if log_exists(st.session_state.today):
        st.warning("Day is locked. Data is immutable.")
    else:
        with st.form("evening_log"):
            c1, c2 = st.columns(2)
            weight = c1.number_input("Morning Weight (kg)", min_value=0.0, step=0.1)
            sleep = c2.number_input("Sleep Score (0-100)", min_value=0, max_value=100)
            
            c3, c4 = st.columns(2)
            spend = c3.number_input("Total Spend (£)", min_value=0.0)
            alcohol = c4.number_input("Alcohol Units", min_value=0)
            
            screen = st.number_input("Screen Time (Mins)", min_value=0)
            notes = st.text_area("Debrief Notes")
            
            if st.form_submit_button("🔒 LOCK & SCORE DAY"):
                try:
                    submit_daily_log(st.session_state.today, weight, sleep, alcohol, spend, screen, notes)
                    calculate_daily_score(st.session_state.today)
                    st.success("Day Locked. Verdict Computed.")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Submission Failed: {e}")