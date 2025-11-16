import json
import re
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional

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

def _fetch(url: str) -> Optional[Dict]:
    """Helper function to fetch JSON data with robust error handling."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from FPL API: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"Error decoding JSON data from FPL API: {e}")
        return None

@st.cache_data(ttl=300)
def get_bootstrap() -> Dict:
    return _fetch(f"{FPL_BASE}/bootstrap-static/") or {}

@st.cache_data(ttl=300)
def get_fixtures() -> List[Dict]:
    return _fetch(f"{FPL_BASE}/fixtures/") or []

@st.cache_data(ttl=300)
def get_entry(entry_id: int) -> Dict:
    return _fetch(f"{FPL_BASE}/entry/{entry_id}/") or {}

@st.cache_data(ttl=300)
def get_entry_picks(entry_id: int, event: int) -> Dict:
    return _fetch(f"{FPL_BASE}/entry/{entry_id}/event/{event}/picks/") or {}

@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
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
            st.warning(f"Error merging Understat teams: {e}")

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
            st.warning(f"Error merging Understat players: {e}")

    return merged_players, merged_teams