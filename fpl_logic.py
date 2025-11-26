import numpy as np
import pandas as pd
import streamlit as st
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, LpBinary, LpStatus, PULP_CBC_CMD
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_helpers import get_player_history

POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
TEAM_MAP_COLS = ["id", "code", "name", "short_name", "strength_overall_home", "strength_overall_away",
                 "strength_attack_home", "strength_attack_away", "strength_defence_home", "strength_defence_away","position"]



def generate_penalty_takers_map(elements_df: pd.DataFrame, teams_df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    สร้าง Dictionary รายชื่อคนยิงจุดโทษแบบ Dynamic จาก API
    โดยใช้ฟิลด์ 'penalties_order' ที่มากับข้อมูลนักเตะ
    """
    penalty_map = {}
    
    # สร้าง Map รหัสทีม -> ชื่อย่อทีม (เช่น 1 -> 'ARS')
    id_to_short_name = teams_df.set_index('id')['short_name'].to_dict()
    
    # กรองเฉพาะคนที่มีลำดับการยิงจุดโทษ (penalties_order ไม่เป็น NULL)
    # และเรียงลำดับความสำคัญ (1 มาก่อน)
    takers_df = elements_df[elements_df['penalties_order'].notna()].sort_values('penalties_order')
    
    for _, player in takers_df.iterrows():
        team_id = player['team']
        team_short = id_to_short_name.get(team_id)
        
        # ใช้ web_name (ชื่อหลังเสื้อ)
        # และใช้ unidecode เพื่อจัดการชื่อที่มีอักขระพิเศษรอไว้เลย
        from unidecode import unidecode
        player_name_clean = unidecode(str(player['web_name'])).lower().strip()
        
        if team_short:
            if team_short not in penalty_map:
                penalty_map[team_short] = []
            penalty_map[team_short].append(player_name_clean)
            
    return penalty_map

def current_and_next_event(events: List[Dict]) -> Tuple[Optional[int], Optional[int]]:
    cur = next_ev = None
    for ev in events:
        if ev.get("is_current"):
            cur = ev["id"]
        if ev.get("is_next"):
            next_ev = ev["id"]
    if cur is None and next_ev is not None:
        cur = next_ev - 1 if next_ev > 1 else 1
    return cur, next_ev

def build_master_tables(bootstrap: Dict, fixtures: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    elements = pd.DataFrame(bootstrap["elements"])
    teams = pd.DataFrame(bootstrap["teams"])
    
    teams['strength_overall'] = (teams['strength_overall_home'] + teams['strength_overall_away']) / 2.0
    teams['strength_attack_overall'] = (teams['strength_attack_home'] + teams['strength_attack_away']) / 2.0
    teams['strength_defence_overall'] = (teams['strength_defence_home'] + teams['strength_defence_away']) / 2.0

    cols_to_keep = [col for col in TEAM_MAP_COLS + ['strength_overall', 'strength_attack_overall', 'strength_defence_overall'] if col in teams.columns]
    teams = teams[cols_to_keep].copy()
    
    events = pd.DataFrame(bootstrap.get("events", []))
    # --- FIX: Removed markdown syntax, plain string concatenation ---
    teams['logo_url'] = 'https://resources.premierleague.com/premierleague/badges/70/t' + teams['code'].astype(str) + '.png'
    
    elements = elements.merge(teams[["id","short_name"]], left_on="team", right_on="id", suffixes=("","_team"))
    elements.rename(columns={"short_name":"team_short"}, inplace=True)
    fixtures_df = pd.DataFrame(fixtures)
    
    return elements, teams, events, fixtures_df

def next_fixture_features(fixtures_df: pd.DataFrame, teams_df: pd.DataFrame, event_id: int) -> pd.DataFrame:
    next_gw_fixtures = fixtures_df[fixtures_df["event"] == event_id].copy()
    rows = []
    team_data = {team_id: {'home_fixtures': [], 'away_fixtures': []} for team_id in teams_df['id'].unique()}
    teams_idx = teams_df.set_index('id')

    for _, row in next_gw_fixtures.iterrows():
        home_team_id, away_team_id = row['team_h'], row['team_a']
        team_data[home_team_id]['home_fixtures'].append(away_team_id)
        team_data[away_team_id]['away_fixtures'].append(home_team_id)

    for team_id, fixtures_info in team_data.items():
        home_opps = fixtures_info['home_fixtures']
        away_opps = fixtures_info['away_fixtures']
        num_fixtures = len(home_opps) + len(away_opps)
        
        opp_list = []
        for opp_id in home_opps:
            opp_list.append(f"{teams_idx.loc[opp_id, 'short_name']} (H)")
        for opp_id in away_opps:
            opp_list.append(f"{teams_idx.loc[opp_id, 'short_name']} (A)")
        
        if num_fixtures == 0:
            rows.append({
                'team': team_id, 'num_fixtures': 0, 
                'total_opp_def_str': 0, 'total_opp_att_str': 0,
                'avg_fixture_ease': 0, 'fixture_ease_att': 0, 'fixture_ease_def': 0,
                'opponent_str': "BLANK"
            })
            continue

        opponent_str = ", ".join(opp_list)
        total_opp_def_str = 0
        total_opp_att_str = 0
        
        for opp_id in home_opps:
            total_opp_def_str += teams_idx.loc[opp_id, 'strength_defence_away']
            total_opp_att_str += teams_idx.loc[opp_id, 'strength_attack_away']
        for opp_id in away_opps:
            total_opp_def_str += teams_idx.loc[opp_id, 'strength_defence_home']
            total_opp_att_str += teams_idx.loc[opp_id, 'strength_attack_home']

        # Normalize Ease (Higher is easier)
        # Attackers want weak Opponent Defense
        # Defenders want weak Opponent Attack
        max_def = teams_idx['strength_defence_home'].max()
        max_att = teams_idx['strength_attack_home'].max()
        
        rows.append({
            'team': team_id,
            'num_fixtures': num_fixtures,
            'total_opp_def_str': total_opp_def_str,
            'total_opp_att_str': total_opp_att_str,
            'avg_fixture_ease': 1.0 - (total_opp_def_str / (num_fixtures * max_def)), # Legacy fallback
            'fixture_ease_att': 1.0 - (total_opp_def_str / (num_fixtures * max_def)), # For Attackers (vs Def)
            'fixture_ease_def': 1.0 - (total_opp_att_str / (num_fixtures * max_att)), # For Defenders (vs Att)
            'opponent_str': opponent_str,
            'venue_multiplier': 1.0 + (len(home_opps) * 0.1) - (len(away_opps) * 0.1)
        })

    return pd.DataFrame(rows)

def calculate_smart_selection_score(player_row):
    score = 0.0
    score += player_row.get('pred_points', 0) * 0.4
    
    if player_row.get('xG', 0) > 0 or player_row.get('xA', 0) > 0:
        minutes_played = player_row.get('minutes', 0)
        games_played_est = max(1, minutes_played / 90.0)
        xgi_bonus = (player_row.get('xG', 0) * 5 + player_row.get('xA', 0) * 3) / games_played_est
        score += xgi_bonus * 0.3
    
    score += player_row.get('form', 0) * 0.15
    score += player_row.get('avg_fixture_ease', 0) * 10 * 0.1
    score += player_row.get('avg_fixture_ease', 0) * 10 * 0.1
    
    # --- IMPROVED: Stricter penalties for unavailable players ---
    play_prob = player_row.get('play_prob', 1.0)
    if play_prob == 0:
        score *= 0.0  # Force score to 0 if definitely not playing
    elif play_prob < 0.5:
        score *= 0.2  # Heavy penalty for low chance
    else:
        score *= (0.5 + 0.5 * play_prob)
    
    if player_row.get('num_fixtures', 1) == 2:
        score *= 1.3
    if player_row.get('num_fixtures', 1) == 0:
        score = 0
    
    return score

def engineer_features_enhanced(elements: pd.DataFrame, teams: pd.DataFrame, nf: pd.DataFrame, understat_players: pd.DataFrame, my_team_ids: List[int] = None, gameweek: int = 1) -> pd.DataFrame:
    elements = elements.copy()
    
    # --- NEW: Parallel Weighted Form Calculation ---
    # Fetch history and calculate weighted form for all players
    # Use ThreadPoolExecutor for I/O bound tasks (API calls)
    weighted_forms = {}
    form_trends = {}
    avg_minutes_map = {}
    variance_map = {}
    
    # Limit to relevant players to save time (e.g., > 0.5% ownership or price > 4.0)
    # Optimization: Only fetch for Top 250 owned + Top 100 points to reduce API calls (approx 300 unique)
    # This prevents hundreds of concurrent requests for irrelevant players.
    
    # Ensure columns are numeric for sorting
    elements['selected_by_percent'] = pd.to_numeric(elements['selected_by_percent'], errors='coerce').fillna(0)
    elements['total_points'] = pd.to_numeric(elements['total_points'], errors='coerce').fillna(0)
    elements['minutes'] = pd.to_numeric(elements['minutes'], errors='coerce').fillna(0)
    
    top_owned = elements.nlargest(250, 'selected_by_percent')['id'].tolist()
    top_points = elements.nlargest(100, 'total_points')['id'].tolist()
    
    # Always include user's current team to ensure xMins is calculated for them
    relevant_players = set(top_owned + top_points)
    if my_team_ids:
        relevant_players.update(my_team_ids)
    relevant_players = list(relevant_players)

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_id = {executor.submit(analyze_player_history, pid): pid for pid in relevant_players}
        for future in as_completed(future_to_id):
            pid = future_to_id[future]
            try:
                res = future.result()
                weighted_forms[pid] = res['weighted_form']
                form_trends[pid] = res['form_trend']
                avg_minutes_map[pid] = res['avg_minutes']
                variance_map[pid] = res.get('points_variance', 0.0)
            except Exception:
                weighted_forms[pid] = 0.0
                form_trends[pid] = "➖"
                avg_minutes_map[pid] = 0.0
                variance_map[pid] = 0.0
    
    # Map calculated values. For those not in relevant_players, fallback to standard 'form'
    elements['weighted_form'] = elements['id'].map(weighted_forms)
    # Fallback: Use standard form for non-VIP players
    elements['weighted_form'] = elements['weighted_form'].fillna(pd.to_numeric(elements['form'], errors='coerce').fillna(0.0))
    
    elements['form_trend'] = elements['id'].map(form_trends).fillna("➖")
    
    # Fallback for avg_minutes: Use 'minutes' / gameweek (approx) if not calculated
    # This ensures players from smaller teams (not in top owned) still have an xMins value
    def get_fallback_minutes(row):
        if row['id'] in avg_minutes_map:
            return avg_minutes_map[row['id']]
        # Fallback: Season average
        return row['minutes'] / max(1, gameweek)

    elements['avg_minutes'] = elements.apply(get_fallback_minutes, axis=1)
    elements['points_variance'] = elements['id'].map(variance_map).fillna(0.0)

    elements["element_type"] = pd.to_numeric(elements["element_type"], errors='coerce').fillna(0).astype(int)
    elements = elements.merge(nf, on="team", how="left")
    elements['num_fixtures'] = elements['num_fixtures'].fillna(0).astype(int)
    elements['avg_fixture_ease'] = elements['avg_fixture_ease'].fillna(0)
    elements['opponent_str'] = elements['opponent_str'].fillna("-")

    cols_to_process = ["form", "points_per_game", "ict_index", "selected_by_percent", "now_cost", 
                       "minutes", "goals_scored", "assists", "clean_sheets", "cost_change_event",
                       "cost_change_start", "transfers_in_event", "transfers_out_event", "code"]
    for col in cols_to_process:
        if col in elements.columns:
            elements[col] = pd.to_numeric(elements[col], errors="coerce").fillna(0)
            
    if 'cost_change_event' in elements.columns:
        elements['cost_change_event'] = elements['cost_change_event'].astype(int)

    # --- FIX: Removed markdown syntax, plain string concatenation ---
    elements['photo_url'] = 'https://resources.premierleague.com/premierleague/photos/players/110x140/p' + elements['code'].astype(int).astype(str) + '.png'
    
    elements["chance_of_playing_next_round"] = pd.to_numeric(elements["chance_of_playing_next_round"], errors="coerce").fillna(100)
    elements["play_prob"] = elements["chance_of_playing_next_round"] / 100.0

    if not understat_players.empty and 'xG' in understat_players.columns:
        # Normalize names for better matching
        import unidecode
        def normalize_name(n): return unidecode.unidecode(str(n)).lower().replace("-", " ").replace("'", "")

        elements['web_name_norm'] = elements['web_name'].apply(normalize_name)
        elements['full_name_norm'] = (elements['first_name'] + " " + elements['second_name']).apply(normalize_name)
        understat_players['player_name_norm'] = understat_players['player_name'].apply(normalize_name)
        
        us_dedup = understat_players[['player_name_norm', 'xG', 'xA']].drop_duplicates('player_name_norm')
        
        # Merge 1: Match on Web Name
        elements = elements.merge(us_dedup, left_on='web_name_norm', right_on='player_name_norm', how='left', suffixes=('', '_web'))
        
        # Merge 2: Match on Full Name
        elements = elements.merge(us_dedup, left_on='full_name_norm', right_on='player_name_norm', how='left', suffixes=('', '_full'))
        
        # Coalesce xG/xA
        elements['xG'] = elements['xG'].fillna(elements['xG_full']).fillna(0)
        elements['xA'] = elements['xA'].fillna(elements['xA_full']).fillna(0)
        
        # Cleanup
        drop_cols = ['web_name_norm', 'full_name_norm', 'player_name_norm', 'player_name_norm_full', 'xG_full', 'xA_full']
        elements.drop(columns=[c for c in drop_cols if c in elements.columns], inplace=True, errors='ignore')
    else:
        elements['xG'] = 0.0
        elements['xA'] = 0.0

    if elements['xG'].sum() > 0: 
        games_played_est = (elements['minutes'] / 90.0).replace(0, 1)
        xg_per_game = elements['xG'] / games_played_est
        xa_per_game = elements['xA'] / games_played_est
        goal_pts_mult = np.select([elements["element_type"] == 2, elements["element_type"] == 3, elements["element_type"] == 4], [6.0, 5.0, 4.0], default=0.0)
        att_base = (xg_per_game * goal_pts_mult) + (xa_per_game * 3.0)
    else:
        att_base = 0.6 * elements["points_per_game"] + 0.4 * (elements["ict_index"] / 10.0)

    def_base = elements['form'] * 0.1 
    elements['base_xP'] = (att_base * 0.6) + (elements['form'] * 0.4) + def_base
    pos_mult = np.select([elements["element_type"] == 1, elements["element_type"] == 2, elements["element_type"] == 3, elements["element_type"] == 4], [0.9, 0.95, 1.0, 1.05], default=1.0)

    # 1. สร้าง Dynamic Map ขึ้นมา ณ เวลานั้นเลย
    dynamic_penalty_takers = generate_penalty_takers_map(elements, teams)

    # --- UPGRADE: xMins Approximation ---
    # xMins = min(90, avg_minutes * play_prob)
    # play_prob is already 0.0-1.0 derived from chance_of_playing_next_round
    elements['xMins'] = elements.apply(lambda row: min(90, row.get('avg_minutes', 0) * row.get('play_prob', 0)), axis=1).astype(int)
    
    # --- UPGRADE: Prediction Logic ---
    
    # --- UPGRADE: Prediction Logic ---
    def calculate_dynamic_pred(row):
        score = 0.0
        
        # 1. Base Points (from API)
        score += float(row.get('pred_points', 0)) * 0.4
        
        # 2. Form
        score += float(row.get('form', 0)) * 0.15
        
        # 3. Granular Fixture Difficulty
        pos = row.get('element_type', 3)
        if pos in [1, 2]: # GK, DEF -> Want weak Opponent Attack
            fix_ease = row.get('fixture_ease_def', row.get('avg_fixture_ease', 0))
        else: # MID, FWD -> Want weak Opponent Defense
            fix_ease = row.get('fixture_ease_att', row.get('avg_fixture_ease', 0))
            
        score += fix_ease * 10 * 0.15 # Increased weight for granular difficulty
        
        # 4. xG/xA Bonus
        if row.get('xG', 0) > 0 or row.get('xA', 0) > 0:
            mins = float(row.get('minutes', 0))
            games = max(1, mins / 90.0)
            xgi_per_90 = (row.get('xG', 0) * 5 + row.get('xA', 0) * 3) / games
            score += xgi_per_90 * 0.3
            
        # 5. Set Piece Bonus (Dynamic Version)
        team_short = row.get('team_short', '')
        from unidecode import unidecode
        web_name_clean = unidecode(str(row.get('web_name', ''))).lower().strip()
        
        # เช็คจาก Map ที่สร้างจาก API
        if team_short in dynamic_penalty_takers:
            team_takers = dynamic_penalty_takers[team_short]
            
            # ถ้าเป็นมือ 1 (คนแรกใน list)
            if len(team_takers) > 0 and web_name_clean == team_takers[0]:
                score += 0.8
            # ถ้าเป็นมือ 2 (คนที่สองใน list)
            elif len(team_takers) > 1 and web_name_clean == team_takers[1]:
                score += 0.4
        
        # 6. xMins Penalty (Availability)
        # 6. xMins Penalty (Availability & Rotation)
        # Use xMins / 90.0 as the multiplier
        x_mins = float(row.get('xMins', 0))
        play_prob = float(row.get('play_prob', 1.0))
        
        if play_prob == 0: 
            score = 0
        else:
            # If xMins is 0 (e.g. new player or no history), fallback to play_prob logic
            if x_mins == 0 and play_prob > 0:
                 if play_prob < 0.5: score *= 0.2
                 elif play_prob < 0.75: score *= 0.6
                 else: score *= (0.7 + 0.3 * play_prob)
            else:
                # Use xMins ratio
                # Example: xMins = 60 -> score *= 0.66
                # Example: xMins = 90 -> score *= 1.0
                score *= (x_mins / 90.0)
        
        # 7. DGW/BGW
        num_fix = row.get('num_fixtures', 1)
        if num_fix == 2: score *= 1.6 # DGW Bonus
        elif num_fix == 0: score = 0 # BGW
        
        # 8. Venue Adjustment (Home/Away)
        venue_mult = float(row.get('venue_multiplier', 1.0))
        score *= venue_mult
        
        return score

    elements['pred_points'] = elements.apply(calculate_dynamic_pred, axis=1)
    elements['selection_score'] = elements.apply(calculate_smart_selection_score, axis=1)

    return elements

def smart_bench_order(bench_df: pd.DataFrame) -> pd.DataFrame:
    bench_gk = bench_df[bench_df['element_type'] == 1]
    bench_outfield = bench_df[bench_df['element_type'] != 1].copy()
    bench_outfield['autosub_value'] = (
        bench_outfield['play_prob'] * 0.4 + 
        (bench_outfield.get('selection_score', bench_outfield['pred_points']) / 10) * 0.4 + 
        (bench_outfield['num_fixtures'] > 0).astype(int) * 0.2
    )
    bench_outfield = bench_outfield.sort_values('autosub_value', ascending=False)
    return pd.concat([bench_gk, bench_outfield])

def select_captain_vice(xi_df: pd.DataFrame) -> Dict[str, any]:
    """
    Selects Captain and Vice-Captain using Enhanced EV Calculation.
    Returns a dictionary with 'safe', 'differential', and 'vice' options.
    """
    xi_candidates = xi_df.copy()
    
    # --- 1. Calculate Risk Factor & EV ---
    # risk_factor = 1 - (variance_last_5 / max_variance) * 0.2
    # If max_variance is 0 (e.g. all players consistent or no data), risk factor is 1.0
    max_variance = xi_candidates['points_variance'].max()
    if max_variance == 0: max_variance = 1.0 # Avoid division by zero
    
    def calculate_ev(row):
        pred = row.get('pred_points', 0)
        var = row.get('points_variance', 0)
        risk_factor = 1.0 - (var / max_variance) * 0.2
        ev = (pred * 2) * risk_factor
        return ev, risk_factor
        
    # Apply calculation
    ev_results = xi_candidates.apply(calculate_ev, axis=1)
    xi_candidates['captain_ev'] = [x[0] for x in ev_results]
    xi_candidates['risk_factor'] = [x[1] for x in ev_results]
    
    # --- 2. Calculate Differential Score ---
    # differential_bonus = 1.0 + ((100 - ownership) / 100) * 0.3
    # differential_score = ev * differential_bonus
    def calculate_diff_score(row):
        ownership = float(row.get('selected_by_percent', 0))
        diff_bonus = 1.0 + ((100.0 - ownership) / 100.0) * 0.3
        return row['captain_ev'] * diff_bonus
        
    xi_candidates['diff_score'] = xi_candidates.apply(calculate_diff_score, axis=1)
    
    # --- 3. Select Options ---
    
    # Safe Pick: Highest EV
    safe_pick = xi_candidates.nlargest(1, 'captain_ev').iloc[0]
    
    # Differential Pick: Highest Diff Score (excluding the Safe Pick if possible)
    remaining_for_diff = xi_candidates[xi_candidates.index != safe_pick.name]
    if not remaining_for_diff.empty:
        diff_pick = remaining_for_diff.nlargest(1, 'diff_score').iloc[0]
    else:
        diff_pick = safe_pick
    
    # Vice Captains: Next best EVs (excluding Safe Pick)
    remaining = xi_candidates[xi_candidates.index != safe_pick.name]
    vc_options = remaining.nlargest(2, 'captain_ev')
    
    return {
        "safe_pick": {
            "id": int(safe_pick.name),
            "name": safe_pick['web_name'],
            "ev": safe_pick['captain_ev'],
            "risk": safe_pick['risk_factor'],
            "ownership": safe_pick['selected_by_percent']
        },
        "diff_pick": {
            "id": int(diff_pick.name),
            "name": diff_pick['web_name'],
            "ev": diff_pick['captain_ev'], # Show raw EV, but selected for differential potential
            "diff_score": diff_pick['diff_score'],
            "ownership": diff_pick['selected_by_percent']
        },
        "vice_picks": [
            {"id": int(row.name), "name": row['web_name'], "ev": row['captain_ev']} 
            for _, row in vc_options.iterrows()
        ]
    }

def analyze_lineup_insights(xi_df: pd.DataFrame, bench_df: pd.DataFrame) -> List[str]:
    """
    วิเคราะห์และให้คำแนะนำเกี่ยวกับการจัดตัว
    """
    insights = []
    
    # 1. เช็ค DGW/BGW
    dgw_count = (xi_df['num_fixtures'] == 2).sum()
    bgw_count = (xi_df['num_fixtures'] == 0).sum()
    
    if dgw_count > 0:
        insights.append(f"✅ คุณมี {dgw_count} คนใน XI ที่มี Double Gameweek")
    if bgw_count > 0:
        insights.append(f"⚠️ คุณมี {bgw_count} คนใน XI ที่ไม่มีนัดแข่ง!")
    
    # 2. เช็คโอกาสลงเล่น (รวมตัวจริงและสำรอง)
    all_players_df = pd.concat([xi_df, bench_df])
    low_prob_players = all_players_df[all_players_df['play_prob'] <= 0.75]
    if len(low_prob_players) > 0:
        names = ", ".join(low_prob_players['web_name'].tolist())
        insights.append(f"⚠️ นักเตะที่อาจไม่ลงเล่น: {names} (โอกาส ≤ 75%)")
    
    # 3. เช็ค Fixture Difficulty (avg_fixture_ease 0.3 คือยากมาก)
    hard_fixtures = xi_df[xi_df['avg_fixture_ease'] < 0.3]
    if len(hard_fixtures) > 2:
        insights.append(f"⚠️ คุณมี {len(hard_fixtures)} คนที่เจอคู่แข่งยาก (ความง่าย < 0.3)")
    
    # 4. เช็ค xG/xA Leaders
    if 'xG' in xi_df.columns and not xi_df.empty:
        try:
            top_xg_player = xi_df.nlargest(1, 'xG').iloc[0]
            insights.append(f"🎯 นักเตะที่มี xG สูงสุดใน XI: {top_xg_player['web_name']} ({top_xg_player['xG']:.2f})")
        except IndexError:
            pass # เกิดขึ้นได้ถ้า xi_df ว่าง
    
    # 5. เช็ค Bench Strength
    bench_score_col = 'selection_score' if 'selection_score' in bench_df.columns else 'pred_points'
    bench_total = bench_df.get(bench_score_col, 0).sum()
    if bench_total < 7.5:
        insights.append(f"⚠️ ตัวสำรองของคุณคะแนนคาดการณ์ต่ำ (คะแนนรวม: {bench_total:.1f})")
    
    return insights

@st.cache_data(ttl=300)
def get_fixture_difficulty_matrix(fixtures_df: pd.DataFrame, teams_df: pd.DataFrame, current_event: int, lookahead: int = 5):
    team_names = teams_df.set_index('id')['short_name'].to_dict()
    team_strength = teams_df.set_index('id')
    future_gws = list(range(current_event, min(current_event + lookahead, 39)))
    future_fixtures = fixtures_df[fixtures_df['event'].isin(future_gws)]
    
    opp_data = {team_id: {} for team_id in teams_df['id']}
    diff_data = {team_id: {} for team_id in teams_df['id']}

    for gw in future_gws:
        gw_fixtures = future_fixtures[future_fixtures['event'] == gw]
        teams_with_fixtures = set(gw_fixtures['team_h']).union(set(gw_fixtures['team_a']))

        for team_id in teams_df['id']:
            if team_id not in teams_with_fixtures:
                opp_data[team_id][f'GW{gw}'] = "BLANK"
                diff_data[team_id][f'GW{gw}'] = 0
                continue

            home_games = gw_fixtures[gw_fixtures['team_h'] == team_id]
            away_games = gw_fixtures[gw_fixtures['team_a'] == team_id]
            opponents, difficulties = [], []
            
            for _, game in home_games.iterrows():
                opp_id = game['team_a']
                opp_rank = team_strength.loc[opp_id, 'position']
                opponents.append(f"{team_names.get(opp_id, '?')} (H) (อันดับ {opp_rank})")
                difficulties.append(opp_rank)

            for _, game in away_games.iterrows():
                opp_id = game['team_h']
                opp_rank = team_strength.loc[opp_id, 'position']
                opponents.append(f"{team_names.get(opp_id, '?')} (A) (อันดับ {opp_rank})")
                difficulties.append(opp_rank)
            
            opp_data[team_id][f'GW{gw}'] = ", ".join(opponents)
            diff_data[team_id][f'GW{gw}'] = np.mean(difficulties) if difficulties else 0

    opp_df = pd.DataFrame(opp_data).T
    diff_df = pd.DataFrame(diff_data).T.fillna(0)
    opp_df.index = opp_df.index.map(team_names)
    diff_df.index = diff_df.index.map(team_names)
    diff_df['Total'] = diff_df.sum(axis=1)
    diff_df = diff_df.sort_values('Total', ascending=False)
    opp_df = opp_df.loc[diff_df.index]

    return opp_df, diff_df

def detect_fixture_swing(fixtures_df: pd.DataFrame, teams_df: pd.DataFrame, current_event: int) -> Dict[int, Dict]:
    """
    Detects teams with significant fixture difficulty swings (Improving/Worsening).
    Compare Avg Difficulty of Next 3 GWs vs Following 3 GWs.
    """
    # Get matrix for next 6 GWs
    _, diff_matrix = get_fixture_difficulty_matrix(fixtures_df, teams_df, current_event, lookahead=6)
    
    swing_data = {}
    team_map = teams_df.set_index('short_name')['id'].to_dict()
    
    for team_short, row in diff_matrix.iterrows():
        if team_short not in team_map: continue
        team_id = team_map[team_short]
        
        # Short Term: GW1, GW2, GW3 (relative to current)
        short_term_cols = [c for c in row.index if c.startswith('GW')][:3]
        # Long Term: GW4, GW5, GW6
        long_term_cols = [c for c in row.index if c.startswith('GW')][3:6]
        
        if not short_term_cols or not long_term_cols:
            swing_data[team_id] = {'trend': 'STABLE', 'val': 0}
            continue
            
        avg_short = row[short_term_cols].mean()
        avg_long = row[long_term_cols].mean()
        
        # Difficulty Scale: Higher = Easier (usually 1-20 rank, but here it seems to be rank-based?)
        # Wait, get_fixture_difficulty_matrix returns 'diff_df' where values are Opponent Rank (1-20).
        # So Higher Value = Weaker Opponent = Easier Fixture.
        
        diff = avg_long - avg_short
        
        # Thresholds
        # If Long Term is Easier (Higher Rank) -> IMPROVING (Buy Low now?)
        # Wait, if Next 3 are Hard (Low Rank) and Following 3 are Easy (High Rank) -> "Improving"
        # Actually, "Swing" usually means "About to change".
        # If Next 3 are Good, and Following 3 are Bad -> WORSENING (Sell High)
        # If Next 3 are Bad, and Following 3 are Good -> IMPROVING (Buy Low)
        
        trend = 'STABLE'
        if diff > 4.0: # Long term is much easier (e.g. avg rank 15 vs 10)
            trend = 'IMPROVING' # Green
        elif diff < -4.0: # Long term is much harder
            trend = 'WORSENING' # Red
            
        swing_data[team_id] = {
            'trend': trend,
            'short_avg': avg_short,
            'long_avg': avg_long,
            'diff': diff
        }
        
    return swing_data


@st.cache_data(ttl=300)
def find_rotation_pairs(difficulty_matrix: pd.DataFrame, teams_df: pd.DataFrame, all_players: pd.DataFrame, budget: float = 9.0):
    gks = all_players[
        (all_players['element_type'] == 1) &
        ((all_players['chance_of_playing_next_round'] > 75) | (all_players['pred_points'] > 0.5))
    ].copy()
    gks['price'] = gks['now_cost'] / 10.0
    gks['team_short'] = gks['team'].map(teams_df.set_index('id')['short_name'])
    cheap_gks = gks[gks['price'] <= (budget - 4.0)]
    
    pairs = []
    checked_pairs = set()
    for i, gk1 in cheap_gks.iterrows():
        for j, gk2 in cheap_gks.iterrows():
            if i >= j or (gk2['team'], gk1['team']) in checked_pairs: continue
            if (gk1['price'] + gk2['price']) > budget: continue
            checked_pairs.add((gk1['team'], gk2['team']))
            
            try:
                diff1 = difficulty_matrix.loc[gk1['team_short']]
                diff2 = difficulty_matrix.loc[gk2['team_short']]
            except KeyError: continue

            rotation_score = 0
            for col in difficulty_matrix.columns:
                if col == 'Total': continue
                rotation_score += min(diff1[col], diff2[col])
            
            pairs.append({
                'GK1': f"{gk1['web_name']} ({gk1['price']:.1f}m)",
                'GK2': f"{gk2['web_name']} ({gk2['price']:.1f}m)",
                'Total Cost': gk1['price'] + gk2['price'],
                'Rotation Score': rotation_score
            })

    if not pairs: return pd.DataFrame(columns=['GK1', 'GK2', 'Total Cost','Rating'])
    pairs_df = pd.DataFrame(pairs)
    if not pairs_df.empty:
        pairs_df = pairs_df.sort_values('Rotation Score', ascending=True)
        min_score, max_score = pairs_df['Rotation Score'].min(), pairs_df['Rotation Score'].max()
        def get_star_rating(score, min_s, max_s):
            if max_s == min_s: return "⭐⭐⭐⭐⭐"
            norm_score = (score - min_s) / (max_s - min_s)
            if norm_score < 0.2: return "⭐⭐⭐⭐⭐"
            elif norm_score < 0.4: return "⭐⭐⭐⭐"
            elif norm_score < 0.6: return "⭐⭐⭐"
            elif norm_score < 0.8: return "⭐⭐"
            else: return "⭐"
        pairs_df['Rating'] = pairs_df['Rotation Score'].apply(lambda x: get_star_rating(x, min_score, max_score))
    
    pairs_df['Total Cost'] = pairs_df['Total Cost'].apply(lambda x: f"£{x:.1f}m")
    return pairs_df[['GK1', 'GK2', 'Total Cost','Rating']].head(10).reset_index(drop=True)

@st.cache_data(ttl=300)
def predict_next_n_gws(player_data: Dict, n_gws: int, current_gw: int, fixtures_df: pd.DataFrame, teams_df: pd.DataFrame) -> float:
    # Use dictionary access instead of DataFrame lookup
    team_id = player_data['team']
    base_xp = player_data.get('base_xP', player_data.get('pred_points', 0) / max(0.5, player_data.get('avg_fixture_ease', 1)))
    play_prob = player_data.get('play_prob', 1.0)
    
    total_expected_points = 0.0
    team_def_strength = teams_df.set_index('id')['strength_defence_overall'].to_dict()
    avg_def_strength = np.mean(list(team_def_strength.values()))

    for gw in range(current_gw, current_gw + n_gws):
        gw_fixtures = fixtures_df[(fixtures_df['event'] == gw) & ((fixtures_df['team_h'] == team_id) | (fixtures_df['team_a'] == team_id))]
        if gw_fixtures.empty: continue
        for _, fixture in gw_fixtures.iterrows():
            is_home = fixture['team_h'] == team_id
            opponent_id = fixture['team_a'] if is_home else fixture['team_h']
            opp_strength = team_def_strength.get(opponent_id, avg_def_strength)
            fixture_multiplier = avg_def_strength / max(opp_strength, 1)
            home_boost = 1.1 if is_home else 0.9
            total_expected_points += base_xp * fixture_multiplier * home_boost * play_prob
    return total_expected_points

def calculate_transfer_roi(player_out_id: int, player_in_id: int, current_gw: int, elements_df: pd.DataFrame, fixtures_df: pd.DataFrame, teams_df: pd.DataFrame, hit_cost: int = 0, lookahead: int = 3) -> Dict:
    # Extract necessary data to pass to cached function (avoids hashing full DataFrame)
    cols = ['team', 'base_xP', 'pred_points', 'avg_fixture_ease', 'play_prob']
    
    p_out = elements_df.loc[player_out_id, cols].to_dict()
    p_in = elements_df.loc[player_in_id, cols].to_dict()
    
    out_xp_3gw = predict_next_n_gws(p_out, lookahead, current_gw, fixtures_df, teams_df)
    in_xp_3gw = predict_next_n_gws(p_in, lookahead, current_gw, fixtures_df, teams_df)
    
    gross_gain = in_xp_3gw - out_xp_3gw
    net_gain = gross_gain - hit_cost
    return {"out_xp_3gw": out_xp_3gw, "in_xp_3gw": in_xp_3gw, "gross_gain": gross_gain, "net_gain": net_gain, "is_worth_it": net_gain > 0.5}

def optimize_starting_xi(squad_players_df: pd.DataFrame) -> Tuple[List[int], List[int]]:
    ids = list(squad_players_df.index)
    positions = squad_players_df['element_type']
    prob = LpProblem("XI_Optimization", LpMaximize)
    x = {i: LpVariable(f"x_{i}", cat=LpBinary) for i in ids}
    
    objective_scores = squad_players_df['selection_score'] if 'selection_score' in squad_players_df.columns else squad_players_df['pred_points'] * squad_players_df['play_prob']
    prob += lpSum([objective_scores.get(i, 0) * x[i] for i in ids])

    prob += lpSum([x[i] for i in ids]) == 11
    prob += lpSum([x[i] for i in ids if positions.get(i) == 1]) == 1
    prob += lpSum([x[i] for i in ids if positions.get(i) == 2]) >= 3
    prob += lpSum([x[i] for i in ids if positions.get(i) == 2]) <= 5
    prob += lpSum([x[i] for i in ids if positions.get(i) == 3]) >= 2
    prob += lpSum([x[i] for i in ids if positions.get(i) == 3]) <= 5
    prob += lpSum([x[i] for i in ids if positions.get(i) == 4]) >= 1
    prob += lpSum([x[i] for i in ids if positions.get(i) == 4]) <= 3

    prob.solve(PULP_CBC_CMD(msg=0))
    if LpStatus[prob.status] == 'Optimal':
        start_ids = [i for i in ids if x[i].value() == 1]
        bench_ids = [i for i in ids if i not in start_ids]
        return start_ids, bench_ids
    return [], []

def calculate_3gw_roi(player, fixtures_df, teams_df, current_event):
    try:
        team_id = int(player['team'])
        next_3gw = list(range(current_event, current_event + 3))
        total_points = 0
        for gw in next_3gw:
            team_fixtures = fixtures_df[((fixtures_df['team_h'] == team_id) | (fixtures_df['team_a'] == team_id)) & (fixtures_df['event'] == gw)]
            if team_fixtures.empty: continue
            for _, fixture in team_fixtures.iterrows():
                is_home = fixture['team_h'] == team_id
                opp_team = fixture['team_a'] if is_home else fixture['team_h']
                opp_str = teams_df.loc[teams_df['id'] == opp_team, 'strength_overall_away' if is_home else 'strength_overall_home'].iloc[0]
                base_points = float(player.get('pred_points', 0)) / 2.0
                max_str = teams_df['strength_overall_home'].max()
                fixture_diff = 1.0 - (opp_str / max_str)
                total_points += base_points * (1.1 if is_home else 0.9) * (1.0 + fixture_diff)
        return total_points
    except Exception:
        return float(player.get('pred_points', 0))

def suggest_transfers(current_squad_ids: List[int], bank: float, free_transfers: int, all_players: pd.DataFrame, strategy: str, fixtures_df: pd.DataFrame, teams_df: pd.DataFrame, current_event: int, picks_data: List[Dict] = None) -> List[Dict]:
    valid_squad_ids = [pid for pid in current_squad_ids if pid in all_players.index]
    if not valid_squad_ids: return []
    current_squad_df = all_players.loc[valid_squad_ids]
    start_ids, _ = optimize_starting_xi(current_squad_df)
    if not start_ids: return []

    if strategy == "Free Transfer": max_transfers, hit_cost = free_transfers, float('inf')
    elif strategy == "Allow Hit (AI Suggest)": max_transfers, hit_cost = 5, 4
    else: max_transfers, hit_cost = 15, 0

    # Helper to get purchase price
    purchase_price_map = {}
    if picks_data:
        for p in picks_data:
            # Public API picks might not have purchase_price. Handle gracefully.
            if 'purchase_price' in p:
                purchase_price_map[p['element']] = p['purchase_price']

    current_team_count = {}
    for pid in valid_squad_ids:
        tid = int(all_players.loc[pid, 'team'])
        current_team_count[tid] = current_team_count.get(tid, 0) + 1

    position_groups = {1: [], 2: [], 3: [], 4: []}
    for pid in valid_squad_ids:
        position_groups.setdefault(int(all_players.loc[pid, 'element_type']), []).append(pid)

    remaining_bank, used_in_players, all_potential_moves = bank, set(), []
    
    # Iterate through ALL positions and ALL players to find the best moves
    for pos in [1, 2, 3, 4]:
        out_ids = position_groups.get(pos, [])
        if not out_ids: continue
        
        # --- IMPROVED: Prioritize selling unavailable players ---
        def get_sell_priority(pid):
            p = all_players.loc[pid]
            prob = p.get('play_prob', 1.0)
            # Sort by: Play Prob (asc), Pred Points (asc)
            # Lower prob = sell first. Lower points = sell first.
            return (prob, p['pred_points'])

        for out_id in sorted(out_ids, key=get_sell_priority):
            out_player = all_players.loc[out_id]
            
            # --- Price Lock Analysis ---
            price_loss = 0.0
            purchase_price = purchase_price_map.get(out_id)
            if purchase_price:
                # Fallback estimate if selling_price not directly available in picks_data map
                pick_obj = next((p for p in picks_data if p['element'] == out_id), None)
                if pick_obj and 'selling_price' in pick_obj:
                    selling_price = pick_obj['selling_price']
                else:
                    selling_price = out_player['now_cost']

                if purchase_price > selling_price:
                    price_loss = (purchase_price - selling_price) / 10.0

            sell_price = out_player['now_cost'] / 10.0 # Use current cost for bank calculation approximation
            
            # Calculate budget for this specific move (independent of other moves)
            available_budget = bank + sell_price
            
            # Find best replacement
            candidates = all_players[
                (all_players['element_type'] == pos) &
                (all_players.index != out_id) &
                (~all_players.index.isin(valid_squad_ids)) & # Exclude players already in squad
                ((all_players['now_cost'] / 10.0) <= available_budget) &
                (all_players['chance_of_playing_next_round'] > 75)
            ].copy()
            
            if candidates.empty: continue
            
            # Filter max 3 players per team
            def can_add(pid):
                tid = int(all_players.loc[pid, 'team'])
                return current_team_count.get(tid, 0) < 3
            
            candidates = candidates[candidates.index.map(can_add)]
            if candidates.empty: continue

            # Get top 3 candidates to consider, not just the absolute best points
            # This helps if the best points player has a bad ROI due to fixtures
            top_candidates = candidates.nlargest(3, 'pred_points')
            
            for _, best_in in top_candidates.iterrows():
                in_id = int(best_in.name)
                
                # ROI Calculation
                roi = calculate_transfer_roi(out_id, in_id, current_event, all_players, fixtures_df, teams_df)
                net_gain = roi['net_gain']
                
                # Apply Price Lock Penalty
                warning_msg = ""
                if price_loss > 0.3:
                    net_gain -= 0.5 # Penalty for breaking price lock
                    warning_msg = "⚠️ Selling at loss"
                
                if net_gain > (hit_cost if free_transfers == 0 else 0):
                    all_potential_moves.append({
                        "out_id": out_id,
                        "in_id": in_id,
                        "out_name": out_player['web_name'],
                        "out_cost": sell_price,
                        "in_name": best_in['web_name'],
                        "in_cost": best_in['now_cost'] / 10.0,
                        "delta_points": best_in['pred_points'] - out_player['pred_points'],
                        "roi_3gw": roi['gross_gain'],
                        "hit_cost": hit_cost if free_transfers == 0 else 0,
                        "net_gain": net_gain,
                        "price_loss": price_loss,
                        "warning": warning_msg
                    })

    # Sort all collected moves by Net Gain (Descending)
    all_potential_moves.sort(key=lambda x: x['net_gain'], reverse=True)
    
    # Select top N unique moves
    final_moves = []
    seen_out = set()
    seen_in = set()
    
    for move in all_potential_moves:
        if len(final_moves) >= max_transfers: break
        
        # Ensure we don't suggest selling the same player twice or buying the same player twice
        # (unless we support multiple transfers, but for now let's keep it simple: 1 suggestion per player involved)
        if move['out_name'] in seen_out or move['in_name'] in seen_in:
            continue
            
        final_moves.append(move)
        seen_out.add(move['out_name'])
        seen_in.add(move['in_name'])
            
    return final_moves

def plan_rolling_transfers(current_squad_ids: List[int], bank: float, free_transfers: int, all_players: pd.DataFrame, fixtures_df: pd.DataFrame, teams_df: pd.DataFrame, current_event: int, horizon: int = 3) -> List[Dict]:
    """
    Simulates a rolling transfer strategy for the next 'horizon' gameweeks.
    Decides whether to 'USE' or 'SAVE' FTs based on ROI.
    """
    plan = []
    sim_squad = set(current_squad_ids)
    sim_bank = bank
    sim_ft = free_transfers
    
    # Threshold to trigger a transfer (Net Gain > Threshold)
    # If FT=2, threshold is lower (use it or lose it). If FT=1, threshold is higher (save for mini-wildcard).
    ROI_THRESHOLD_SAVE = 2.0 # If FT=1, need > 2.0 gain to use
    ROI_THRESHOLD_USE = 0.5  # If FT>=2, need > 0.5 gain to use
    
    for step in range(horizon):
        gw = current_event + step
        
        # 1. Get Suggestions for this simulated state
        # We use 'Free Transfer' strategy to see best FT moves
        suggestions = suggest_transfers(list(sim_squad), sim_bank, sim_ft, all_players, "Free Transfer", fixtures_df, teams_df, gw)
        
        action = {"gw": gw, "action": "HOLD", "details": "Save Free Transfer", "roi": 0.0, "net_gain": 0.0}
        
        if suggestions:
            best_move = suggestions[0] # Best move by Net Gain
            threshold = ROI_THRESHOLD_USE if sim_ft >= 2 else ROI_THRESHOLD_SAVE
            
            if best_move['net_gain'] >= threshold:
                # Execute Transfer in Simulation
                action = {
                    "gw": gw,
                    "action": "TRANSFER",
                    "details": f"Sell {best_move['out_name']} -> Buy {best_move['in_name']}",
                    "roi": best_move['roi_3gw'],
                    "net_gain": best_move['net_gain'],
                    "in_id": best_move['in_id'],
                    "out_id": best_move['out_id'],
                    "in_cost": best_move['in_cost'],
                    "out_cost": best_move['out_cost']
                }

        plan.append(action)
        
        # Update State for next loop
        if action['action'] == "TRANSFER":
            if action['out_id'] in sim_squad:
                sim_squad.remove(action['out_id'])
            sim_squad.add(action['in_id'])
            sim_bank += (action['out_cost'] - action['in_cost'])
            sim_ft = max(1, sim_ft - 1) # Used 1 FT
        else:
            sim_ft = min(5, sim_ft + 1) # Saved FT, max 5
            
    return plan

def optimize_wildcard_team(all_players: pd.DataFrame, budget: float) -> Optional[List[int]]:
    ids = list(all_players.index)
    teams = all_players['team'].unique()
    prob = LpProblem("Wildcard_Optimization", LpMaximize)
    x = {i: LpVariable(f"x_{i}", cat=LpBinary) for i in ids}
    
    prob += lpSum([all_players.loc[i, 'pred_points'] * x[i] for i in ids])
    prob += lpSum([all_players.loc[i, 'now_cost'] * x[i] for i in ids]) <= budget * 10
    prob += lpSum([x[i] for i in ids]) == 15
    prob += lpSum([x[i] for i in ids if all_players.loc[i, 'element_type'] == 1]) == 2
    prob += lpSum([x[i] for i in ids if all_players.loc[i, 'element_type'] == 2]) == 5
    prob += lpSum([x[i] for i in ids if all_players.loc[i, 'element_type'] == 3]) == 5
    prob += lpSum([x[i] for i in ids if all_players.loc[i, 'element_type'] == 4]) == 3
    for team_id in teams: prob += lpSum([x[i] for i in ids if all_players.loc[i, 'team'] == team_id]) <= 3
    
    prob.solve(PULP_CBC_CMD(msg=0))
    if LpStatus[prob.status] == 'Optimal': return [i for i in ids if x[i].value() == 1]
    return None

def suggest_transfers_enhanced(current_squad_ids: List[int], bank: float, free_transfers: int, all_players: pd.DataFrame, strategy: str, fixtures_df: pd.DataFrame, teams_df: pd.DataFrame, current_event: int) -> Tuple[List[Dict], List[Dict]]:
    normal_moves = suggest_transfers(current_squad_ids, bank, free_transfers, all_players, strategy, fixtures_df, teams_df, current_event)
    
    conservative_all_players = all_players.copy()
    for player_id in current_squad_ids:
        if player_id not in all_players.index: continue
        current_price = all_players.loc[player_id, 'selling_price']
        conservative_price = max(current_price - 2, current_price * 0.95)
        conservative_all_players.loc[player_id, 'selling_price'] = conservative_price
    
    conservative_bank = bank
    for move in normal_moves:
        if move['out_id'] not in all_players.index: continue
        original_price = all_players.loc[move['out_id'], 'selling_price']
        conservative_price = conservative_all_players.loc[move['out_id'], 'selling_price']
        price_diff = (original_price - conservative_price) / 10.0
        conservative_bank = max(0, conservative_bank - price_diff)
    
    conservative_moves = suggest_transfers(current_squad_ids, conservative_bank, free_transfers, conservative_all_players, strategy, fixtures_df, teams_df, current_event)
    filtered_conservative_moves = []
    remaining_bank = conservative_bank
    used_players = set()
    
    for move in conservative_moves:
        if move['in_id'] not in used_players:
            cost_change = move['in_cost'] - move['out_cost']
            if cost_change <= remaining_bank:
                if move['out_id'] in conservative_all_players.index:
                    move['out_cost'] = round(conservative_all_players.loc[move['out_id'], 'selling_price'] / 10.0, 1)
                    filtered_conservative_moves.append(move)
                    remaining_bank -= cost_change
                    used_players.add(move['in_id'])
    return normal_moves, filtered_conservative_moves
def calculate_home_away_split(player_id: int) -> Dict[str, float]:
    """
    Fetches player history and calculates average points for Home vs Away games.
    """
    try:
        history_data = get_player_history(player_id)
        history = history_data.get("history", [])
        
        if not history:
            return {"home_avg": 0.0, "away_avg": 0.0, "home_games": 0, "away_games": 0}
            
        home_points = []
        away_points = []
        
        for match in history:
            points = match.get("total_points", 0)
            if match.get("was_home", False):
                home_points.append(points)
            else:
                away_points.append(points)
                
        home_avg = sum(home_points) / len(home_points) if home_points else 0.0
        away_avg = sum(away_points) / len(away_points) if away_points else 0.0
        
        return {
            "home_avg": round(home_avg, 2),
            "away_avg": round(away_avg, 2),
            "home_games": len(home_points),
            "away_games": len(away_points)
        }
    except Exception as e:
        print(f"Error calculating split for {player_id}: {e}")
        return {"home_avg": 0.0, "away_avg": 0.0, "home_games": 0, "away_games": 0}

def analyze_player_history(player_id: int) -> Dict[str, any]:
    """
    Analyzes a player's history to calculate weighted form and trend.
    Fetches element-summary from API (using cached helper).
    """
    try:
        data = get_player_history(player_id)
        if not data: return {'weighted_form': 0.0, 'form_trend': "➖", 'avg_minutes': 0.0, 'points_variance': 0.0}
        
        history = data.get('history', [])
        
        if not history: return {'weighted_form': 0.0, 'form_trend': "➖", 'avg_minutes': 0.0, 'points_variance': 0.0}
        
        # Sort by round (descending)
        history.sort(key=lambda x: x['round'], reverse=True)
        last_5 = history[:5]
        
        if not last_5: return {'weighted_form': 0.0, 'form_trend': "➖", 'avg_minutes': 0.0, 'points_variance': 0.0}
        
        # Weighted Form
        total_weight = 0
        weighted_sum = 0
        minutes_sum = 0
        points_list = []
        
        for i, match in enumerate(last_5):
            pts = match['total_points']
            mins = match['minutes']
            weight = 5 - i # 5, 4, 3, 2, 1
            
            weighted_sum += pts * weight
            total_weight += weight
            minutes_sum += mins
            points_list.append(pts)
            
        weighted_form = weighted_sum / total_weight
        avg_minutes = minutes_sum / len(last_5)
        
        # Form Trend
        trend = "➖"
        if len(last_5) >= 2:
            recent_avg = sum(m['total_points'] for m in last_5[:2]) / 2
            older_avg = sum(m['total_points'] for m in last_5[2:]) / max(1, len(last_5)-2)
            if recent_avg > older_avg + 1.5: trend = "🔥"
            elif recent_avg < older_avg - 1.5: trend = "📉"
            
        # Variance Calculation
        points_variance = np.var(points_list) if len(points_list) > 1 else 0.0
            
        return {
            'weighted_form': weighted_form,
            'form_trend': trend,
            'avg_minutes': avg_minutes,
            'points_variance': points_variance
        }
        
    except Exception:
        return {'weighted_form': 0.0, 'form_trend': "➖", 'avg_minutes': 0.0, 'points_variance': 0.0}

def suggest_chip_usage(current_gw: int, chips_history: List[Dict], fixtures_df: pd.DataFrame, teams_df: pd.DataFrame, squad_df: pd.DataFrame) -> List[Dict]:
    """
    Analyzes upcoming fixtures (DGW/BGW) and squad status to recommend chip usage.
    """
    recommendations = []
    
    # 1. Identify Used Chips
    used_chips = set()
    for chip in chips_history:
        used_chips.add(chip['name']) # '3xc', 'bboost', 'freehit', 'wildcard'
        
    # Map API names to readable names
    chip_map = {
        '3xc': 'Triple Captain',
        'bboost': 'Bench Boost',
        'freehit': 'Free Hit',
        'wildcard': 'Wildcard'
    }
    
    # 2. Analyze Upcoming Fixtures (Next 5 GWs)
    lookahead = 5
    future_gws = list(range(current_gw, current_gw + lookahead))
    
    dgw_gws = [] # Gameweeks with Double Games
    bgw_gws = [] # Gameweeks with Blanks
    
    for gw in future_gws:
        gw_fixtures = fixtures_df[fixtures_df['event'] == gw]
        team_counts = gw_fixtures['team_h'].value_counts().add(gw_fixtures['team_a'].value_counts(), fill_value=0)
        
        # DGW: Any team plays > 1 game
        if (team_counts > 1).any():
            dgw_teams = team_counts[team_counts > 1].index.tolist()
            dgw_gws.append({'gw': gw, 'teams': dgw_teams})
            
        # BGW: Count of teams playing < 1 game (Total teams = 20)
        teams_playing = len(team_counts)
        if teams_playing < 20:
            bgw_gws.append({'gw': gw, 'teams_playing': teams_playing})

    # 3. Generate Recommendations
    
    # --- Triple Captain (3xc) ---
    if '3xc' not in used_chips:
        found_tc_opp = False
        for dgw in dgw_gws:
            gw = dgw['gw']
            teams = dgw['teams']
            # Check if we own premium players from these teams
            premium_assets = squad_df[
                (squad_df['team'].isin(teams)) & 
                ((squad_df['now_cost'] > 100) | (squad_df['selected_by_percent'] > 30))
            ]
            
            if not premium_assets.empty:
                names = ", ".join(premium_assets['web_name'].tolist())
                recommendations.append({
                    'chip': 'Triple Captain',
                    'gw': gw,
                    'status': 'Recommended',
                    'reason': f"GW{gw} เป็น Double Gameweek และคุณมีตัวท็อปอย่าง {names} โปรแกรมน่าส่งเสริม เหมาะมากสำหรับกด TC"
                })
                found_tc_opp = True
                break # Recommend first good opportunity
        
        if not found_tc_opp:
             recommendations.append({
                'chip': 'Triple Captain',
                'gw': '-',
                'status': 'Hold',
                'reason': "แนะนำให้รอ Double Gameweek ที่มีตัวหลักของคุณแข่ง 2 นัดในสัปดาห์เดียวก่อน"
            })
    else:
        recommendations.append({'chip': 'Triple Captain', 'gw': '-', 'status': 'Used', 'reason': "คุณใช้ Triple Captain ไปแล้วในซีซั่นนี้"})

    # --- Bench Boost (bboost) ---
    if 'bboost' not in used_chips:
        found_bb_opp = False
        for dgw in dgw_gws:
            gw = dgw['gw']
            recommendations.append({
                'chip': 'Bench Boost',
                'gw': gw,
                'status': 'Consider',
                'reason': f"GW{gw} มี Double Gameweek หากตัวสำรองของคุณมีโปรแกรมลงครบ นี่คือจังหวะทองของ Bench Boost"
            })
            found_bb_opp = True
            break
            
        if not found_bb_opp:
             recommendations.append({
                'chip': 'Bench Boost',
                'gw': '-',
                'status': 'Hold',
                'reason': "ควรรอช่วงที่คุณสามารถส่งผู้เล่นลงครบทั้ง 15 คนได้พร้อมกัน"
            })
    else:
        recommendations.append({'chip': 'Bench Boost', 'gw': '-', 'status': 'Used', 'reason': "คุณใช้ Bench Boost ไปแล้วเรียบร้อย"})

    # --- Free Hit (freehit) ---
    if 'freehit' not in used_chips:
        found_fh_opp = False
        for bgw in bgw_gws:
            gw = bgw['gw']
            if bgw['teams_playing'] <= 14: # Less than 7 matches
                recommendations.append({
                    'chip': 'Free Hit',
                    'gw': gw,
                    'status': 'Recommended',
                    'reason': f"GW{gw} เป็น Blank Gameweek มีแข่งเพียง {bgw['teams_playing']} ทีม แนะนำให้ใช้ Free Hit เพื่อจัดทีมให้ครบ 11 คน"
                })
                found_fh_opp = True
                break
        
        if not found_fh_opp:
             recommendations.append({
                'chip': 'Free Hit',
                'gw': '-',
                'status': 'Hold',
                'reason': "เก็บไว้ใช้ในสัปดาห์ที่ทีมคุณตัวขาดเยอะ หรือมี Blank / Double หนัก ๆ"
            })
    else:
        recommendations.append({'chip': 'Free Hit', 'gw': '-', 'status': 'Used', 'reason': "คุณใช้ Free Hit ไปแล้วในซีซั่นนี้"})

    # --- Wildcard (wildcard) ---
    if 'wildcard' not in used_chips: 
        if dgw_gws:
            first_dgw = dgw_gws[0]['gw']
            recommendations.append({
                'chip': 'Wildcard',
                'gw': first_dgw - 1,
                'status': 'Consider',
                'reason': f"ควรพิจารณากดก่อน GW{first_dgw} เพื่อเตรียมทีมรับ Double Gameweek ที่กำลังจะมา"
            })
        else:
             recommendations.append({
                'chip': 'Wildcard',
                'gw': '-',
                'status': 'Hold',
                'reason': "เก็บไว้ใช้ช่วงที่ตารางแข่งทีมหลักเปลี่ยนหนัก หรือจำเป็นต้องยกเครื่องทีม"
            })
    else:
        recommendations.append({'chip': 'Wildcard', 'gw': '-', 'status': 'Used', 'reason': "คุณใช้ Wildcard ไปแล้วแล้ว" })

    return recommendations
