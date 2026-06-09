import json
import os
from datetime import datetime
from config import DATA_PATH

# Plant database and seasonal data are loaded once at module load.
# This mirrors how a real service would cache its data source in memory.
with open(os.path.join(DATA_PATH, "plants.json"), encoding="utf-8") as f:
    _plant_db = json.load(f)

with open(os.path.join(DATA_PATH, "seasons.json"), encoding="utf-8") as f:
    _season_data = json.load(f)

# Maps calendar months to seasons for auto-detection.
_MONTH_TO_SEASON = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "fall",  10: "fall",  11: "fall",
}


def lookup_plant(plant_name: str) -> dict:
    """
    Search the plant database for a plant by name and return its care information.
    
    Handles matching for:
      1. Direct key match
      2. Display name match
      3. Alias match
    """
    if not plant_name:
        return {
            "found": False,
            "name": plant_name,
            "message": "No plant name provided."
        }

    # Normalize the input: strip whitespace and convert to lowercase
    normalized = plant_name.strip().lower()

    # 1. Direct key match (Fastest, O(1) lookup)
    if normalized in _plant_db:
        return {"found": True, "plant": _plant_db[normalized]}

    # 2 & 3. Display name and Alias match (Linear search through keys)
    for key, plant_data in _plant_db.items():
        # Check display name match
        display_name = plant_data.get("display_name", "").lower()
        if display_name == normalized:
            return {"found": True, "plant": plant_data}
            
        # Check alias match
        aliases = [alias.lower() for alias in plant_data.get("aliases", [])]
        if normalized in aliases:
            return {"found": True, "plant": plant_data}

    # If the loop finishes without returning, the plant was not found.
    return {
        "found": False,
        "name": plant_name,
        "message": (
            f"The plant '{normalized}' was not found in the local database. "
            "The database currently only contains specialized care guides for 15 common houseplants. "
            "Inform the user that you don't have specific data for this plant, and ask if they "
            "would like to ask about a different plant or receive general plant care advice."
        )
    }


def get_seasonal_conditions(season: str | None = None) -> dict:
    """
    Return current seasonal care context for houseplants.

    If season is provided and valid, returns that season's data.
    If season is None (or invalid), auto-detects from the current calendar month.
    """
    VALID_SEASONS = {"spring", "summer", "fall", "winter"}

    if season and season.lower() in VALID_SEASONS:
        # Caller specified a valid season — use it directly
        season_key = season.lower()
        detected = False
    else:
        # Auto-detect from the current month using the _MONTH_TO_SEASON mapping
        current_month = datetime.now().month
        season_key = _MONTH_TO_SEASON[current_month]
        detected = True

    # Copy the season dict so we don't mutate the cached data
    result = dict(_season_data[season_key])
    result["detected_season"] = detected
    return result
