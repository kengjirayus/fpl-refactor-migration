import json
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone
import dateutil.parser
from functools import lru_cache

# API Helpers
FPL_BASE = "https://fantasy.premierleague.com/api"

# Understat Helper Map
UNDERSTAT_TEAM_TO_FPL_NAME = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton": "Brighton",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Ipswich": "Ipswich",
    "Leicester": "Leicester",
    "Liverpool": "Liverpool",
    "Manchester City": "Man City",
    "Manchester United": "Man Utd",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nott'm Forest",
    "Southampton": "Southampton",
    "Tottenham": "Spurs",
    "West Ham": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
    # Add other teams as needed
    "Leeds": "Leeds",
    "Burnley": "Burnley",
    "Sheffield United": "Sheffield Utd",
    "Luton": "Luton"
}

# FotMob Team IDs (User to update/verify)
FPL_TO_FOTMOB_ID = {
    1: 9825,   # Arsenal
    2: 10252,  # Aston Villa
    3: 8678,   # Bournemouth
    4: 9937,   # Brentford
    5: 10204,  # Brighton
    6: 8455,   # Chelsea
    7: 9826,   # Crystal Palace
    8: 8668,   # Everton
    9: 9879,   # Fulham
    10: 9423,  # Ipswich
    11: 8197,  # Leicester
    12: 8650,  # Liverpool
    13: 8456,  # Man City
    14: 10260, # Man Utd
    15: 10261, # Newcastle
    16: 9823,  # Nott'm Forest
    17: 8466,  # Southampton
    18: 8586,  # Spurs
    19: 8654,  # West Ham
    20: 8602   # Wolves
}

def _fetch(url: str) -> Optional[Dict]:
    """Helper function to fetch JSON data with robust error handling."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://www.fotmob.com/',
        'Origin': 'https://www.fotmob.com'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # Suppress 401/403/404 errors from UI to avoid spamming
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code in [401, 403, 404]:
             print(f"API Error {e.response.status_code} for {url}") # Log to console instead
             return None
        
        print(f"Error fetching data from {url}: {e}") # Log to console
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON data from {url}: {e}")
        return None

# Simple lru_cache used instead of st.cache_data
# Note: lru_cache does not have TTL support natively. 
# For production, consider using cachetools.TTLCache or a database.

@lru_cache(maxsize=1)
def get_bootstrap() -> Dict:
    return _fetch(f"{FPL_BASE}/bootstrap-static/") or {}

@lru_cache(maxsize=1)
def get_fixtures() -> List[Dict]:
    return _fetch(f"{FPL_BASE}/fixtures/") or []

@lru_cache(maxsize=100)
def get_entry(entry_id: int) -> Dict:
    return _fetch(f"{FPL_BASE}/entry/{entry_id}/") or {}

@lru_cache(maxsize=100)
def get_entry_picks(entry_id: int, event: int) -> Dict:
    return _fetch(f"{FPL_BASE}/entry/{entry_id}/event/{event}/picks/") or {}

@lru_cache(maxsize=1000)
def get_player_history(player_id: int) -> Dict:
    return _fetch(f"{FPL_BASE}/element-summary/{player_id}/") or {}

@lru_cache(maxsize=100)
def get_entry_history(entry_id: int) -> Dict:
    return _fetch(f"{FPL_BASE}/entry/{entry_id}/history/") or {}

@lru_cache(maxsize=1)
def get_understat_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Fetches player and team data from Understat.com."""
    try:
        url = "https://understat.com/league/EPL"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        scripts = soup.find_all('script')
        
        players_data_str = None
        teams_data_str = None
        
        for script in scripts:
            if script.string and 'playersData' in script.string:
                players_data_str = script.string
            if script.string and 'teamsData' in script.string:
                teams_data_str = script.string

        # Process Players
        players_df = pd.DataFrame()
        if players_data_str:
            match = re.search(r"var playersData\s*=\s*JSON\.parse\('(.+?)'\);", players_data_str)
            if match:
                json_data = match.group(1).encode('utf-8').decode('unicode_escape')
                players_data = json.loads(json_data)
                players_df = pd.DataFrame(players_data)
                players_df['xG'] = pd.to_numeric(players_df['xG'], errors='coerce')
                players_df['xA'] = pd.to_numeric(players_df['xA'], errors='coerce')
                players_df = players_df[['id', 'player_name', 'team_title', 'xG', 'xA']]
            
        # Process Teams
        teams_df = pd.DataFrame()
        if teams_data_str:
            match = re.search(r"var teamsData\s*=\s*JSON\.parse\('(.+?)'\);", teams_data_str)
            if match:
                json_data = match.group(1).encode('utf-8').decode('unicode_escape')
                teams_data = json.loads(json_data)
                team_list = []
                for team_id_key, team_data in teams_data.items():
                    if team_data.get('history'):
                        latest_stats = team_data['history'][-1]
                        team_list.append({
                            'title': team_data.get('title'),
                            'xpts': latest_stats.get('xpts', 0)
                        })
                teams_df = pd.DataFrame(team_list)
                teams_df['xpts'] = pd.to_numeric(teams_df['xpts'], errors='coerce')

        return players_df, teams_df

    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

def check_name_match(fpl_name: str, understat_name: str) -> bool:
    if not fpl_name or not understat_name:
        return False
    fpl_name_lower = str(fpl_name).lower()
    understat_name_lower = str(understat_name).lower()
    if fpl_name_lower in understat_name_lower:
        return True
    try:
        fpl_last = fpl_name_lower.split(' ')[-1]
        understat_last = understat_name_lower.split(' ')[-1]
        if fpl_last == understat_last:
            return True
    except Exception:
        pass
    return False

@lru_cache(maxsize=1)
def merge_understat_data(us_players_df: pd.DataFrame, us_teams_df: pd.DataFrame, fpl_players_df: pd.DataFrame, fpl_teams_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    # Merge Teams
    merged_teams = pd.DataFrame()
    if not us_teams_df.empty and not fpl_teams_df.empty:
        try:
            us_teams_df['fpl_name'] = us_teams_df['title'].map(UNDERSTAT_TEAM_TO_FPL_NAME)
            merged_teams = us_teams_df.merge(
                fpl_teams_df[['name', 'logo_url']], 
                left_on='fpl_name', 
                right_on='name',
                how='left'
            )
            merged_teams = merged_teams[['title', 'name', 'xpts', 'logo_url']].sort_values('xpts', ascending=False)
        except Exception as e:
            print(f"Error merging Understat teams: {e}")

    # Merge Players
    merged_players = pd.DataFrame()
    if not us_players_df.empty and not fpl_players_df.empty and not fpl_teams_df.empty:
        try:
            fpl_name_to_id_map = fpl_teams_df.set_index('name')['id'].to_dict()
            us_players_df['fpl_name'] = us_players_df['team_title'].map(UNDERSTAT_TEAM_TO_FPL_NAME)
            us_players_df['fpl_team_id'] = us_players_df['fpl_name'].map(fpl_name_to_id_map)
            
            fpl_lookup = fpl_players_df[['team', 'web_name', 'photo_url', 'team_short', 'goals_scored', 'assists']].copy()
            combined_df = us_players_df.merge(fpl_lookup, left_on='fpl_team_id', right_on='team', how='inner')
            
            combined_df['name_match'] = combined_df.apply(
                lambda row: check_name_match(row['web_name'], row['player_name']), axis=1
            )
            final_players = combined_df[combined_df['name_match'] == True].copy()
            final_players = final_players.sort_values('xG', ascending=False)
            merged_players = final_players.drop_duplicates(subset=['id', 'player_name'])
            merged_players = merged_players[['player_name', 'team_short', 'photo_url', 'xG', 'xA', 'goals_scored', 'assists']]
        except Exception as e:
            print(f"Error merging Understat players: {e}")

    return merged_players, merged_teams

@lru_cache(maxsize=100)
def get_midweek_data(fpl_team_id: int) -> Dict:
    """
    Fetches the most recent match data for a team from FotMob to analyze rotation/fatigue.
    Returns:
        {
            'hours_gap': float, # Hours since last match
            'player_minutes': Dict[str, int] # Map of player name -> minutes played
        }
    """
    fotmob_id = FPL_TO_FOTMOB_ID.get(fpl_team_id)
    if not fotmob_id:
        return {}

    try:
        # 1. Fetch Team Fixtures
        url_fixtures = f"https://www.fotmob.com/api/teams?id={fotmob_id}&ccode3=ENG"
        data = _fetch(url_fixtures)
        if not data or 'fixtures' not in data:
            return {}

        # 2. Find last finished match
        # fixtures usually contains 'allFixtures' or similar, or just 'fixtures'
        # The structure can vary, let's look for 'fixtures' key which is usually a list
        fixtures = data.get('fixtures', [])
        
        last_match = None
        now = datetime.now(timezone.utc)
        
        # Sort by date descending to find the most recent finished one
        # FotMob dates are usually ISO strings
        finished_matches = []
        for fixture in fixtures:
            status = fixture.get('status', {})
            if status.get('finished') or status.get('type') == 'finished':
                match_time_str = fixture.get('status', {}).get('utcTime') or fixture.get('pageUrl', '').split('/')[-1] # Fallback
                # Better to use 'utcTime' if available, or 'startTime'
                # Let's try to parse the date from the fixture object directly if possible
                # Usually 'status': {'utcTime': ...} or top level 'utcTime'
                # Let's inspect a typical fixture object structure if we could, but we can't.
                # We'll assume standard fields.
                
                # Try to find a date field
                date_str = fixture.get('status', {}).get('utcTime')
                if not date_str:
                    continue
                    
                try:
                    match_date = dateutil.parser.parse(date_str)
                    if match_date < now:
                        finished_matches.append((match_date, fixture))
                except:
                    continue
        
        if not finished_matches:
            return {}
            
        # Get the most recent one
        finished_matches.sort(key=lambda x: x[0], reverse=True)
        last_match_date, last_match_data = finished_matches[0]
        match_id = last_match_data.get('id')
        
        if not match_id:
            return {}

        # 3. Calculate Gap
        hours_gap = (now - last_match_date).total_seconds() / 3600.0
        
        # 4. Fetch Match Details
        url_match = f"https://www.fotmob.com/api/matchDetails?matchId={match_id}"
        match_details = _fetch(url_match)
        if not match_details:
            return {'hours_gap': hours_gap, 'player_minutes': {}}
            
        # 5. Extract Minutes
        player_minutes = {}
        
        content = match_details.get('content', {})
        lineup = content.get('lineup', {}).get('lineup', [])
        
        # Lineup is usually a list of 2 teams
        for team_lineup in lineup:
            # Check if this is our team (optional, but good for safety)
            # But we can just parse all players since names should be unique enough or we filter later
            
            # Starters
            for player in team_lineup.get('players', []):
                name = player.get('name', {}).get('firstName', '') + " " + player.get('name', {}).get('lastName', '')
                name = name.strip()
                # Minutes usually in 'stats' or top level
                # If 'time' is present (minutes played)
                mins = 0
                # Check for 'time' field or 'stats'
                # FotMob often has 'time' as string "90" or "45+2"
                time_val = player.get('time')
                if time_val:
                    try:
                        mins = int(str(time_val).split('+')[0])
                    except:
                        mins = 0
                
                # Check substitution events if time is missing?
                # Usually 'time' is reliable for starters who finished or subbed out
                
                # If player was subbed ON, they are in 'bench' usually?
                # Actually FotMob puts subbed-in players in 'bench' list usually, with 'time' > 0
                
                if mins > 0:
                    player_minutes[name] = mins
                    
            # Bench
            for player in team_lineup.get('bench', []):
                name = player.get('name', {}).get('firstName', '') + " " + player.get('name', {}).get('lastName', '')
                name = name.strip()
                mins = 0
                time_val = player.get('time')
                if time_val:
                    try:
                        mins = int(str(time_val).split('+')[0])
                    except:
                        mins = 0
                
                if mins > 0:
                    player_minutes[name] = mins

        return {
            'hours_gap': hours_gap,
            'player_minutes': player_minutes
        }

    except Exception as e:
        # st.warning(f"Error fetching FotMob data: {e}")
        return {}