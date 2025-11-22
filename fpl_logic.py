import numpy as np
import pandas as pd
import streamlit as st
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, LpBinary, LpStatus, PULP_CBC_CMD
from typing import List, Dict, Tuple, Optional

POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
TEAM_MAP_COLS = ["id", "code", "name", "short_name", "strength_overall_home", "strength_overall_away",
                 "strength_attack_home", "strength_attack_away", "strength_defence_home", "strength_defence_away","position"]

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
            rows.append({'team': team_id, 'num_fixtures': 0, 'total_opp_def_str': 0, 'avg_fixture_ease': 0, 'opponent_str': "BLANK"})
            continue

        opponent_str = ", ".join(opp_list)
        total_opp_def_str = 0
        for opp_id in home_opps:
            total_opp_def_str += teams_idx.loc[opp_id, 'strength_defence_away']
        for opp_id in away_opps:
            total_opp_def_str += teams_idx.loc[opp_id, 'strength_defence_home']

        rows.append({
            'team': team_id,
            'num_fixtures': num_fixtures,
            'total_opp_def_str': total_opp_def_str,
            'avg_fixture_ease': 1.0 - (total_opp_def_str / (num_fixtures * teams_idx['strength_defence_home'].max())),
            'opponent_str': opponent_str
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

def engineer_features_enhanced(elements: pd.DataFrame, teams: pd.DataFrame, nf: pd.DataFrame, understat_players: pd.DataFrame) -> pd.DataFrame:
    elements = elements.copy()
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
        elements['web_name_lower'] = elements['web_name'].str.lower()
        understat_players['player_name_lower'] = understat_players['player_name'].str.lower()
        us_dedup = understat_players[['player_name_lower', 'xG', 'xA']].drop_duplicates('player_name_lower')
        elements = elements.merge(us_dedup, left_on='web_name_lower', right_on='player_name_lower', how='left')
        elements['xG'] = elements['xG'].fillna(0)
        elements['xA'] = elements['xA'].fillna(0)
        elements.drop(columns=['web_name_lower', 'player_name_lower'], inplace=True, errors='ignore')
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

    elements["pred_points_enhanced"] = (
        elements['base_xP'] * (0.5 + 0.5 * elements["avg_fixture_ease"]) * (0.4 + 0.6 * elements["play_prob"]) * pos_mult * elements['num_fixtures']
    )
    elements["pred_points_enhanced"] = elements["pred_points_enhanced"].clip(lower=0, upper=25)
    elements.loc[elements['num_fixtures'] == 0, 'pred_points_enhanced'] = 0
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

def select_captain_vice(xi_df: pd.DataFrame) -> Tuple[int, int]:
    xi_candidates = xi_df.copy()
    xi_candidates['captain_score'] = (
        xi_candidates.get('selection_score', xi_candidates['pred_points']) * 0.5 +
        xi_candidates.get('form', 0) * 0.2 +
        xi_candidates.get('avg_fixture_ease', 0) * 10 * 0.2 +
        (xi_candidates.get('xG', 0) + xi_candidates.get('xA', 0)) * 0.1
    )
    xi_candidates.loc[xi_candidates['num_fixtures'] == 2, 'captain_score'] *= 1.5
    sorted_candidates = xi_candidates.sort_values('captain_score', ascending=False)
    return sorted_candidates.iloc[0].name, sorted_candidates.iloc[1].name

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
def predict_next_n_gws(player_id: int, n_gws: int, current_gw: int, elements_df: pd.DataFrame, fixtures_df: pd.DataFrame, teams_df: pd.DataFrame) -> float:
    if player_id not in elements_df.index: return 0.0
    player = elements_df.loc[player_id]
    team_id = player['team']
    base_xp = player.get('base_xP', player.get('pred_points', 0) / max(0.5, player.get('avg_fixture_ease', 1)))
    play_prob = player.get('play_prob', 1.0)
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
            home_boost = 1.1 if is_home else 0.95
            total_expected_points += base_xp * fixture_multiplier * home_boost * play_prob
    return total_expected_points

def calculate_transfer_roi(player_out_id: int, player_in_id: int, current_gw: int, elements_df: pd.DataFrame, fixtures_df: pd.DataFrame, teams_df: pd.DataFrame, hit_cost: int = 0, lookahead: int = 3) -> Dict:
    out_xp_3gw = predict_next_n_gws(player_out_id, lookahead, current_gw, elements_df, fixtures_df, teams_df)
    in_xp_3gw = predict_next_n_gws(player_in_id, lookahead, current_gw, elements_df, fixtures_df, teams_df)
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

def suggest_transfers(current_squad_ids: List[int], bank: float, free_transfers: int, all_players: pd.DataFrame, strategy: str, fixtures_df: pd.DataFrame, teams_df: pd.DataFrame, current_event: int) -> List[Dict]:
    valid_squad_ids = [pid for pid in current_squad_ids if pid in all_players.index]
    if not valid_squad_ids: return []
    current_squad_df = all_players.loc[valid_squad_ids]
    start_ids, _ = optimize_starting_xi(current_squad_df)
    if not start_ids: return []

    if strategy == "Free Transfer": max_transfers, hit_cost = free_transfers, float('inf')
    elif strategy == "Allow Hit (AI Suggest)": max_transfers, hit_cost = 5, 4
    else: max_transfers, hit_cost = 15, 0

    current_team_count = {}
    for pid in valid_squad_ids:
        tid = int(all_players.loc[pid, 'team'])
        current_team_count[tid] = current_team_count.get(tid, 0) + 1

    position_groups = {1: [], 2: [], 3: [], 4: []}
    for pid in valid_squad_ids:
        position_groups.setdefault(int(all_players.loc[pid, 'element_type']), []).append(pid)

    remaining_bank, used_in_players, potential_moves = bank, set(), []
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
            out_team_id = int(out_player['team'])
            budget = out_player['selling_price'] + (remaining_bank * 10)
            all_replacements = all_players[(all_players['element_type'] == out_player['element_type']) & (~all_players.index.isin(valid_squad_ids)) & (all_players['now_cost'] <= budget) & (all_players['pred_points'] > out_player['pred_points'])].sort_values('pred_points', ascending=False)
            if all_replacements.empty: continue

            best_replacement, best_replacement_id = None, None
            for cid, candidate in all_replacements.iterrows():
                candidate_team_id = int(candidate['team'])
                ftc = current_team_count.copy()
                ftc[out_team_id] = ftc.get(out_team_id, 0) - 1
                if ftc[out_team_id] <= 0: ftc.pop(out_team_id, None)
                if ftc.get(candidate_team_id, 0) + 1 > 3: continue
                if int(cid) in used_in_players: continue
                best_replacement, best_replacement_id = candidate, int(cid)
                break

            if best_replacement is None: continue
            cost_change = (best_replacement['now_cost'] - out_player['selling_price']) / 10.0
            if cost_change > remaining_bank: continue
            
            if out_team_id != int(best_replacement['team']):
                current_team_count[out_team_id] = current_team_count.get(out_team_id, 0) - 1
                if current_team_count[out_team_id] <= 0: current_team_count.pop(out_team_id, None)
                current_team_count[int(best_replacement['team'])] = current_team_count.get(int(best_replacement['team']), 0) + 1
            
            remaining_bank = round(max(0.0, remaining_bank - cost_change), 2)
            used_in_players.add(best_replacement_id)
            roi_in = calculate_3gw_roi(best_replacement, fixtures_df, teams_df, current_event)
            roi_out = calculate_3gw_roi(out_player, fixtures_df, teams_df, current_event)
            
            potential_moves.append({
                "out_id": int(out_id), "in_id": best_replacement_id,
                "out_name": out_player.get("web_name", ""), "in_name": best_replacement.get("web_name", ""),
                "out_pos": POSITIONS.get(int(out_player["element_type"]), str(out_player["element_type"])),
                "in_pos": POSITIONS.get(int(best_replacement["element_type"]), str(best_replacement["element_type"])),
                "out_team": out_player.get("team_short", ""), "in_team": best_replacement.get("team_short", ""),
                "in_points": float(best_replacement.get("pred_points", 0.0)),
                "delta_points": float(best_replacement.get('pred_points', 0.0) - out_player.get('pred_points', 0.0) + (2.0 if out_player.get('play_prob', 1.0) == 0 else (1.0 if out_player.get('play_prob', 1.0) < 0.5 else 0.0))), # Bonus for selling dead players
                "roi_3gw": float(roi_in - roi_out),
                "in_cost": float(best_replacement.get('now_cost', 0.0)) / 10.0, "out_cost": float(out_player.get('selling_price', 0.0)) / 10.0,
            })

    potential_moves.sort(key=lambda x: x.get("delta_points", 0.0), reverse=True)
    final_suggestions = []
    GREEDY_THRESHOLD, CONSERVATIVE_THRESHOLD = -2.0, -0.1
    for i, move in enumerate(potential_moves):
        if len(final_suggestions) >= max_transfers: break
        hit = 0 if len(final_suggestions) < free_transfers else hit_cost
        net_gain = move["delta_points"] - hit
        m = move.copy(); m['net_gain'] = round(net_gain, 2); m['hit_cost'] = hit
        if strategy == "Free Transfer" and net_gain >= CONSERVATIVE_THRESHOLD: final_suggestions.append(m)
        elif strategy == "Allow Hit (AI Suggest)" and net_gain >= GREEDY_THRESHOLD: final_suggestions.append(m)
        elif strategy == "Wildcard / Free Hit" and net_gain > 0.0: final_suggestions.append(m)
    return final_suggestions

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