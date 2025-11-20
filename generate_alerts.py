
# Entrypoint for GitHub Actions: run lotto analysis and write alerts
import sys
import os
from lotto_logic import run_lotto_analysis

def main():
    alerts = run_lotto_analysis()
    os.makedirs("public", exist_ok=True)
    with open("public/alerts.json", "w") as f:
        for line in alerts:
            f.write(line + "\n")
    print(f"Wrote {len(alerts)} alerts to public/alerts.json")

if __name__ == "__main__":
    main()
