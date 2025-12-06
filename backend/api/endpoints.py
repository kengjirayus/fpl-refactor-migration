from fastapi import APIRouter, HTTPException, Query 
from typing import Optional, List
import pandas as pd
from datetime import datetime, timezone
from pydantic import BaseModel

from core.data_helpers import (
    get_bootstrap, get_fixtures, get_understat_data, merge_understat_data, 
    get_entry, get_entry_picks
)
try:
    from core.firebase_config import get_firestore_client
except ImportError:
    get_firestore_client = lambda: None

from core.fpl_logic import (
    build_master_tables, current_and_next_event, next_fixture_features, 
    engineer_features_enhanced, get_fixture_difficulty_matrix, 
    detect_fixture_swing, find_rotation_pairs, optimize_starting_xi,
    select_captain_vice, smart_bench_order, suggest_transfers_enhanced
)

router = APIRouter()

class AnalysisRequest(BaseModel):
    team_id: int
    free_transfers: int = 1
    bank: float = 0.0

class SimulationRequest(BaseModel):
    team_ids: List[int]
    bank: float = 0.0

def get_cached_features(gameweek: int = 1):
    # 1. Load Data
    bootstrap = get_bootstrap()
    fixtures = get_fixtures()
    if not bootstrap or "elements" not in bootstrap:
        return None, None, None

    # 2. Process Basic Tables
    elements, teams, events, fixtures_df = build_master_tables(bootstrap, fixtures)
    cur_event, next_event = current_and_next_event(bootstrap.get("events", []))
    target_event = next_event or (cur_event + 1 if cur_event else 1)
    
    # 3. Feature Engineering
    nf = next_fixture_features(fixtures_df, teams, target_event)
    us_players, us_teams = get_understat_data()
    
    # We pass None for my_team_ids here as a general cache, 
    # but strictly speaking engineer_features_enhanced filters top players 
    # unless my_team_ids is provided. 
    # For simulation (arbitrary players), this might miss some low-ownership players.
    # PROPOSAL: We might need to fetch specific players on demand if missing?
    # For now, let's fetch 'rich' features.
    feat = engineer_features_enhanced(elements, teams, nf, us_players, gameweek=gameweek)
    feat.set_index('id', inplace=True)
    
    return feat, fixtures_df, teams

@router.get("/bootstrap")
def get_bootstrap_data():
    return get_bootstrap()

@router.get("/fixtures")
def get_fixtures_data():
    return get_fixtures()

@router.get("/analyze/{team_id}")
def analyze_team(team_id: int):
    bootstrap = get_bootstrap()
    fixtures = get_fixtures()
    
    if not bootstrap or "elements" not in bootstrap:
        raise HTTPException(status_code=503, detail="FPL API access failed")

    elements, teams, events, fixtures_df = build_master_tables(bootstrap, fixtures)
    cur_event, next_event = current_and_next_event(bootstrap.get("events", []))
    target_event = next_event or (cur_event + 1 if cur_event else 1)

    entry = get_entry(team_id)
    if not entry or 'id' not in entry:
        raise HTTPException(status_code=404, detail="Team not found")

    picks = get_entry_picks(team_id, cur_event or 1)
    picks_data = picks.get("picks", [])
    my_team_ids = [p['element'] for p in picks_data] if picks_data else []

    nf = next_fixture_features(fixtures_df, teams, target_event)
    us_players, us_teams = get_understat_data()
    
    # Pass my_team_ids to ensure they are analyzed
    feat = engineer_features_enhanced(elements, teams, nf, us_players, my_team_ids=my_team_ids, gameweek=cur_event or 1)
    feat.set_index('id', inplace=True, drop=False) # Keep ID as column too
    
    # Select cols
    cols = ['id', 'web_name', 'team', 'team_short', 'element_type', 'now_cost', 
            'pred_points', 'xG', 'xA', 'form', 'ict_index', 'selected_by_percent',
            'chance_of_playing_next_round', 'news', 'points_per_game', 'total_points',
            'xMins', 'set_piece_roles', 'is_aerial_threat', 'risk_level']
            
    # Ensure all NaN are replaced
    json_data = feat[cols].fillna(0).to_dict(orient="records")
    
    return {
        "team_info": entry,
        "gameweek": {
            "current": cur_event,
            "next": target_event
        },
        "players": json_data,
        "picks": picks_data
    }

@router.get("/general-data")
def get_general_data():
    bootstrap = get_bootstrap()
    fixtures = get_fixtures()
    
    if not bootstrap or "elements" not in bootstrap:
        raise HTTPException(status_code=503, detail="FPL API access failed")

    # 1. Basic Data
    elements, teams, events, fixtures_df = build_master_tables(bootstrap, fixtures)
    cur_event, next_event = current_and_next_event(bootstrap.get("events", []))
    target_event = next_event or (cur_event + 1 if cur_event else 1)

    # 2. Feature Engineering (Generic)
    nf = next_fixture_features(fixtures_df, teams, target_event)
    us_players, us_teams = get_understat_data()
    
    # We pass None for my_team_ids to get generic data (top players)
    feat = engineer_features_enhanced(elements, teams, nf, us_players, gameweek=cur_event or 1)
    feat.set_index('id', inplace=True, drop=False)
    
    # 3. Specific Sections
    
    # Fixture Difficulty & Swing
    opp_matrix, diff_matrix = get_fixture_difficulty_matrix(fixtures_df, teams, target_event)
    swing_data = detect_fixture_swing(fixtures_df, teams, target_event)
    
    # Map Next Opponent to Players
    # opp_matrix index is team short name, columns are GWx
    gw_col = f"GW{target_event}"
    if gw_col in opp_matrix.columns:
        feat['next_opponent'] = feat['team_short'].map(opp_matrix[gw_col])
    else:
        feat['next_opponent'] = "-"
    
    # Undervalued/Overvalued (Risers/Fallers)
    risers = feat[feat['cost_change_start'] > 0].sort_values('cost_change_start', ascending=False).head(5).fillna(0).to_dict(orient="records")
    fallers = feat[feat['cost_change_start'] < 0].sort_values('cost_change_start', ascending=True).head(5).fillna(0).to_dict(orient="records")
    
    # Top Captains
    captains = feat.nlargest(5, 'pred_points').fillna(0).to_dict(orient="records")

    # Trend Cards Logic
    # 1. Top Form (Highest form)
    top_form = feat.nlargest(5, 'form').fillna(0).to_dict(orient="records")

    # 2. Top Differentials (Selected < 10%, sorted by pred_points)
    differentials = feat[feat['selected_by_percent'] < 10.0].nlargest(5, 'pred_points').fillna(0).to_dict(orient="records")

    # 3. Top Most Selected (Highest selected_by_percent)
    top_selected = feat.nlargest(5, 'selected_by_percent').fillna(0).to_dict(orient="records")
    
    # Understat Leaders
    # We need to merge them to get proper display data if possible, or just send raw
    # merge_understat_data logic:
    merged_us_players, merged_us_teams = merge_understat_data(
            us_players, 
            us_teams, 
            feat[['team', 'web_name', 'photo_url', 'team_short', 'goals_scored', 'assists']], 
            teams[['id', 'name', 'logo_url']]
    )
    
    # Convert DataFrames to JSON-compatible format
    # Helper to clean NaNs
    def clean_df(df):
        return df.fillna(0).to_dict(orient="records")

    # Find deadline for next/target event
    target_event_data = next((e for e in bootstrap.get("events", []) if e['id'] == target_event), None)
    deadline_time = target_event_data['deadline_time'] if target_event_data else None

    return {
        "gameweek": {
            "current": cur_event,
            "next": target_event,
            "deadline_time": deadline_time
        },
        "top_players": clean_df(feat.nlargest(50, 'pred_points')),
        "captains": captains,
        "risers": risers,
        "fallers": fallers,
        "fixture_swing": swing_data,
        "fixture_difficulty": clean_df(diff_matrix.reset_index().rename(columns={"index": "team_short"})),
        "opponent_matrix": clean_df(opp_matrix.reset_index().rename(columns={"index": "team_short"})),
        "understat_players": clean_df(merged_us_players) if not merged_us_players.empty else [],
        "understat_teams": clean_df(merged_us_teams) if not merged_us_teams.empty else [],
        "top_form": top_form,
        "differentials": differentials,
        "top_selected": top_selected,
        "teams": clean_df(teams)
    }

@router.post("/simulate")
def simulate_team(request: SimulationRequest):
    # 1. Get Features (Re-using logic, ideally cached)
    bootstrap = get_bootstrap()
    if not bootstrap or "events" not in bootstrap:
        raise HTTPException(status_code=503, detail="FPL API Unavailable")
        
    cur_event, _ = current_and_next_event(bootstrap.get("events", []))
    
    # Fetch features including these specific players
    # Note: This is a bit inefficient to re-engineer every time, but required 
    # if the simulation uses players not in the top 250 owned.
    feat, fixtures_df, teams = get_cached_features_with_ids(request.team_ids, cur_event or 1)
    
    # 2. Filter to requested IDs
    # Existing IDs in feat
    valid_ids = [pid for pid in request.team_ids if pid in feat.index]
    if len(valid_ids) < 11:
         raise HTTPException(status_code=400, detail="Not enough valid players found in dataset")

    squad_df = feat.loc[valid_ids].copy()
    
    # 3. Optimize XI
    xi_ids, bench_ids = optimize_starting_xi(squad_df)
    
    # 4. Process Result
    xi_df = squad_df.loc[xi_ids].copy()
    bench_df = squad_df.loc[bench_ids].copy()
    
    cap_data = select_captain_vice(xi_df)
    ordered_bench = smart_bench_order(bench_df)
    
    # Format Response
    def to_record(row):
        r = row.to_dict()
        # Handle numpy types
        for k, v in r.items():
            if pd.isna(v): r[k] = None
        return r

    return {
        "starting_xi": [to_record(row) for _, row in xi_df.iterrows()],
        "bench": [to_record(row) for _, row in ordered_bench.iterrows()],
        "captain": cap_data['safe_pick'],
        "vice_captain": cap_data['vice_picks'][0] if cap_data['vice_picks'] else None,
        "stats": {
            "total_cost": squad_df['now_cost'].sum() / 10.0,
            "total_pred_points": squad_df['pred_points'].sum()
        }
    }

def get_cached_features_with_ids(my_ids: List[int], gameweek: int):
    # Helper to avoid code duplication, though caching this function might be tricky 
    # if my_ids changes layout.
    bootstrap = get_bootstrap()
    fixtures = get_fixtures()
    elements, teams, events, fixtures_df = build_master_tables(bootstrap, fixtures)
    _, next_event = current_and_next_event(bootstrap.get("events", []))
    target_event = next_event or (gameweek + 1)
    
    nf = next_fixture_features(fixtures_df, teams, target_event)
    us_players, _ = get_understat_data()
    
    feat = engineer_features_enhanced(elements, teams, nf, us_players, my_team_ids=my_ids, gameweek=gameweek)
    feat.set_index('id', inplace=True)
    feat.set_index('id', inplace=True)
    return feat, fixtures_df, teams

class TransferRequest(BaseModel):
    team_ids: List[int]
    bank: float
    free_transfers: int = 1
    strategy: str = "aggressive"

@router.post("/transfers/suggest")
def get_transfer_suggestions(request: TransferRequest):
    # 1. Get Data
    bootstrap = get_bootstrap()
    if not bootstrap or "events" not in bootstrap:
        raise HTTPException(status_code=503, detail="FPL API Unavailable")
    
    cur_event, _ = current_and_next_event(bootstrap.get("events", []))
    # We need a rich dataset of ALL players to find transfer targets
    # Passing [] to my_team_ids implies we want general population stats
    # ideally we should use a comprehensive list or Top N players.
    # For now, let's assume 'engineer_features_enhanced' handles 'None' appropriately
    # or serves top players.
    # Looking at fpl_logic.py, if my_team_ids is passed, it ensures they are in.
    # To get POTENTIAL targets, we need the "market".
    # Let's pass the user's team IDs to ensure they are calculated, 
    # and rely on the function to include top ownership players too.
    
    feat, fixtures_df, teams_df = get_cached_features_with_ids(request.team_ids, cur_event or 1)
    
    # 2. Call Logic
    # We might need to handle 'Strategy' mapping if it's strict
    try:
        suggestions, conservative = suggest_transfers_enhanced(
            current_squad_ids=request.team_ids,
            bank=request.bank,
            free_transfers=request.free_transfers,
            all_players=feat,
            strategy=request.strategy,
            fixtures_df=fixtures_df,
            teams_df=teams_df,
            current_event=cur_event or 1
        )
    except Exception as e:
        print(f"Error generating transfers: {e}")
        # Return empty rules to avoid crash
        suggestions = []
        conservative = []

    return {
        "aggressive": suggestions,
        "conservative": conservative
    }

class UserSettings(BaseModel):
    team_id: int
    theme: Optional[str] = "dark"
    email: Optional[str] = None

@router.post("/settings")
def save_user_settings(settings: UserSettings):
    db = get_firestore_client()
    if not db:
        return {"status": "skipped", "reason": "Firebase not configured"}
    
    try:
        # Use team_id as document ID
        doc_ref = db.collection("users").document(str(settings.team_id))
        doc_ref.set({
            "team_id": settings.team_id,
            "theme": settings.theme,
            "email": settings.email,
            "updated_at": firestore.SERVER_TIMESTAMP if 'firestore' in globals() else datetime.now(timezone.utc)
        }, merge=True)
        return {"status": "success", "message": "Settings saved"}
    except Exception as e:
        print(f"Error saving settings: {e}")
        # Don't block the UI if firebase fails
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings/{team_id}")
def get_user_settings(team_id: int):
    db = get_firestore_client()
    if not db:
        return {}
    
    try:
        doc_ref = db.collection("users").document(str(team_id))
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            return {}
    except Exception as e:
        print(f"Error fetching settings: {e}")
        return {}
