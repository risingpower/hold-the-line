import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from services.day_service import ensure_day
from services.session_service import get_active_session, start_session, stop_session
from services.plan_service import get_plan_hit_rate, create_task, add_to_plan, get_daily_plan, set_completion
from services.log_service import submit_daily_log, log_exists
from services.db import get_connection
from services.scoring_service import calculate_daily_score

# --- CONFIG ---
st.set_page_config(page_title="LIFE OS", page_icon="💀", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stApp {background-color: #0e1117;}
    .big-metric {font-size: 3em; font-weight: bold; color: #00FF00;}
    div.stButton > button {
        width: 100%;
        background-color: #1c1c1c;
        border: 1px solid #333;
        color: #eee;
    }
    div.stButton > button:hover {
        border-color: #00FF00;
        color: #00FF00;
    }
    .task-card {
        padding: 15px;
        border: 1px solid #333;
        border-radius: 5px;
        margin-bottom: 10px;
        background-color: #161b22;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER: Timestamp Polish ---
def format_timestamp(ts):
    if not ts: return "--"
    return datetime.fromtimestamp(ts).strftime('%H:%M')

# --- INITIALIZATION ---
if 'today' not in st.session_state:
    st.session_state.today = date.today()

# Bootstrapping (Ensure today exists)
try:
    ensure_day(st.session_state.today)
except Exception as e:
    st.error(f"System Failure: {e}")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ SYSTEM MENU")
    st.write(f"**Date:** {st.session_state.today}")
    
    # Date Navigation
    col_nav1, col_nav2 = st.columns(2)
    if col_nav1.button("⬅️ Prev"):
        st.session_state.today -= timedelta(days=1)
        st.rerun()
    if col_nav2.button("Next ➡️"):
        st.session_state.today += timedelta(days=1)
        st.rerun()

    if st.button("Jump to Today"):
        st.session_state.today = date.today()
        st.rerun()

    st.divider()
    mode = st.radio("View Mode", ["HUD", "PLANNING", "EVENING LOG"])

# --- MODE: HUD ---
if mode == "HUD":
    # Fetch Latest Score
    conn = get_connection()
    # We use a raw query here for speed in the UI layer
    score_row = pd.read_sql(f"SELECT * FROM daily_derived_latest WHERE date = '{st.session_state.today}'", conn)
    
    nps = score_row.iloc[0]['nps_score'] if not score_row.empty else 0.0
    vessel = score_row.iloc[0]['score_vessel'] if not score_row.empty else "--"
    resources = score_row.iloc[0]['score_resources'] if not score_row.empty else "--"
    
    # Determine Status Display
    status_label = "WIN" if nps > 85 else ("HOLD" if nps > 50 else "FAIL")
    status_color = "#00FF00" if status_label == "WIN" else ("#FFA500" if status_label == "HOLD" else "#FF0000")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("### 🛡️ STATUS")
        st.markdown(f"<div class='big-metric' style='color:{status_color}'>{status_label}</div>", unsafe_allow_html=True)
        st.caption(f"NPS: {int(nps)}")
    with col2:
        st.markdown("### ⚡ ENGINE")
        hit_rate = get_plan_hit_rate(st.session_state.today)
        st.markdown(f"<div class='big-metric'>{hit_rate}%</div>", unsafe_allow_html=True)
    with col3:
        st.markdown("### 🔥 VITALITY")
        st.markdown(f"<div class='big-metric'>{int(vessel) if vessel != '--' else '--'}</div>", unsafe_allow_html=True)
    with col4:
        st.markdown("### 💰 RESOURCES")
        st.markdown(f"<div class='big-metric'>£{int(resources) if resources != '--' else '--'}</div>", unsafe_allow_html=True)

    # 2. SESSION MANAGER
    active_session = get_active_session()
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("🎯 FOCUS CONTROL")
        if active_session:
            start_ts = active_session['start_ts']
            elapsed = int(datetime.now().timestamp() - start_ts) // 60
            st.warning(f"⚠️ SESSION ACTIVE | DURATION: {elapsed} MINS")
            
            if st.button("🟥 TERMINATE SESSION"):
                duration = stop_session(active_session['id'], evidence_url="Manual Stop")
                st.success(f"Session Closed. +{duration} mins logged.")
                st.rerun()
        else:
            # Dropdown to pick from Planned Tasks
            todays_plan = get_daily_plan(st.session_state.today)
            task_options = {t['title']: t['task_id'] for t in todays_plan if t['domain'] == 'ENGINE'}
            
            selected_task_name = st.selectbox("Select Mission Target", options=list(task_options.keys()) + ["Unplanned Deep Work"])
            
            if st.button("🚀 INITIATE SESSION"):
                task_id = task_options.get(selected_task_name)
                start_session(task_id=task_id, session_type='DEEP')
                st.rerun()

        # Task Completion Checklist (Mini View)
        st.subheader("✅ PLAN EXECUTION")
        plan_tasks = get_daily_plan(st.session_state.today)
        for t in plan_tasks:
            is_done = t['completion_status'] == 'COMPLETE'
            if st.checkbox(f"{t['title']} ({t['domain']})", value=is_done, key=f"chk_{t['task_id']}"):
                if not is_done:
                    set_completion(st.session_state.today, t['task_id'], 'COMPLETE')
                    st.rerun()
            elif is_done:
                set_completion(st.session_state.today, t['task_id'], 'PENDING')
                st.rerun()

    with c2:
        st.subheader("📝 RECENT LOGS")
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM work_sessions ORDER BY id DESC LIMIT 5", conn)
        
        # Apply Timestamp Polish
        if not df.empty:
            df['start'] = df['start_ts'].apply(format_timestamp)
            df['end'] = df['end_ts'].apply(format_timestamp)
            st.dataframe(df[['start', 'end', 'duration_minutes', 'session_type']], hide_index=True)

# --- MODE: PLANNING ---
elif mode == "PLANNING":
    st.title(f"🗺️ TACTICAL PLANNING: {st.session_state.today}")
    
    # 1. Add New Task Form
    with st.expander("➕ Add New Task", expanded=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        new_title = c1.text_input("Task Title")
        new_domain = c2.selectbox("Domain", ["ENGINE", "VESSEL", "RESOURCES", "SYSTEM"])
        is_keystone = c3.checkbox("Keystone?")
        
        if st.button("Add to Plan"):
            if new_title:
                try:
                    # 1. Create in Inventory
                    t_id = create_task(new_title, new_domain)
                    # 2. Add to Daily Plan
                    add_to_plan(st.session_state.today, t_id, is_keystone)
                    st.success("Task Added")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    # 2. View Current Plan
    st.subheader("Current Commitment")
    plan = get_daily_plan(st.session_state.today)
    
    if not plan:
        st.info("No tasks planned yet.")
    else:
        for t in plan:
            status_icon = "👑 " if t['is_keystone'] else ""
            st.markdown(f"""
            <div class='task-card'>
                <b>{status_icon}{t['domain']}</b>: {t['title']} <br>
                <small>Status: {t['completion_status']}</small>
            </div>
            """, unsafe_allow_html=True)

# --- MODE: EVENING LOG ---
elif mode == "EVENING LOG":
    st.title("🌙 EVENING DEBRIEF")
    
    if log_exists(st.session_state.today):
        st.warning("✅ Log already submitted for today. Data is immutable.")
        st.info("To correct an error, you must insert a correction row in the DB manually (Steel Thread Rules).")
    else:
        with st.form("evening_log"):
            c1, c2 = st.columns(2)
            weight = c1.number_input("Morning Weight (kg/lbs)", min_value=0.0, step=0.1)
            sleep = c2.number_input("Sleep Score (0-100)", min_value=0, max_value=100)
            
            c3, c4 = st.columns(2)
            spend = c3.number_input("Total Spend (£)", min_value=0.0)
            alcohol = c4.number_input("Alcohol Units", min_value=0)
            
            screen = st.number_input("Screen Time (Mins)", min_value=0)
            notes = st.text_area("Debrief Notes")
            
            if st.form_submit_button("🔒 LOCK IN DAY"):
                try:
                    # 1. Submit the Immutable Log
                    submit_daily_log(st.session_state.today, weight, sleep, alcohol, spend, screen, notes)
                    
                    # 2. Trigger the Judge (Calculate Score immediately)
                    calculate_daily_score(st.session_state.today)
                    
                    st.success("Day Locked & Scored. The Verdict is in.")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Submission Failed: {e}")