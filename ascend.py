import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from backend import init_db, get_user_stats, log_habit_completion, engine, Habit, SessionLocal, CompletionLog

st.set_page_config(page_title="Ascend", page_icon="🔺", layout="wide")
init_db()

st.markdown("""
    <style>
        #MainMenu, footer {visibility: hidden;}
        .block-container { padding-top: 1rem !important; max-width: 900px; }
        .tier-Iron { color: #6c757d; } .tier-Bronze { color: #cd7f32; }
        .tier-Silver { color: #c0c0c0; text-shadow: 0px 0px 5px rgba(192,192,192,0.3); }
        .tier-Gold { color: #ffd700; text-shadow: 0px 0px 10px rgba(255,215,0,0.4); }
        .tier-Onyx { color: #ffffff; text-shadow: 0px 0px 15px rgba(255,255,255,0.8); }
        .massive-title { font-size: 3rem !important; font-weight: 900 !important; text-align: center !important; margin-bottom: 30px !important; letter-spacing: 2px !important; }
        .momentum-badge { font-size: 0.8rem; background: rgba(99, 110, 250, 0.2); padding: 2px 8px; border-radius: 12px; color: #636EFA; font-weight: bold; margin-left: 10px;}
    </style>
""", unsafe_allow_html=True)

ist_time = datetime.now(ZoneInfo('Asia/Kolkata'))
local_date = ist_time.date()
current_hour = ist_time.hour

db_stats = get_user_stats(user_id=1)
current_tier = db_stats['ascension_tier']
tier_class = f"tier-{current_tier}"
tier_icons = {"Iron": "⚙️", "Bronze": "🥉", "Silver": "🥈", "Gold": "🥇", "Onyx": "💎"}
tier_icon = tier_icons.get(current_tier, "⚙️")

# --- SIDEBAR (IDENTITY & INVENTORY) ---
with st.sidebar:
    st.markdown('<div class="massive-title">🔺 ASCEND</div>', unsafe_allow_html=True)
    st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: center; gap: 20px; margin-bottom: 25px;">
            <div style="font-size: 4.5rem; line-height: 1;">{tier_icon}</div>
            <div style="display: flex; flex-direction: column; align-items: flex-start;">
                <span class="{tier_class}" style="font-size: 2.2rem; font-weight: 900; line-height: 1.1; margin: 0;">{current_tier}</span>
                <span style="font-size: 1.2rem; font-weight: 700; color: #8892b0; margin-top: 5px;">Level {db_stats['level']}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    progress_percent = db_stats['total_xp'] % 100
    st.progress(progress_percent, text=f"{progress_percent}/100 XP to next level")
    st.markdown(f"<div style='text-align: center; margin-top: 10px;'>🔥 **{db_stats['current_streak']} Day Streak**</div>", unsafe_allow_html=True)
    
    # Visual Freeze Inventory
    st.markdown(f"<div style='text-align: center; margin-top: 5px; color: #00CC96;'>❄️ **Freezes Available: {db_stats['streak_freezes']}**</div>", unsafe_allow_html=True)
    
    st.divider()
    current_view = st.radio("Navigation", ["Dashboard", "Habit Engine", "Profile"], label_visibility="hidden")

# --- MAIN CONTENT ---
if current_view == "Dashboard":
    st.title("Executive Dashboard")
    st.divider()
    
    db = SessionLocal()
    habits = db.query(Habit).filter_by(is_active=True).all()
    logs_today = [log.habit_id for log in db.query(CompletionLog).filter_by(date_completed=local_date).all()]
    db.close()
    
    for block in ["Morning", "Midday", "Evening"]:
        is_active = (block == "Morning" and current_hour < 12) or (block == "Midday" and 12 <= current_hour < 18) or (block == "Evening" and current_hour >= 18)
        
        with st.expander(f"📍 {block} Execution", expanded=is_active):
            block_habits = [h for h in habits if h.time_block == block]
            if not block_habits: st.caption("No targets assigned.")
            
            for h in block_habits:
                col1, col2 = st.columns([4, 1])
                
                # --- DEFENSIVE MOMENTUM LOGIC ---
                # Fallback to local_date if database is corrupted and missing created_at
                safe_created_at = h.created_at if h.created_at else local_date
                habit_age = (local_date - safe_created_at).days + 1
                
                momentum_html = ""
                if habit_age <= 45:
                    if habit_age <= 14:
                        boost_pct = 100
                    else:
                        boost_pct = int((1.0 - ((habit_age - 14) / 31.0)) * 100)
                    days_left = 45 - habit_age
                    momentum_html = f"<span class='momentum-badge'>⚡ Momentum: {days_left}d left (+{boost_pct}%)</span>"

                col1.markdown(f"<h4 style='color: {h.color_hex}; display: inline-block; margin: 0;'>{h.icon} {h.name}</h4> {momentum_html}", unsafe_allow_html=True)
                # --------------------------------
                
                if h.id in logs_today:
                    col2.button("Done", key=f"btn_done_{h.id}", disabled=True)
                else:
                    if col2.button("Complete", key=f"btn_{h.id}"):
                        xp_earned = log_habit_completion(h.id, user_id=1, local_date=local_date)
                        if xp_earned:
                            st.toast(f"Target Acquired. +{xp_earned} XP")
                            st.rerun()

elif current_view == "Habit Engine":
    st.header("Construct New Target")
    with st.form("new_habit"):
        name = st.text_input("Habit Designation").strip()
        c1, c2, c3 = st.columns(3)
        icon = c1.text_input("Vector Icon", "🎯")
        color = c2.color_picker("Aesthetic", "#636EFA")
        time_block = c3.selectbox("Time Block", ["Morning", "Midday", "Evening"])
        
        # Decoupled Core Difficulty and Priority
        st.markdown("**Economic Parameters**")
        d1, d2 = st.columns(2)
        difficulty = d1.selectbox("Difficulty (Base XP)", ["Easy", "Medium", "Hard"], index=1)
        priority = d2.selectbox("Priority (Multiplier)", ["Low", "Medium", "High"], index=1)
        
        if st.form_submit_button("Deploy Habit"):
            if not name: st.error("Designation required.")
            else:
                db = SessionLocal()
                if db.query(Habit).filter(Habit.name.ilike(name)).first():
                    st.error("Duplicate Blueprint detected.")
                else:
                    db.add(Habit(name=name, icon=icon, color_hex=color, time_block=time_block, difficulty=difficulty, priority=priority))
                    db.commit()
                    st.success("Target Locked. 45-Day Momentum Boost Activated.")
                    st.rerun()
                db.close()
                
    # --- CRUA COMPLETION: The Archive Engine ---
    st.divider()
    st.subheader("Manage Active Targets")
    
    db = SessionLocal()
    # Query ONLY active habits for the management list
    active_habits = db.query(Habit).filter_by(is_active=True).all()
    
    if not active_habits:
        st.caption("No blueprints deployed yet.")
    else:
        for h in active_habits:
            c1, c2, c3 = st.columns([1, 3, 1])
            c1.markdown(f"**{h.time_block}**")
            c2.markdown(f"<span style='color: {h.color_hex};'>{h.icon} {h.name}</span>", unsafe_allow_html=True)
            
            # The Soft Delete Action
            if c3.button("Archive", key=f"del_{h.id}", type="primary"):
                habit_to_archive = db.query(Habit).filter(Habit.id == h.id).first()
                if habit_to_archive:
                    habit_to_archive.is_active = False # Deactivates without destroying data
                    db.commit()
                    st.toast(f"Target '{h.name}' archived. Historical XP preserved.")
                    st.rerun()
    db.close()

elif current_view == "Profile":
    st.header("Operative Profile")
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Ascension Tier", value=f"{tier_icon} {current_tier}")
    col2.metric(label="Current Level", value=db_stats['level'])
    col3.metric(label="Total XP Earned", value=db_stats['total_xp'])