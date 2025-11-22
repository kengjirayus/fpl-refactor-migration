import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import plotly.graph_objects as go
from fpl_logic import POSITIONS

# --- NEW: Global CSS from original file ---
def add_global_css():
    st.markdown(
        """
        <style>
        /* CSS สำหรับหน้าจอขนาดใหญ่ (Desktop) */
        @media (min-width: 769px) {
            .mobile-only {
                display: none !important;
            }
        }
        
        /* CSS สำหรับหน้าจอขนาดเล็ก (Mobile) */
        @media (max-width: 768px) {
            /* ซ่อนปุ่ม << >> ของ Streamlit บนมือถือ */
            .st-emotion-cache-1l02wac {
                display: none !important;
            }
            /* ปรับ padding บน mobile เพื่อให้มีพื้นที่มากขึ้น */
            .st-emotion-cache-1629p26 {
                padding-top: 1rem;
                padding-bottom: 1rem;
            }
        }
        
        /* Custom Submit Button Style */
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
    
    # Mobile-only header content
    st.markdown(
        """
        <div class="mobile-only" style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #4CAF50; font-size: 24px;">⚙️ การตั้งค่าอยู่ที่แถบด้านข้าง</h2>
            <p style="color: #607D8B; font-size: 18px;">(คลิก >> มุมซ้ายบนเพื่อเปิด)</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# 1. สร้าง Dictionary สำหรับแปลง Column Names
def create_column_mapping():
    thai_english_headers = {
        "web_name": "ชื่อนักเตะ (Name)", "team_short": "ทีม (Team)", "element_type": "ตำแหน่ง (Position)",
        "pos": "ตำแหน่ง (Pos)", "now_cost": "ราคา (Price)", "price": "ราคา (Price)", "form": "ฟอร์ม (Form)",
        "avg_fixture_ease": "ความยากของเกม (Fixture)", "fixture_ease": "ความยากของเกมถัดไป (Fixture)",
        "pred_points": "คะแนนคาดการณ์ (Pred Points)", "points_per_game": "คะแนน/เกม (PPG)",
        "total_points": "คะแนนรวม (Total Pts)", "selected_by_percent": "% เลือก (Selected %)",
        "ict_index": "ICT Index", "play_prob": "โอกาสลงเล่น (Play %)", "num_fixtures": "จำนวนแมตช์ (Fixtures)",
        "out_name": "ขายออก (Out)", "in_name": "ซื้อเข้า (In)", "delta_points": "ผลต่าง(Points)",
        "net_gain": "กำไรสุทธิ", "out_cost": "ราคาขาย (£)", "in_cost": "ราคาซื้อ (£)",
        "hit_cost": "ค่าแรงลบ (Hit Cost)", "photo_url": "รูป", "chance_of_playing_next_round": "โอกาสลงเล่น (%)"
    }
    english_headers = {
        "web_name": "Player Name", "team_short": "Team", "element_type": "Position", "pos": "Pos",
        "now_cost": "Price (£)", "price": "Price (£)", "form": "Form", "avg_fixture_ease": "Fixture Difficulty",
        "fixture_ease": "Fixture Difficulty", "pred_points": "Predicted Points", "points_per_game": "Points Per Game",
        "total_points": "Total Points", "selected_by_percent": "Selected %", "ict_index": "ICT Index",
        "play_prob": "Play Probability", "num_fixtures": "Fixtures", "out_name": "Player Out",
        "in_name": "Player In", "delta_points": "Points Difference", "net_gain": "Net Gain",
        "out_cost": "Selling Price", "in_cost": "Buying Price", "hit_cost": "Hit Cost", "photo_url": "Photo",
        "chance_of_playing_next_round": "Chance of Playing"
    }
    return thai_english_headers, english_headers

def format_dataframe(df, language="thai_english"):
    thai_english_headers, english_headers = create_column_mapping()
    headers = thai_english_headers if language == "thai_english" else english_headers
    formatted_df = df.copy()
    formatted_df.columns = [headers.get(col, col) for col in formatted_df.columns]
    return formatted_df

def format_numbers_in_dataframe(df):
    formatted_df = df.copy()
    for col in formatted_df.columns:
        if formatted_df[col].dtype in ['float64', 'int64']:
            if any(keyword in col.lower() for keyword in ['price', '£', 'cost', 'ราคา']):
                formatted_df[col] = formatted_df[col].apply(lambda x: f"£{x:.1f}m" if pd.notnull(x) else "")
            elif any(keyword in col.lower() for keyword in ['%', 'percent', 'prob', 'โอกาส']):
                formatted_df[col] = formatted_df[col].apply(lambda x: f"{x:.0f}%" if pd.notnull(x) else "")
            elif any(keyword in col.lower() for keyword in ['points', 'คะแนน', 'form', 'ฟอร์ม']):
                formatted_df[col] = formatted_df[col].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "")
            else:
                formatted_df[col] = formatted_df[col].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "")
    return formatted_df

def add_color_coding(df, score_columns=None):
    if score_columns is None: score_columns = ['pred_points', 'form', 'delta_points', 'net_gain']
    def highlight_scores(row):
        colors = []
        for col in row.index:
            if any(score_col in col.lower() for score_col in score_columns):
                val = row[col]
                if isinstance(val, str):
                    try: val = float(val.replace('£', '').replace('m', '').replace('%', ''))
                    except: val = 0
                if val >= 7: colors.append('background-color: #d4edda')
                elif val >= 5: colors.append('background-color: #fff3cd')
                elif val >= 4: colors.append('background-color: #fce4b3')
                elif val < 4: colors.append('background-color: #f8d7da')
                else: colors.append('')
            else: colors.append('')
        return colors
    return df.style.apply(highlight_scores, axis=1)

def display_user_friendly_table(df, title="", language="thai_english", add_colors=True, height=400):
    if title: st.subheader(title)
    display_df = df.copy()
    formatted_df = format_dataframe(display_df, language)
    formatted_df = format_numbers_in_dataframe(formatted_df)
    if add_colors:
        styled_df = add_color_coding(formatted_df)
        st.dataframe(styled_df, use_container_width=True, height=height)
    else:
        st.dataframe(formatted_df, use_container_width=True, height=height)

def display_table_section(df: pd.DataFrame, title: str, columns: list = None, height: int = 400):
    if columns: df = df[columns]
    display_user_friendly_table(df=df, title=title, language="thai_english", add_colors=True, height=height)

def add_table_css():
    st.markdown("""
    <style>
    .dataframe { font-size: 14px !important; }
    .dataframe th { background-color: #f0f2f6 !important; color: #262730 !important; font-weight: bold !important; text-align: center !important; padding: 12px 8px !important; border-bottom: 2px solid #e6e9ef !important; }
    .dataframe td { text-align: center !important; padding: 8px !important; border-bottom: 1px solid #e6e9ef !important; }
    @media (max-width: 768px) { .dataframe { font-size: 12px !important; } .dataframe th, .dataframe td { padding: 6px 4px !important; } }
    </style>
    """, unsafe_allow_html=True)

def display_pitch_view(team_df: pd.DataFrame, title: str):
    st.subheader(title)
    import base64
    with open("Pix/FPL-Wiz-Field.png", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    pitch_css = f"""
    <style>
    .pitch-container {{ position: relative; width: 100%; max-width: 600px; margin: 20px auto; background-image: url('data:image/png;base64,{encoded_string}'); background-size: contain; background-repeat: no-repeat; background-position: center; aspect-ratio: 7/10; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); padding: 5% 0; }}
    .pitch-row {{ display: flex; justify-content: space-around; align-items: center; width: 100%; margin-bottom: 10%; }}
    .player-card {{ display: flex; flex-direction: column; align-items: center; text-align: center; width: 80px; }}
    .player-card img {{ width: 60px; height: 80px; margin-bottom: 4px; background-color: #eee; border-radius: 4px; object-fit: cover; }}
    .player-name {{ font-size: 11px; font-weight: bold; color: white; background-color: rgba(0, 0, 0, 0.7); padding: 2px 5px; border-radius: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; box-sizing: border-box; }}
    .player-info {{ font-size: 10px; color: #f0f0f0; background-color: rgba(50, 50, 50, 0.6); padding: 1px 4px; border-radius: 4px; margin-top: 2px; }}
    </style>
    """
    team_df['pos'] = team_df['element_type'].map(POSITIONS)
    gk = team_df[team_df['pos'] == 'GK']
    defs = team_df[team_df['pos'] == 'DEF'].sort_values('pred_points', ascending=False)
    mids = team_df[team_df['pos'] == 'MID'].sort_values('pred_points', ascending=False)
    fwds = team_df[team_df['pos'] == 'FWD'].sort_values('pred_points', ascending=False)
    DEFAULT_PHOTO_URL_PITCH = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png"

    def generate_player_html(player_row):
        name = player_row['web_name']
        if player_row.get('is_captain', False): name = f"{name} (C)"
        elif player_row.get('is_vice_captain', False): name = f"{name} (V)"
        
        chance = player_row.get('chance_of_playing_next_round', 100)
        if pd.isna(chance): chance = 100
        
        return f"<div class='player-card'><img src='{player_row['photo_url']}' alt='{player_row['web_name']}' onerror=\"this.onerror=null;this.src='{DEFAULT_PHOTO_URL_PITCH}';\"><div class='player-name'>{name}</div><div class='player-info'>{player_row['pred_points']:.1f}pts | {chance:.0f}%</div></div>"

    html = f"{pitch_css}<div class='pitch-container'>"
    for group in [gk, defs, mids, fwds]:
        html += "<div class='pitch-row'>"
        for _, player in group.iterrows(): html += generate_player_html(player)
        html += "</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def get_difficulty_css_class(val, min_val, max_val):
    if val == 0: return "bg-blank"
    if val >= 15: return "bg-easy"
    elif val >= 8: return "bg-medium"
    else: return "bg-hard"

def display_visual_fixture_planner(opp_matrix: pd.DataFrame, diff_matrix: pd.DataFrame, teams_df: pd.DataFrame):
    team_logo_lookup = teams_df.set_index('short_name')['logo_url'].to_dict()
    team_rank_lookup = teams_df.set_index('short_name')['position'].to_dict()
    gw_cols = [col for col in diff_matrix.columns if col.startswith('GW')]
    min_val, max_val = 1, 20

    html = """
    <style>
        .fixture-planner { width: 100%; border-collapse: collapse; font-family: 'Inter', sans-serif; border-radius: 8px; overflow: hidden; }
        .fixture-planner th, .fixture-planner td { text-align: center; padding: 8px 4px; border: 1px solid #444; min-width: 65px; }
        .fixture-planner th { background-color: #333; color: white; font-size: 14px; }
        .team-cell { width: 85px; background-color: #f0f2f6; padding: 4px; }
        .team-cell img { width: 35px; height: 35px; }
        .team-cell span { display: block; font-size: 13px; font-weight: bold; color: #333; margin-top: 2px; }
        .team-rank { font-size: 11px; font-weight: normal; color: #555; margin-top: 0; }
        .fixture-cell { vertical-align: middle; font-size: 13px; font-weight: bold; width: 70px; height: 60px; }
        .fixture-cell img { width: 25px; height: 25px; vertical-align: middle; }
        .opponent-rank { display: block; font-size: 11px; font-weight: normal; }
        .bg-easy { background-color: #35F00A; color: black; }
        .bg-medium { background-color: #FFF100; color: black; }
        .bg-hard { background-color: #FF0000; color: white; }
        .bg-blank { background-color: #373737; color: white; }
        .dgw-cell { font-size: 12px; line-height: 1.4; text-align: left; padding-left: 8px; }
    </style>
    <table class="fixture-planner"><thead><tr><th>Team</th>
    """
    for gw in gw_cols: html += f"<th>{gw}</th>"
    html += "</tr></thead><tbody>"

    for team_short_name, diff_row in diff_matrix.drop(columns=['Total']).iterrows():
        team_logo_url = team_logo_lookup.get(team_short_name, '')
        team_rank = team_rank_lookup.get(team_short_name, '?')
        html += f"<tr><td class='team-cell'><img src='{team_logo_url}'><br><span>{team_short_name}</span><span class='team-rank'>(อันดับ {team_rank})</span></td>"
        for gw in gw_cols:
            diff_score = diff_row[gw]
            opp_string = opp_matrix.loc[team_short_name, gw]
            css_class = get_difficulty_css_class(diff_score, min_val, max_val)
            cell_content = ""
            if opp_string == "BLANK": cell_content = "BLANK"
            elif "," in opp_string:
                cell_content = opp_string.replace(", ", "<br>")
                css_class = "dgw-cell " + css_class
            else:
                try:
                    last_paren = opp_string.rfind('(')
                    opp_rank_str = opp_string[last_paren:].strip()
                    main_part = opp_string[:last_paren].strip()
                    second_last_paren = main_part.rfind('(')
                    home_away = main_part[second_last_paren:].strip()
                    opp_short_name = main_part[:second_last_paren].strip()
                    opp_logo_url = team_logo_lookup.get(opp_short_name, '')
                    cell_content = f"<img src='{opp_logo_url}'><br>{home_away}<span class='opponent-rank'>{opp_rank_str}</span>"
                except: cell_content = opp_string
            html += f"<td class='fixture-cell {css_class}'>{cell_content}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

def display_understat_section(merged_players: pd.DataFrame, merged_teams: pd.DataFrame):
    st.subheader("📊 สถิติจาก Understat (xG, xA, xPTS)")
    DEFAULT_PHOTO_URL = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png"
    def get_player_image_html(photo_url, player_name, width=60):
        alt_text = str(player_name).replace("'", "").replace('"', '')
        src_url = photo_url if pd.notna(photo_url) else DEFAULT_PHOTO_URL
        return f'<img src="{src_url}" alt="{alt_text}" width="{width}" style="border-radius: 4px; min-height: {int(width*1.33)}px; background-color: #eee;" onerror="this.onerror=null;this.src=\'{DEFAULT_PHOTO_URL}\';">'

    col1, col2, col3 = st.columns(3)
    
    # --- Top 5 xG ---
    with col1:
        st.markdown("#### 🎯 Top 5 xG (โอกาสยิง)")
        if merged_players.empty or 'xG' not in merged_players.columns:
            st.caption("ไม่มีข้อมูล xG")
        else:
            for _, row in merged_players.nlargest(5, 'xG').iterrows():
                c1, c2 = st.columns([1, 4])
                with c1:
                    st.markdown(get_player_image_html(row['photo_url'], row['player_name'], 60), unsafe_allow_html=True)
                with c2:
                    # ใช้ <br> เพื่อให้ขึ้นบรรทัดใหม่ได้จริง
                    st.markdown(f"**{row['player_name']}** ({row['team_short']})<br>xG: {row['xG']:.2f} | ยิง: {row['goals_scored']:.0f}", unsafe_allow_html=True)
    
    # --- Top 5 xA ---
    with col2:
        st.markdown("#### 🅰️ Top 5 xA (โอกาสจ่าย)")
        if merged_players.empty or 'xA' not in merged_players.columns:
            st.caption("ไม่มีข้อมูล xA")
        else:
            for _, row in merged_players.nlargest(5, 'xA').iterrows():
                c1, c2 = st.columns([1, 4])
                with c1:
                    st.markdown(get_player_image_html(row['photo_url'], row['player_name'], 60), unsafe_allow_html=True)
                with c2:
                    st.markdown(f"**{row['player_name']}** ({row['team_short']})<br>xA: {row['xA']:.2f} | จ่าย: {row['assists']:.0f}", unsafe_allow_html=True)
    
    # --- Top 5 xPTS ---
    with col3:
        st.markdown("#### 📈 Top 5 xPTS (คะแนนคาดหวัง)")
        if merged_teams.empty or 'xpts' not in merged_teams.columns:
            st.caption("ไม่มีข้อมูล xPTS")
        else:
            for _, row in merged_teams.nlargest(5, 'xpts').iterrows():
                c1, c2 = st.columns([1, 4])
                with c1: 
                    logo = row['logo_url'] if pd.notna(row['logo_url']) else ""
                    st.markdown(f'<img src="{logo}" width="40" style="min-height: 40px; background-color: #eee; border-radius: 4px;">', unsafe_allow_html=True)
                with c2: 
                    display_name = row['name'] if pd.notna(row['name']) else row['title']
                    st.markdown(f"**{display_name}**<br>xPTS: {row['xpts']:.2f}", unsafe_allow_html=True)
    
    st.markdown("---")

def display_home_dashboard(feat_df: pd.DataFrame, nf_df: pd.DataFrame, teams_df: pd.DataFrame, opp_matrix: pd.DataFrame, diff_matrix: pd.DataFrame, rotation_pairs: pd.DataFrame, merged_understat_players: pd.DataFrame, merged_understat_teams: pd.DataFrame):
    DEFAULT_PHOTO_URL = "https://resources.premierleague.com/premierleague/photos/players/110x140/p-blank.png"
    def get_player_image_html(photo_url, player_name, width=60):
        alt_text = str(player_name).replace("'", "").replace('"', '')
        src_url = photo_url if pd.notna(photo_url) else DEFAULT_PHOTO_URL
        return f'<img src="{src_url}" alt="{alt_text}" width="{width}" style="border-radius: 4px; min-height: {int(width*1.33)}px; background-color: #eee;" onerror="this.onerror=null;this.src=\'{DEFAULT_PHOTO_URL}\';">'

    dgw_teams = nf_df[nf_df['num_fixtures'] == 2]
    bgw_teams = nf_df[nf_df['num_fixtures'] == 0]
    if not dgw_teams.empty or not bgw_teams.empty:
        st.subheader("🚨 สรุปทีม DGW / BGW")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🟩 Double Gameweek (น่าซื้อ)")
            if dgw_teams.empty: st.caption("ไม่มีทีม Double Gameweek")
            else:
                for _, row in dgw_teams.merge(teams_df[['id', 'short_name', 'logo_url']], left_on='team', right_on='id').iterrows():
                    c1, c2 = st.columns([1, 4])
                    with c1: st.image(row['logo_url'], width=40)
                    with c2: st.markdown(f"**{row['short_name']}**"); st.caption(f"{row['opponent_str']}")
        with col2:
            st.markdown("#### 🟥 Blank Gameweek (น่าขาย)")
            if bgw_teams.empty: st.caption("ไม่มีทีม Blank Gameweek")
            else:
                for _, row in bgw_teams.merge(teams_df[['id', 'short_name', 'logo_url']], left_on='team', right_on='id').iterrows():
                    c1, c2 = st.columns([1, 4])
                    with c1: st.image(row['logo_url'], width=40)
                    with c2: st.markdown(f"**{row['short_name']}**"); st.caption("ไม่มีนัดแข่ง")
        st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("👑 5 สุดยอดกัปตัน")
        captains = feat_df.nlargest(5, 'pred_points')
        if captains.empty:
            st.caption("ไม่มีข้อมูลกัปตัน")
        else:
            for _, row in captains.iterrows():
                c1, c2 = st.columns([1, 4])
                with c1:
                    st.markdown(get_player_image_html(row['photo_url'], row['web_name'], 60), unsafe_allow_html=True)
                with c2:
                    st.markdown(f"**{row['web_name']}** ({row['team_short']})")
                    st.markdown(f"**คะแนน: {row['pred_points']:.1f}**")
                    st.caption(f"คู่แข่ง: {row['opponent_str']}")
                    st.caption(f"ราคาปัจจุบัน: £{row['now_cost']/10.0:.1f}m")

    with col2:
        st.subheader("💹 ราคากำลังขึ้น 🔼")
        risers = feat_df[feat_df['cost_change_start'] > 0].sort_values('cost_change_start', ascending=False).head(5)
        if risers.empty:
            st.caption("ไม่มีนักเตะราคาขึ้นในสัปดาห์นี้")
        else:
            for _, row in risers.iterrows():
                c1, c2 = st.columns([1, 4])
                with c1: 
                    st.markdown(get_player_image_html(row['photo_url'], row['web_name'], 60), unsafe_allow_html=True)
                with c2: 
                    st.markdown(f"**{row['web_name']}** ({row['team_short']})")
                    weekly_change = row['cost_change_event']
                    if weekly_change > 0:
                        st.caption(f"▲ ขึ้นสัปดาห์นี้: +£{weekly_change/10.0:.1f}m")
                    st.caption(f"▲ ขึ้นรวม: +£{row['cost_change_start']/10.0:.1f}m")
                    st.caption(f"ราคาปัจจุบัน: £{row['now_cost']/10.0:.1f}m")

    with col3:
        st.subheader("🔻 ราคากำลังลง 📉")
        fallers = feat_df[feat_df['cost_change_start'] < 0].sort_values('cost_change_start', ascending=True).head(5)
        if fallers.empty:
            st.caption("ไม่มีนักเตะราคาลงในสัปดาห์นี้")
        else:
            for _, row in fallers.iterrows():
                c1, c2 = st.columns([1, 4])
                with c1: 
                    st.markdown(get_player_image_html(row['photo_url'], row['web_name'], 60), unsafe_allow_html=True)
                with c2: 
                    st.markdown(f"**{row['web_name']}** ({row['team_short']})")
                    weekly_change = row['cost_change_event']
                    if weekly_change < 0:
                        st.caption(f"▼ ลงสัปดาห์นี้: -£{abs(weekly_change/10.0):.1f}m")
                    st.caption(f"▼ ลงรวม: -£{abs(row['cost_change_start']/10.0):.1f}m")
                    st.caption(f"ราคาปัจจุบัน: £{row['now_cost']/10.0:.1f}m")
    st.markdown("---")

    st.subheader("⭐ Top 20 นักเตะคะแนนคาดการณ์สูงสุด")
    st.caption("หมายเหตุ: ตารางนี้อาจยังแสดงไอคอนรูปเสีย 🖼️ หากไม่มีรูปใน API ครับ")
    top_tbl = feat_df[["photo_url", "web_name", "team_short", "element_type", "now_cost", "form", "avg_fixture_ease", "pred_points"]].copy()
    top_tbl.rename(columns={"element_type": "pos", "now_cost": "price", "avg_fixture_ease": "fixture_ease"}, inplace=True)
    top_tbl["pos"] = top_tbl["pos"].map(POSITIONS)
    top_tbl["price"] = (top_tbl["price"] / 10.0)
    
    top_players = top_tbl.sort_values("pred_points", ascending=False).head(20)
    
    top_players.reset_index(drop=True, inplace=True)
    top_players.index = np.arange(1, len(top_players) + 1)
    top_players.index.name = "ลำดับ"
    
    cols_to_show = ["photo_url", "web_name", "team_short", "pos", "price", "form", "fixture_ease", "pred_points"]
    
    st.data_editor(
        top_players[cols_to_show],
        column_config={
            "photo_url": st.column_config.ImageColumn(
                "รูป", help="รูปนักเตะ", width="small"
            ),
            "web_name": st.column_config.TextColumn(
                "ชื่อนักเตะ", width="medium"
            ),
            "team_short": st.column_config.TextColumn(
                "ทีม", width="small"
            ),
            "pos": st.column_config.TextColumn(
                "ตำแหน่ง", width="small"
            ),
            "price": st.column_config.NumberColumn(
                "ราคา (£)", format="£%.1f"
            ),
            "form": st.column_config.NumberColumn(
                "ฟอร์ม", format="%.1f"
            ),
            "fixture_ease": st.column_config.NumberColumn(
                "ความง่าย", help="ความง่ายของเกมถัดไป", format="%.2f"
            ),
            "pred_points": st.column_config.NumberColumn(
                "คะแนนคาดการณ์", format="%.1f"
            ),
        },
        column_order=("ลำดับ", "photo_url", "web_name", "team_short", "pos", "price", "form", "fixture_ease", "pred_points"),
        use_container_width=True,
        height=750,
        disabled=True
    )
    st.markdown("---")
    
    display_understat_section(merged_understat_players, merged_understat_teams)

    st.subheader("🔥 นักเตะน่าสนใจ (Player Trends)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 🔥 Top 5 ฟอร์มแรง")
        for _, row in feat_df.nlargest(5, 'form').iterrows():
            c1, c2 = st.columns([1, 3])
            with c1: st.markdown(get_player_image_html(row['photo_url'], row['web_name'], 50), unsafe_allow_html=True)
            with c2: st.markdown(f"**{row['web_name']}**"); st.caption(f"ฟอร์ม: {row['form']:.1f}")
    with col2:
        st.markdown("#### 💎 Top 5 ตัวแรร์ (<10%)")
        for _, row in feat_df[feat_df['selected_by_percent'] < 10.0].nlargest(5, 'pred_points').iterrows():
            c1, c2 = st.columns([1, 3])
            with c1: st.markdown(get_player_image_html(row['photo_url'], row['web_name'], 50), unsafe_allow_html=True)
            with c2: st.markdown(f"**{row['web_name']}**"); st.caption(f"คะแนน: {row['pred_points']:.1f} | คนมี: {row['selected_by_percent']:.1f}%")
    with col3:
        st.markdown("#### 👥 Top 5 ขวัญใจมหาชน")
        for _, row in feat_df.nlargest(5, 'selected_by_percent').iterrows():
            c1, c2 = st.columns([1, 3])
            with c1: st.markdown(get_player_image_html(row['photo_url'], row['web_name'], 50), unsafe_allow_html=True)
            with c2: st.markdown(f"**{row['web_name']}**"); st.caption(f"คนมี: {row['selected_by_percent']:.1f}%")
    st.markdown("---")

    st.subheader("🗓️ ตารางแข่ง 5 นัดล่วงหน้า (Fixture Planner)")
    st.markdown("เรียงตามความง่าย ➡ ยาก **อันดับตารางคะแนน** ของคู่แข่ง (สีเขียว = ง่าย, สีเหลือง = ปานกลาง, สีแดง = ยาก)")
    display_visual_fixture_planner(opp_matrix, diff_matrix, teams_df)
    st.markdown("---")

    st.subheader("💰 กราฟนักเตะคุ้มค่า (Value Finder)")
    st.markdown("🪄 เอาเมาส์ไปชี้เพื่อดูชื่อนักเตะได้เลย!แต่ละสีบอกตำแหน่ง ส่วนจุดใกล้มุมซ้ายบนที่สุดคือของดีราคาถูกในตำแหน่งนั้นๆ 💰")
    value_df = feat_df[feat_df['pred_points'] > 1.2].copy()
    value_df['price'] = value_df['now_cost'] / 10.0
    value_df['position'] = value_df['element_type'].map(POSITIONS)
    chart = alt.Chart(value_df).mark_circle(size=80, opacity=0.85, stroke='#CCCCCC',strokeWidth=0.8).encode(
        x=alt.X('price', title='ราคา (£)'), y=alt.Y('pred_points', title='คะแนนคาดการณ์'),
        color=alt.Color('position', scale=alt.Scale(domain=['GK', 'DEF', 'MID', 'FWD'], range=['#EE7733', '#0077BB', '#CC3311', '#33BBEE'])),
        tooltip=['web_name', 'team_short', 'position', 'price', 'pred_points']
    ).interactive()
    st.altair_chart(chart, use_container_width=True)
    st.markdown("---")
    
    st.markdown("#### 🥅 Top 10 คู่ผู้รักษาประตู (GK Rotation Pairs)")
    st.caption(f"ค้นหาคู่ GK ที่ตารางแข่งสลับกันดีที่สุด (งบรวมไม่เกิน £9.0m)")
    st.dataframe(rotation_pairs, use_container_width=True, hide_index=True)

def display_player_comparison(player1_data, player2_data):
    # Map display categories to dataframe columns
    category_map = {
        'Form': 'form',
        'ICT Index': 'ict_index',
        'xG': 'xG',
        'xA': 'xA',
        'Fixture Ease': 'avg_fixture_ease',
        'Predicted Pts': 'pred_points'
    }
    categories = list(category_map.keys())
    
    # Helper to safely get float value
    def get_val(row, col):
        try:
            val = float(row.get(col, 0))
            # Normalize Fixture Ease to 0-10 scale for visualization if it's 0-1
            if col == 'avg_fixture_ease' and val <= 1.0:
                return val * 10
            return val
        except:
            return 0.0

    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
      r=[get_val(player1_data, category_map[c]) for c in categories],
      theta=categories,
      fill='toself',
      name=player1_data.get('web_name', 'Player 1'),
      line_color='#1f77b4', # Blue
      fillcolor='rgba(31, 119, 180, 0.3)'
    ))
    
    fig.add_trace(go.Scatterpolar(
      r=[get_val(player2_data, category_map[c]) for c in categories],
      theta=categories,
      fill='toself',
      name=player2_data.get('web_name', 'Player 2'),
      line_color='#ff7f0e', # Orange
      fillcolor='rgba(255, 127, 14, 0.3)'
    ))

    fig.update_layout(
      polar=dict(radialaxis=dict(visible=True, range=[0, 10])), # Adjust scale if needed
      showlegend=True,
      margin=dict(l=40, r=40, t=40, b=40)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_injury_watch(feat_df: pd.DataFrame):
    st.subheader("🏥 Injury & Suspension Watch (เช็คตัวเจ็บ/แบน)")
    
    # Filter players with < 100% chance of playing
    # Ensure chance_of_playing_next_round is numeric, handle NaNs (assume 100 if NaN)
    feat_df['chance_of_playing_next_round'] = pd.to_numeric(feat_df['chance_of_playing_next_round'], errors='coerce').fillna(100)
    
    injured_players = feat_df[feat_df['chance_of_playing_next_round'] < 100].copy()
    
    if injured_players.empty:
        st.success("✅ ไม่มีนักเตะบาดเจ็บหรือติดโทษแบนในขณะนี้ (หรือ API ยังไม่อัปเดต)")
        return

    # Select relevant columns
    cols_to_show = ["photo_url", "web_name", "team_short", "pos", "chance_of_playing_next_round", "news"]
    
    # Prepare for display
    injured_players['pos'] = injured_players['element_type'].map(POSITIONS)
    injured_players = injured_players.sort_values(['chance_of_playing_next_round', 'web_name'], ascending=[False, True])
    
    # Rename columns for display if needed, or use column_config
    
    st.data_editor(
        injured_players[cols_to_show],
        column_config={
            "photo_url": st.column_config.ImageColumn(
                "รูป", width="small"
            ),
            "web_name": st.column_config.TextColumn(
                "ชื่อนักเตะ", width="medium"
            ),
            "team_short": st.column_config.TextColumn(
                "ทีม", width="small"
            ),
            "pos": st.column_config.TextColumn(
                "ตำแหน่ง", width="small"
            ),
            "chance_of_playing_next_round": st.column_config.ProgressColumn(
                "โอกาสลงเล่น (%)", 
                format="%d%%",
                min_value=0,
                max_value=100,
                width="medium"
            ),
            "news": st.column_config.TextColumn(
                "ข่าว/อาการ", width="large"
            )
        },
        column_order=("photo_url", "web_name", "team_short", "pos", "chance_of_playing_next_round", "news"),
        use_container_width=True,
        height=400,
        disabled=True,
        hide_index=True
    )