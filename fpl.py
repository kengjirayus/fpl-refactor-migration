import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import pytz

# 1. Set page config FIRST
st.set_page_config(page_title="FPL Weekly Assistant", page_icon="⚽️", layout="wide")

# 2. Import modules
from data_helpers import (
    get_bootstrap, get_fixtures, get_entry, get_entry_picks,
    get_understat_data, merge_understat_data
)
from fpl_logic import (
    build_master_tables, current_and_next_event, next_fixture_features,
    engineer_features_enhanced, get_fixture_difficulty_matrix, find_rotation_pairs,
    optimize_wildcard_team, optimize_starting_xi, select_captain_vice,
    smart_bench_order, analyze_lineup_insights, calculate_transfer_roi,
    suggest_transfers, POSITIONS
)
from ui_components import (
    add_table_css, add_global_css, display_home_dashboard, display_user_friendly_table,
    display_pitch_view
)

def main():
    st.title("🏟️ FPL WIZ จัดตัวนักเตะด้วย AI | FPL WIZ AI-Powered 🤖")
    st.markdown("เครื่องมือช่วยวิเคราะห์และแนะนำนักเตะ FPL ในแต่ละสัปดาห์ 🧠")
    
    # --- FIX: Call both CSS functions ---
    add_table_css()
    add_global_css()

    with st.sidebar:
        st.header("⚙️ Settings | ตั้งค่า")
        def reset_team_id():
            st.session_state.team_id_input = ""
            if 'simulated_squad_ids' in st.session_state: del st.session_state['simulated_squad_ids']
            if 'current_team_id' in st.session_state: del st.session_state['current_team_id']
            st.session_state.analysis_submitted = False

        with st.form("settings_form"):
            entry_id_str = st.text_input("Your FPL Team ID", key="team_id_input")
            transfer_strategy = st.radio("Transfer Strategy", ("Free Transfer", "Allow Hit (AI Suggest)", "Wildcard / Free Hit"))
            free_transfers = st.number_input("จำนวนย้ายตัวฟรี", 0, 5, 1) if transfer_strategy == "Free Transfer" else 1
            submitted = st.form_submit_button("Analyze Team")
            if submitted: st.session_state.analysis_submitted = True
        
        st.button("Reset", on_click=reset_team_id, type="primary")
        st.markdown("<hr><a href='https://www.kengji.co/2025/08/30/fpl-wiz/' target='_blank'><button style='width:100%'>คู่มือการใช้งาน 📖</button></a>", unsafe_allow_html=True)

    # Load Data
    bootstrap = get_bootstrap()
    fixtures = get_fixtures()
    if not bootstrap or "elements" not in bootstrap:
        st.error("⚠️ FPL API กำลังปิดปรับปรุงชั่วคราว")
        st.stop()
        
    elements, teams, events, fixtures_df = build_master_tables(bootstrap, fixtures)
    cur_event, next_event = current_and_next_event(bootstrap.get("events", []))
    target_event = next_event or (cur_event + 1 if cur_event else 1)
    
    # Display Deadline
    target_event_info = next((e for e in bootstrap.get("events", []) if e.get("id") == target_event), None)
    deadline_text = ""
    if target_event_info and target_event_info.get("deadline_time"):
        utc_time = datetime.fromisoformat(target_event_info["deadline_time"].replace("Z", "+00:00"))
        local_time = utc_time.astimezone(pytz.timezone('Asia/Bangkok'))
        deadline_text = f" | ⏳ Deadline: <b>{local_time.strftime('%a, %d %b %H:%M %Z')}</b>"
    
    st.markdown(f"<div style='background-color:#e8f4fd;padding:1rem;border-radius:0.5rem;border-left:5px solid #2b8ad7;font-size:28px;'>📅 GW: <b>{cur_event}</b> | Next: <b>{target_event}</b>{deadline_text}</div>", unsafe_allow_html=True)

    # Process Data
    nf = next_fixture_features(fixtures_df, teams, target_event)
    us_players, us_teams = get_understat_data()
    feat = engineer_features_enhanced(elements, teams, nf, us_players)
    feat.set_index('id', inplace=True)
    feat["pred_points"] = feat["pred_points_enhanced"]

    # Create maps
    feat_sorted = feat.sort_values('web_name')
    player_search_map = {f"{row['web_name']} ({row['team_short']}) - £{row['now_cost']/10.0}m": idx for idx, row in feat_sorted.iterrows()}
    player_id_to_name_map = {v: k for k, v in player_search_map.items()}
    all_player_name_options = list(player_search_map.keys())

    # Dashboard (If not submitted)
    if not st.session_state.get('analysis_submitted', False):
        opp_matrix, diff_matrix = get_fixture_difficulty_matrix(fixtures_df, teams, target_event)
        rotation_pairs = find_rotation_pairs(diff_matrix, teams, feat)
        merged_us_players, merged_us_teams = merge_understat_data(us_players, us_teams, feat, teams)
        display_home_dashboard(feat, nf, teams, opp_matrix, diff_matrix, rotation_pairs, merged_us_players, merged_us_teams)
        st.error("❗กรุณากรอก FPL Team ID เพื่อเริ่มการวิเคราะห์")

    # Analysis (If submitted)
    else:
        try:
            entry_id = int(st.session_state.team_id_input)
            entry = get_entry(entry_id)
            if not entry or 'name' not in entry: st.error("ไม่สามารถดึงข้อมูลทีมได้"); st.stop()
            picks = get_entry_picks(entry_id, cur_event or 1)
            
            # Process Picks & Selling Price
            picks_data = picks.get("picks", [])
            if not picks_data: st.error("ไม่พบข้อมูลนักเตะ"); st.stop()
            
            selling_price_map = {}
            for p in picks_data:
                pid = p['element']
                if 'selling_price' in p: selling_price_map[pid] = p['selling_price']
                elif 'purchase_price' in p:
                    now_cost = feat.loc[pid, 'now_cost'] if pid in feat.index else p['purchase_price']
                    selling_price_map[pid] = p['purchase_price'] + ((now_cost - p['purchase_price']) // 2)
                else: selling_price_map[pid] = feat.loc[pid, 'now_cost'] if pid in feat.index else 0
            feat['selling_price'] = feat.index.map(selling_price_map)
            feat['selling_price'].fillna(feat['now_cost'], inplace=True)

            st.header(f"🚀 Analysis for '{entry['name']}'")

            # Wildcard Logic
            if transfer_strategy == "Wildcard / Free Hit":
                budget = (entry.get('last_deadline_value', 1000) + entry.get('last_deadline_bank', 0)) / 10.0
                st.info(f"Optimizing for Wildcard budget: £{budget:.1f}m")
                wc_ids = optimize_wildcard_team(feat, budget)
                if wc_ids:
                    squad_df = feat.loc[wc_ids].copy()
                    xi_ids, bench_ids = optimize_starting_xi(squad_df)
                    xi_df = squad_df.loc[xi_ids].copy()
                    cap, vc = select_captain_vice(xi_df)
                    xi_df['is_captain'] = xi_df.index == cap
                    xi_df['is_vice_captain'] = xi_df.index == vc
                    
                    t1, t2 = st.tabs(["Pitch View", "List View"])
                    with t1: display_pitch_view(xi_df, "Wildcard XI")
                    with t2: 
                        xi_disp = xi_df.copy()
                        xi_disp['pos'] = xi_disp['element_type'].map(POSITIONS)
                        display_user_friendly_table(xi_disp[['web_name', 'team_short', 'pos', 'pred_points']], "Wildcard List")
                    
                    st.success(f"Captain: {xi_df.loc[cap]['web_name']}")
                else: st.error("Wildcard optimization failed.")
            
            # Transfer Logic
            else:
                bank = entry.get('last_deadline_bank', 0) / 10.0
                current_ids = [p['element'] for p in picks_data]
                valid_ids = [i for i in current_ids if i in feat.index]
                squad_df = feat.loc[valid_ids].copy()
                
                # Init Simulation
                if 'simulated_squad_ids' not in st.session_state: st.session_state.simulated_squad_ids = valid_ids
                if 'current_team_id' not in st.session_state or st.session_state.current_team_id != entry_id:
                    st.session_state.simulated_squad_ids = valid_ids
                    st.session_state.current_team_id = entry_id

                xi_ids, bench_ids = optimize_starting_xi(squad_df)
                if xi_ids:
                    xi_df = squad_df.loc[xi_ids].copy()
                    cap, vc = select_captain_vice(xi_df)
                    xi_df['is_captain'] = xi_df.index == cap
                    xi_df['is_vice_captain'] = xi_df.index == vc
                    t1, t2 = st.tabs(["Pitch View", "List View"])
                    with t1: display_pitch_view(xi_df, "Current XI")
                    with t2:
                        xi_disp = xi_df.copy()
                        xi_disp['pos'] = xi_disp['element_type'].map(POSITIONS)
                        display_user_friendly_table(xi_disp[['web_name', 'team_short', 'pos', 'pred_points']], "Current List")
                    
                    st.success(f"Captain: {xi_df.loc[cap]['web_name']}")
                    bench_df = squad_df.loc[bench_ids].copy()
                    ordered_bench = smart_bench_order(bench_df)
                    insights = analyze_lineup_insights(xi_df, ordered_bench)
                    if insights: st.info("\n".join([f"- {i}" for i in insights]))

                # ROI Calculator
                st.markdown("---")
                st.subheader("🧮 Transfer ROI Calculator")
                with st.expander("Open Calculator", expanded=True):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    squad_opts = [player_id_to_name_map[pid] for pid in valid_ids if pid in player_id_to_name_map]
                    with c1:
                        p_out_name = st.selectbox("OUT", squad_opts)
                        p_out_id = player_search_map[p_out_name]
                        pos_id = feat.loc[p_out_id, 'element_type']
                    with c2:
                        in_opts = [f"{row['web_name']} ({row['team_short']}) - £{row['now_cost']/10.0}m" 
                                  for _, row in feat[feat['element_type'] == pos_id].sort_values('web_name').iterrows()]
                        p_in_name = st.selectbox("IN", in_opts)
                        p_in_id = player_search_map[p_in_name]
                    with c3:
                        hit = 4 if st.radio("Hit?", ["No", "Yes (-4)"]) == "Yes (-4)" else 0
                    
                    if st.button("Calculate"):
                        roi = calculate_transfer_roi(p_out_id, p_in_id, target_event, feat, fixtures_df, teams, hit)
                        st.metric("Net Gain (3GW)", f"{roi['net_gain']:.1f}", delta=roi['net_gain'])

                # Suggestions
                st.markdown("---")
                st.subheader("🔄 Suggested Transfers")
                moves = suggest_transfers(valid_ids, bank, free_transfers, feat, transfer_strategy, fixtures_df, teams, target_event)
                if moves:
                    moves_df = pd.DataFrame(moves).rename(columns={"out_name": "Out", "in_name": "In", "net_gain": "Gain"})
                    display_user_friendly_table(moves_df[["Out", "out_cost", "In", "in_cost", "Gain"]], height=300)
                else: st.success("No transfers recommended.")

                # Simulation Mode
                st.markdown("---")
                st.subheader("🛠️ Simulation Mode")
                if st.button("Reset Simulation"): st.session_state.simulated_squad_ids = valid_ids; st.rerun()
                
                current_sim_ids = st.session_state.simulated_squad_ids
                new_sim_ids = []
                for i, pid in enumerate(current_sim_ids):
                    if pid not in feat.index: pid = valid_ids[i]
                    p_name = player_id_to_name_map.get(pid, f"Unknown ({pid})")
                    c1, c2 = st.columns([1, 1])
                    c1.text(f"{i+1}. {p_name}")
                    sel = c2.selectbox(f"Swap {i+1}", all_player_name_options, index=all_player_name_options.index(p_name) if p_name in all_player_name_options else 0, key=f"sim_{i}", label_visibility="collapsed")
                    new_sim_ids.append(player_search_map[sel])
                
                if new_sim_ids != current_sim_ids:
                    st.session_state.simulated_squad_ids = new_sim_ids
                    st.rerun()
                
                if st.button("Calc Sim XI"):
                    sim_df = feat.loc[new_sim_ids]
                    s_xi, s_bench = optimize_starting_xi(sim_df)
                    if s_xi:
                         display_pitch_view(sim_df.loc[s_xi], "Simulated XI")
                         st.success(f"Sim Cost: £{sim_df['now_cost'].sum()/10.0:.1f}m")

        except Exception as e: st.error(f"Error: {e}")

if __name__ == "__main__":
    main()