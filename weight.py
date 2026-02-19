from datetime import date, timedelta
from garminconnect import Garmin
from notion_client import Client
from dotenv import load_dotenv
import os

def get_weight_data(garmin):
    """
    Get yesterday's body composition (weight) data from Garmin Connect.
    Garmin's get_body_composition() returns data for a date range.
    """
    startdate = date.today() - timedelta(days=1)
    enddate = date.today() - timedelta(days=1)
    data = garmin.get_body_composition(startdate.isoformat(), enddate.isoformat())
    
    # The API returns a dict with a 'dateWeightList' key
    entries = data.get('dateWeightList', [])
    return entries

def weight_entry_exists(client, database_id, entry_date):
    """
    Check if a weight entry already exists in the Notion database for this date.
    """
    query = client.databases.query(
        database_id=database_id,
        filter={
            "property": "Date",
            "date": {"equals": entry_date}
        }
    )
    results = query['results']
    return results[0] if results else None

def weight_needs_update(existing_entry, new_data):
    """
    Compare existing entry with new data to determine if an update is needed.
    """
    existing_props = existing_entry['properties']
    new_weight_kg = new_data.get('weight')
    if new_weight_kg:
        new_weight_kg = round(new_weight_kg / 1000, 2)  # Garmin returns grams
    
    existing_weight = existing_props.get('Weight (kg)', {}).get('number')
    return existing_weight != new_weight_kg

def kg_to_lbs(kg):
    """Convert kilograms to pounds."""
    if kg is None:
        return None
    return round(kg * 2.20462, 1)

def create_weight_entry(client, database_id, entry):
    """
    Create a new weight entry in the Notion database.
    """
    # Garmin returns weight in grams — convert to kg and lbs
    weight_g = entry.get('weight')
    weight_kg = round(weight_g / 1000, 2) if weight_g else None
    weight_lbs = kg_to_lbs(weight_kg)
    
    bmi = entry.get('bmi')
    body_fat = entry.get('bodyFat')
    entry_date = entry.get('calendarDate')

    properties = {
        "Date": {"title": [{"text": {"content": entry_date or "Unknown"}}]},
        "Weight (kg)": {"number": weight_kg},
        "Weight (lbs)": {"number": weight_lbs},
    }

    if bmi is not None:
        properties["BMI"] = {"number": round(bmi, 1)}
    
    if body_fat is not None:
        properties["Body Fat (%)"] = {"number": round(body_fat, 1)}

    page = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }

    client.pages.create(**page)
    print(f"Created weight entry for {entry_date}: {weight_lbs} lbs ({weight_kg} kg)")

def update_weight_entry(client, existing_entry, entry):
    """
    Update an existing weight entry in the Notion database.
    """
    weight_g = entry.get('weight')
    weight_kg = round(weight_g / 1000, 2) if weight_g else None
    weight_lbs = kg_to_lbs(weight_kg)

    bmi = entry.get('bmi')
    body_fat = entry.get('bodyFat')

    properties = {
        "Weight (kg)": {"number": weight_kg},
        "Weight (lbs)": {"number": weight_lbs},
    }

    if bmi is not None:
        properties["BMI"] = {"number": round(bmi, 1)}
    
    if body_fat is not None:
        properties["Body Fat (%)"] = {"number": round(body_fat, 1)}

    client.pages.update(
        page_id=existing_entry['id'],
        properties=properties
    )
    print(f"Updated weight entry: {weight_lbs} lbs ({weight_kg} kg)")

def main():
    load_dotenv()

    garmin_email = os.getenv("GARMIN_EMAIL")
    garmin_password = os.getenv("GARMIN_PASSWORD")
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_WEIGHT_DB_ID")

    if not database_id:
        print("NOTION_WEIGHT_DB_ID not set — skipping weight sync.")
        return

    garmin = Garmin(garmin_email, garmin_password)
    garmin.login()
    client = Client(auth=notion_token)

    weight_entries = get_weight_data(garmin)

    if not weight_entries:
        print("No weight data returned from Garmin for yesterday. Make sure you log weight in Garmin Connect.")
        return

    for entry in weight_entries:
        entry_date = entry.get('calendarDate')
        if not entry_date:
            continue

        existing = weight_entry_exists(client, database_id, entry_date)
        if existing:
            if weight_needs_update(existing, entry):
                update_weight_entry(client, existing, entry)
            else:
                print(f"Weight entry for {entry_date} already up to date.")
        else:
            create_weight_entry(client, database_id, entry)

if __name__ == '__main__':
    main()
