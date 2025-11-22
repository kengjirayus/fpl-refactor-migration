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

        # Create a form to handle the main analysis submission
        with st.form("settings_form"):
            entry_id_str = st.text_input(
                "Your FPL Team ID (ระบุ ID ทีมของคุณ)",
                key="team_id_input",
                help="นำเลข ID ทีมของคุณจาก URL หลังจากเข้าสู่ระบบ FPL บนเว็บแล้ว Click ดู Points จะเห็น URL https://fantasy.premierleague.com/entry/xxxxxxx/event/2 ให้นำเลข xxxxxxx มาใส่"
            )
            
            transfer_strategy = st.radio(
                "Transfer Strategy (เลือกรูปแบบการเปลี่ยนตัว)",
                ("Free Transfer", "Allow Hit (AI Suggest)", "Wildcard / Free Hit")
            )

            free_transfers = 1
            if transfer_strategy == "Free Transfer":
                free_transfers = st.number_input(
                    "เลือกจำนวนย้ายตัวฟรีที่คุณมี (สูงสุด 5 ตัว)",
                    min_value=0,
                    max_value=5,
                    value=1,
                    help="Select how many free transfers you have available (0-5)"
                )
        
            elif transfer_strategy == "Allow Hit (AI Suggest)":
                free_transfers = 1
        
        # ปุ่ม Analyze Team
            
            submitted = st.form_submit_button(
                label="Analyze Team",
                help="คลิกเพื่อวิเคราะห์ทีมของคุณ",
                use_container_width=False
            )
            
            # --- BUGFIX: Set session state on submission ---
            if submitted:
                if not entry_id_str or entry_id_str.strip() == "":
                    st.error("❗กรุณากรอก FPL Team ID ของคุณในช่องด้านบนเพื่อเริ่มการวิเคราะห์")
                else:
                    st.session_state.analysis_submitted = True
            
            st.markdown(
            """
            <style>
            div[data-testid="stFormSubmitButton"] button {
                background-color: #4CAF50;
                color: white;
            }
            div[data-testid="stFormSubmitButton"] button:hover {
                background-color: #FF9800; /* สีส้มเมื่อ hover */
                color: white;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        # Create a reset button outside of the form with an on_click callback
        st.button("Reset", on_click=reset_team_id, help="ล้างค่า ID และรีเฟรชหน้าจอ", type="primary")

        st.markdown(
            """
            <hr style="border-top: 1px solid #bbb;">
            <a href="https://www.kengji.co/2025/08/30/fpl-wiz/" target="_blank">
                <button style="width: 100%; font-size: 16px; padding: 10px; border-radius: 8px;">
                    คู่มือการใช้งาน 📖
                </button>
            </a>
            <hr style="border-top: 1px solid #bbb;">
            """,
            unsafe_allow_html=True
        )

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
        # Show landing page info only if not submitted
        st.markdown("---")
        st.error("❗กรุณากรอก FPL Team ID ของคุณในช่องด้านข้างเพื่อเริ่มการวิเคราะห์")
        st.info("💡 FPL Team ID จากเว็บไซต์ https://fantasy.premierleague.com/ คลิกที่ Points แล้วจะเห็น Team ID ตามตัวอย่างรูปด้านล่าง")
        st.markdown(
            """
            <style>
            .custom-image img {
                width: 100%;
                max-width: 800px;
                height: auto;
                display: block;
                margin: 0 auto;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="custom-image"><img src="https://mlkrw8gmc4ni.i.optimole.com/w:1920/h:1034/q:mauto/ig:avif/https://www.kengji.co/wp-content/uploads/2025/08/FPL-01-scaled.webp"></div>',
            unsafe_allow_html=True
        )

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
            # Wildcard Logic
            if transfer_strategy == "Wildcard / Free Hit":
                budget = (entry.get('last_deadline_value', 1000) + entry.get('last_deadline_bank', 0)) / 10.0
                st.info(f"Optimizing for Wildcard budget: £{budget:.1f}m")
                wc_ids = optimize_wildcard_team(feat, budget)
                if wc_ids:
                    squad_df = feat.loc[wc_ids].copy()
                    xi_ids, bench_ids = optimize_starting_xi(squad_df)
                    
                    # --- Pitch View ---
                    xi_df = squad_df.loc[xi_ids].copy()
                    cap, vc = select_captain_vice(xi_df)
                    xi_df['is_captain'] = xi_df.index == cap
                    xi_df['is_vice_captain'] = xi_df.index == vc
                    
                    t1, t2 = st.tabs(["Pitch View ⚽", "List View 📋"])
                    with t1: 
                        with st.container(border=False):
                            display_pitch_view(xi_df, "✅ แนะนำนักเตะ 11 ตัวจริง (Suggested Starting XI)")
                    with t2:
                        with st.container(border=False):
                            st.subheader("✅ แนะนำนักเตะ 11 ตัวจริง (List View)")
                            xi_disp = xi_df.copy()
                            xi_disp['pos'] = xi_disp['element_type'].map(POSITIONS)
                            xi_disp['pos'] = pd.Categorical(xi_disp['pos'], categories=['GK', 'DEF', 'MID', 'FWD'], ordered=True)
                            xi_disp = xi_disp.sort_values('pos')
                            display_user_friendly_table(xi_disp[['web_name', 'team_short', 'pos', 'pred_points']], "", height=420)
                    
                    st.success(f"👑 Captain: **{xi_df.loc[cap]['web_name']}** | Vice-Captain: **{xi_df.loc[vc]['web_name']}**")
                    
                    # --- Bench & Insights ---
                    bench_df = squad_df.loc[bench_ids].copy()
                    ordered_bench = smart_bench_order(bench_df)
                    ordered_bench['pos'] = ordered_bench['element_type'].map(POSITIONS)
                    
                    insights = analyze_lineup_insights(xi_df, ordered_bench)
                    if insights: st.info("💡 **คำแนะนำ:**\n\n" + "\n\n".join([f"- {i}" for i in insights]))
                    
                    bench_display = ordered_bench[['web_name', 'team_short', 'pos', 'pred_points']].copy().reset_index(drop=True)
                    bench_display.index += 1
                    display_user_friendly_table(bench_display, "ตัวสำรอง (เรียงตามลำดับ)", height=175)
                    
                    total_points = squad_df['pred_points'].sum()
                    total_cost = squad_df['now_cost'].sum() / 10.0
                    st.success(f"Total Expected Points: **{total_points:.1f}** | Team Value: **£{total_cost:.1f}m**")
                else: st.error("Wildcard optimization failed.")
            
            # Transfer Logic
            else:
                bank = entry.get('last_deadline_bank', 0) / 10.0
                current_ids = [p['element'] for p in picks_data]
                valid_ids = [i for i in current_ids if i in feat.index]
                squad_df = feat.loc[valid_ids].copy()

                free_transfers_from_api = entry.get('free_transfers', 1)
                overall_points = entry.get('summary_overall_points', 0)
                gameweek_points = entry.get('summary_event_points', 0)
                st.info(f"🏦 Bank: **£{bank:.1f}m** | 🆓 Free Transfer: **{free_transfers_from_api}** | 🎯 Overall points: **{overall_points}** | Gameweek points: **{gameweek_points}**")
                
                # Init Simulation
                if 'simulated_squad_ids' not in st.session_state: st.session_state.simulated_squad_ids = valid_ids
                if 'current_team_id' not in st.session_state or st.session_state.current_team_id != entry_id:
                    st.session_state.simulated_squad_ids = valid_ids
                    st.session_state.current_team_id = entry_id

                xi_ids, bench_ids = optimize_starting_xi(squad_df)
                if xi_ids:
                    xi_df = squad_df.loc[xi_ids].copy()
                    cap_id, vc_id = select_captain_vice(xi_df)
                    xi_df['is_captain'] = xi_df.index == cap_id
                    xi_df['is_vice_captain'] = xi_df.index == vc_id

                    # --- BUGFIX v1.5.2: Correct st.tabs syntax ---
                    tab_pitch_api, tab_list_api = st.tabs(["Pitch View ⚽", "List View 📋"])

                    with tab_pitch_api:
                        with st.container(border=False):
                            display_pitch_view(xi_df, "✅ แนะนำนักเตะ 11 ตัวจริง (Suggested Starting XI)")
                    
                    with tab_list_api:
                        with st.container(border=False):
                            st.subheader("✅ แนะนำนักเตะ 11 ตัวจริง (List View)")
                            xi_df_list = xi_df.copy()
                            xi_df_list['pos'] = xi_df_list['element_type'].map(POSITIONS)
                            position_order = ['GK', 'DEF', 'MID', 'FWD']
                            xi_df_list['pos'] = pd.Categorical(xi_df_list['pos'], categories=position_order, ordered=True)
                            xi_df_list = xi_df_list.sort_values('pos')
                            xi_display_df = xi_df_list[['web_name', 'team_short', 'pos', 'pred_points', 'chance_of_playing_next_round']]
                            display_user_friendly_table(
                                df=xi_display_df,
                                title="", # Title is handled by tab
                                height=420
                            )

                    st.success(f"👑 Captain: **{xi_df.loc[cap_id]['web_name']}** | Vice-Captain: **{xi_df.loc[vc_id]['web_name']}**")
                    
                    xi_dgw_teams = xi_df[xi_df['num_fixtures'] > 1]['team_short'].unique()
                    xi_bgw_teams = xi_df[xi_df['num_fixtures'] == 0]['team_short'].unique()

                    dgw_note = ""
                    bgw_note = ""

                    if len(xi_dgw_teams) > 0:
                        dgw_note = f"สัปดาห์นี้มี Double Gameweek ของทีม ({', '.join(xi_dgw_teams)})"
                    if len(xi_bgw_teams) > 0:
                        bgw_note = f"สัปดาห์นี้มี Blank Gameweek ของทีม ({', '.join(xi_bgw_teams)})"

                    if dgw_note or bgw_note:
                        full_note = ""
                        if dgw_note and bgw_note:
                            full_note = f"{dgw_note}. {bgw_note}."
                        elif dgw_note:
                            full_note = f"{dgw_note}."
                        elif bgw_note:
                            full_note = f"{bgw_note}."
                        st.info(f"💡 {full_note}")
                    
                    bench_df = squad_df.loc[bench_ids].copy()
                    ordered_bench_df = smart_bench_order(bench_df)
                    ordered_bench_df['pos'] = ordered_bench_df['element_type'].map(POSITIONS)

                    insights = analyze_lineup_insights(xi_df, ordered_bench_df)
                    if insights:
                        st.info("💡 **คำแนะนำ:**\n\n" + "\n\n".join([f"- {i}" for i in insights]))
                    
                        # --- ปรับปรุง Bench Display (เริ่ม) ---
                    bench_display_df = ordered_bench_df[['web_name', 'team_short', 'pos', 'pred_points', 'chance_of_playing_next_round']].copy()
                    bench_display_df.reset_index(drop=True, inplace=True)
                    bench_display_df.index = bench_display_df.index + 1
                        # --- ปรับปรุง Bench Display (จบ) ---

                    display_user_friendly_table(
                        df=bench_display_df,
                        title="ตัวสำรอง (เรียงตามลำดับ)",
                        height=175
                    )

                # ROI Calculator
                st.markdown("---")
                st.subheader("🧮 คำนวณความคุ้มค่าการย้ายตัว (Transfer ROI Calculator)")
                st.markdown("💡 เลือกนักเตะจากทีมของคุณเพื่อขายออก (OUT) ระบบจะกรองนักเตะตำแหน่งเดียวกันมาให้เลือกซื้อเข้า (IN) เพื่อเปรียบเทียบคะแนน 3 นัดล่วงหน้า")
                
                with st.expander("คลิกเพื่อเปิดเครื่องมือคำนวณ (3-GW Projection)", expanded=True):
                    col_out, col_in, col_hit = st.columns([2, 2, 1])
                    squad_options = [player_id_to_name_map[pid] for pid in valid_ids if pid in player_id_to_name_map]
                    
                    with col_out:
                        p_out_name = st.selectbox("🔴 Player OUT (เลือกจากทีมปัจจุบัน)", options=squad_options, key="roi_out_restricted")
                        p_out_id = player_search_map[p_out_name]
                        out_pos_id = feat.loc[p_out_id, 'element_type']
                        out_pos_name = POSITIONS.get(out_pos_id, "")
                    
                    with col_in:
                        filtered_in = feat[(feat['element_type'] == out_pos_id) & (feat.index != p_out_id)].sort_values('web_name')
                        in_opts = [f"{row['web_name']} ({row['team_short']}) - £{row['now_cost']/10.0}m" for _, row in filtered_in.iterrows()]
                        p_in_name = st.selectbox(f"🟢 Player IN (เฉพาะตำแหน่ง {out_pos_name})", options=in_opts, key="roi_in_restricted")
                        p_in_id = player_search_map[p_in_name]
                    
                    with col_hit:
                        hit_opt = st.radio("การย้ายตัวโดนหักคะแนนหรือไม่?", ["ไม่เสีย", "โดนหัก (-4)"], horizontal=True, key="roi_hit_val")
                        hit_val = 4 if hit_opt == "โดนหัก (-4)" else 0
                    
                    if st.button("คำนวณความคุ้มค่า (Calculate ROI)", type="primary", use_container_width=True):
                        roi_data = calculate_transfer_roi(p_out_id, p_in_id, target_event, feat, fixtures_df, teams, hit_cost=hit_val)
                        
                        st.markdown(f"##### ผลการวิเคราะห์: {out_pos_name} Transfer")
                        c1, c2, c3 = st.columns(3)
                        c1.metric(f"🔴 OUT: {feat.loc[p_out_id, 'web_name']}", f"{roi_data['out_xp_3gw']:.1f} pts", help="คะแนนคาดการณ์รวม 3 นัดถัดไป")
                        c2.metric(f"🟢 IN: {feat.loc[p_in_id, 'web_name']}", f"{roi_data['in_xp_3gw']:.1f} pts", help="คะแนนคาดการณ์รวม 3 นัดถัดไป")
                        delta = roi_data['net_gain']
                        c3.metric("Net Gain (3 GWs)", f"{delta:+.1f} pts", delta=delta, help="ผลต่างคะแนนสุทธิหลังหักลบค่า Hit แล้ว")
                        
                        if roi_data['is_worth_it']:
                            st.success(f"✅ **แนะนำให้เปลี่ยน!** {feat.loc[p_in_id, 'web_name']} น่าจะทำแต้มได้มากกว่าในระยะยาว (3 นัด)")
                        elif delta > 0:
                            st.warning(f"⚠️ **เปลี่ยนได้แต่มีความเสี่ยง** คุ้มทุนเพียงเล็กน้อย ({delta:+.1f} แต้ม)")
                        else:
                            st.error(f"❌ **ไม่แนะนำ** {feat.loc[p_out_id, 'web_name']} ยังน่าจะทำแต้มได้ดีกว่า หรือไม่คุ้มค่า Hit")

                # Suggestions
                st.markdown("---")
                st.subheader("🔄 แนะนำการย้ายตัว (Suggested Transfers)")
                st.markdown("💡 คำแนะนำนี้ใช้ **ราคาขายจริง (Selling Price)** จาก FPL API ของคุณ")
                
                with st.spinner("Analyzing potential transfers..."):
                    moves = suggest_transfers(valid_ids, bank, free_transfers, feat, transfer_strategy, fixtures_df, teams, target_event)
                    if moves:
                        moves_df = pd.DataFrame(moves)
                        moves_df.index += 1
                        moves_df.index.name = "ลำดับ"
                        
                        total_out = moves_df['out_cost'].sum()
                        total_in = moves_df['in_cost'].sum()
                        total_hit = moves_df['hit_cost'].sum()
                        st.info(f"💰 งบประมาณ: ขายออก **£{total_out:.1f}m** | ซื้อเข้า **£{total_in:.1f}m** | เสียแต้ม: **-{total_hit}**")
                        
                        cols_ren = {
                            "out_name": "ขายออก (Out)", "out_cost": "ราคาขาย (£)",
                            "in_name": "ซื้อเข้า (In)", "in_cost": "ราคาซื้อ (£)",
                            "delta_points": "กำไร (GW นี้)", "roi_3gw": "กำไร (3 GW)",
                            "hit_cost": "แต้มที่เสีย", "net_gain": "กำไรสุทธิ (GW นี้)"
                        }
                        moves_disp = moves_df.rename(columns=cols_ren)
                        final_cols = [c for c in ["ขายออก (Out)", "ราคาขาย (£)", "ซื้อเข้า (In)", "ราคาซื้อ (£)", "กำไร (GW นี้)", "กำไร (3 GW)", "แต้มที่เสีย", "กำไรสุทธิ (GW นี้)"] if c in moves_disp.columns]
                        
                        display_user_friendly_table(moves_disp[final_cols], height=45+(len(moves_df)*35))
                    else: st.success("✅ ทีมของคุณยอดเยี่ยมแล้ว! ไม่จำเป็นต้องย้ายตัวในสัปดาห์นี้")
                    st.warning("⚠️ **สำคัญ**: ตรวจสอบราคาขายจริงในแอป FPL ก่อนทำ transfer")

                # Simulation Mode
                st.markdown("---")
                st.subheader("🛠️ ทดลองจัดทีม (Simulation Mode)")
                st.markdown("ใช้ส่วนนี้เพื่อจำลองการย้ายทีมของคุณ *หลังจาก* ที่คุณกดยืนยันใน FPL แล้ว แต่ในนี้ยังไม่อัปเดตตาม")
                
                if st.button("♻️ Reset to Current API Team"):
                    st.session_state.simulated_squad_ids = valid_ids
                    st.rerun()

                st.markdown("#### แก้ไข 15 นักเตะในทีมของคุณ:")
                new_sim_ids = []
                cols = st.columns([3, 1, 4])
                cols[0].markdown("**นักเตะคนปัจจุบัน (ในโหมดจำลอง)**")
                cols[2].markdown("**เลือกนักเตะที่จะเปลี่ยน**")
                
                current_sim_ids = st.session_state.get('simulated_squad_ids', valid_ids)
                if len(current_sim_ids) != 15:
                    st.warning("ทีมจำลองของคุณไม่ครบ 15 คน, กำลังรีเซ็ต...")
                    current_sim_ids = valid_ids
                    st.session_state.simulated_squad_ids = valid_ids

                for i, pid in enumerate(current_sim_ids):
                    if pid not in feat.index: pid = valid_ids[i]
                    player = feat.loc[pid]
                    p_name = player_id_to_name_map.get(pid)
                    if not p_name:
                        p_name = f"{player['web_name']} ({player['team_short']}) - £{player['now_cost']/10.0}m"
                        if p_name not in player_search_map:
                            all_player_name_options.append(p_name)
                            player_search_map[p_name] = pid
                            player_id_to_name_map[pid] = p_name
                    
                    with st.container():
                        c1, c2, c3 = st.columns([3, 1, 4])
                        c1.text(f"{i+1}. {player['web_name']} ({POSITIONS[player['element_type']]})")
                        c2.text("➡️")
                        sel = c3.selectbox(f"Select player {i+1}", all_player_name_options, index=all_player_name_options.index(p_name) if p_name in all_player_name_options else 0, key=f"sim_{i}", label_visibility="collapsed")
                        new_sim_ids.append(player_search_map[sel])
                
                if new_sim_ids != current_sim_ids:
                    st.session_state.simulated_squad_ids = new_sim_ids
                    st.rerun()
                
                st.markdown("---")
                if st.button("คำนวณ 11 ตัวจริง (Simulated Team)", type="primary"):
                    sim_df = feat.loc[new_sim_ids]
                    
                    # Validation
                    errors = []
                    counts = sim_df['element_type'].value_counts().to_dict()
                    if counts.get(1, 0) != 2: errors.append(f"❌ ผู้รักษาประตู: {counts.get(1, 0)} (ต้องมี 2)")
                    if counts.get(2, 0) != 5: errors.append(f"❌ กองหลัง: {counts.get(2, 0)} (ต้องมี 5)")
                    if counts.get(3, 0) != 5: errors.append(f"❌ กองกลาง: {counts.get(3, 0)} (ต้องมี 5)")
                    if counts.get(4, 0) != 3: errors.append(f"❌ กองหน้า: {counts.get(4, 0)} (ต้องมี 3)")
                    for t, c in sim_df['team_short'].value_counts().items():
                        if c > 3: errors.append(f"❌ ทีม {t}: มี {c} คน (สูงสุด 3)")
                    
                    if errors:
                        st.error("ไม่สามารถจัดทีมได้! กรุณาแก้ไขทีมจำลองของคุณ:")
                        for e in errors: st.write(e)
                    else:
                        st.success("✅ ทีมจำลองถูกต้องตามกฎ FPL! กำลังคำนวณ...")
                        orig_budget = (entry.get('last_deadline_value', 1000) + entry.get('last_deadline_bank', 0)) / 10.0
                        sim_cost = sim_df['now_cost'].sum() / 10.0
                        diff = orig_budget - sim_cost
                        msg = f"มูลค่าทีมจำลอง: **£{sim_cost:.1f}m** | งบประมาณคงเหลือ: **£{diff:.1f}m**"
                        if diff < 0: st.warning(msg)
                        else: st.info(msg)
                        
                        xi_ids_sim, bench_ids_sim = optimize_starting_xi(sim_df)
                        if xi_ids_sim:
                            xi_sim = sim_df.loc[xi_ids_sim].copy()
                            cap_sim, vc_sim = select_captain_vice(xi_sim)
                            xi_sim['is_captain'] = xi_sim.index == cap_sim
                            xi_sim['is_vice_captain'] = xi_sim.index == vc_sim
                            
                            t1, t2 = st.tabs(["Pitch View ⚽", "List View 📋"])
                            with t1: 
                                with st.container(border=False):
                                    display_pitch_view(xi_sim, "✅ 11 ตัวจริง (Simulated Team)")
                            with t2:
                                with st.container(border=False):
                                    st.subheader("✅ 11 ตัวจริง (Simulated List View)")
                                    xi_disp_sim = xi_sim.copy()
                                    xi_disp_sim['pos'] = xi_disp_sim['element_type'].map(POSITIONS)
                                    xi_disp_sim['pos'] = pd.Categorical(xi_disp_sim['pos'], categories=['GK', 'DEF', 'MID', 'FWD'], ordered=True)
                                    xi_disp_sim = xi_disp_sim.sort_values('pos')
                                    display_user_friendly_table(xi_disp_sim[['web_name', 'team_short', 'pos', 'pred_points']], "", height=420)
                            
                            st.success(f"👑 Captain (Simulated): **{xi_sim.loc[cap_sim]['web_name']}** | Vice: **{xi_sim.loc[vc_sim]['web_name']}**")
                            
                            bench_sim = sim_df.loc[bench_ids_sim].copy()
                            ordered_bench_sim = smart_bench_order(bench_sim)
                            ordered_bench_sim['pos'] = ordered_bench_sim['element_type'].map(POSITIONS)
                            
                            insights = analyze_lineup_insights(xi_sim, ordered_bench_sim)
                            if insights: st.info("💡 **คำแนะนำ:**\n\n" + "\n\n".join([f"- {i}" for i in insights]))
                            
                            bench_disp_sim = ordered_bench_sim[['web_name', 'team_short', 'pos', 'pred_points']].copy().reset_index(drop=True)
                            bench_disp_sim.index += 1
                            display_user_friendly_table(bench_disp_sim, "ตัวสำรอง (Simulated Team - เรียงตามลำดับ)", height=175)

        except Exception as e: st.error(f"Error: {e}")

if __name__ == "__main__":
    main()