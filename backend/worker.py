import os
import sys
import time
from datetime import datetime
import json
import logging

# Ensure we can import from core
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.data_helpers import get_bootstrap, get_fixtures, get_understat_data
from core.firebase_config import get_firestore_client

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("FPLWorker")

def update_fpl_data():
    """
    Fetches latest data from FPL/Understat APIs and updates Firestore.
    """
    db = get_firestore_client()
    if not db:
        logger.error("Firebase not initialized. Cannot run worker.")
        return

    logger.info("Starting FPL Data Update...")

    # 1. Update Bootstrap Data
    try:
        logger.info("Fetching Bootstrap Static...")
        bootstrap = get_bootstrap()
        # Force clear cache to ensure fresh fetch next time/if script stays alive
        get_bootstrap.cache_clear()
        
        if bootstrap:
            # Firestore document size limit is 1MB. Bootstrap can be large.
            # We might need to split it or just save essential parts if it's too big.
            # For now, let's try saving the whole thing, but maybe remove 'elements' if it fails?
            # Actually elements is the most important part.
            # Let's try saving.
            db.collection('fpl_data').document('bootstrap').set(bootstrap)
            logger.info("Bootstrap data saved to Firestore.")
    except Exception as e:
        logger.error(f"Failed to update Bootstrap: {e}")

    # 2. Update Fixtures
    try:
        logger.info("Fetching Fixtures...")
        fixtures = get_fixtures()
        get_fixtures.cache_clear()
        
        if fixtures:
            # Wrap list in dict
            db.collection('fpl_data').document('fixtures').set({"all_fixtures": fixtures})
            logger.info("Fixtures data saved to Firestore.")
    except Exception as e:
        logger.error(f"Failed to update Fixtures: {e}")

    # 3. Update Understat Data (Optional, less frequent?)
    try:
        logger.info("Fetching Understat Data...")
        # This returns DataFrames
        us_players_df, us_teams_df = get_understat_data()
        get_understat_data.cache_clear()
        
        if not us_players_df.empty:
            # Convert to list of dicts
            players_data = us_players_df.to_dict(orient='records')
            # Chunking might be needed if too many players?
            # Firestore limit ~20k fields/1MB. 600 players * 5 fields is small.
            db.collection('fpl_data').document('understat_players').set({"data": players_data})
            logger.info(f"Understat players ({len(players_data)}) saved.")

        if not us_teams_df.empty:
            teams_data = us_teams_df.to_dict(orient='records')
            db.collection('fpl_data').document('understat_teams').set({"data": teams_data})
            logger.info(f"Understat teams ({len(teams_data)}) saved.")
            
    except Exception as e:
        logger.error(f"Failed to update Understat: {e}")

    logger.info("Update Complete.")

if __name__ == "__main__":
    # If passed --loop, run continuously
    if "--loop" in sys.argv:
        while True:
            update_fpl_data()
            logger.info("Sleeping for 1 hour...")
            time.sleep(3600)
    else:
        update_fpl_data()
