import json
from lotto_logic import run_lotto_analysis

# Run Lotto Logic
alerts = run_lotto_analysis()

# Convert to JSON structure for Firebase
output = {
    "alerts": [
        {"id": i, "message": msg}
        for i, msg in enumerate(alerts)
    ]
}

# Output to Firebase Hosting folder
with open("public/alerts.json", "w") as f:
    json.dump(output, f, indent=2)

print("alerts.json generated successfully")
