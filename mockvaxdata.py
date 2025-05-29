from pymongo import MongoClient
from datetime import datetime

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["PRS"]
collection = db["PatientsWithImmunizations"]

# Define PRS ID
prs_id = "PRS1001"

# Mock immunization record
new_vaccine = {
    "id": "mock-vax-001",
    "vaccine": "COVID-19 Vaccine Moderna",
    "date": datetime(2024, 10, 15).isoformat(),
    "lotNumber": "MODX2024",
    "manufacturer": "Moderna Inc."
}

# Update or insert
existing = collection.find_one({"PRS_ID": prs_id})

if existing:
    # Append to existing immunizations
    collection.update_one(
        {"PRS_ID": prs_id},
        {"$push": {"immunizations": new_vaccine}}
    )
    print("Immunization added to existing patient.")
else:
    # Create a new document
    new_doc = {
        "PRS_ID": prs_id,
        "patient": {
            "name": "Alice Johnson",
            "dob": "1985-06-15",
            "email": "alice.johnson@example.com"
        },
        "immunizations": [new_vaccine]
    }
    collection.insert_one(new_doc)
    print("New patient record created with vaccination.")
