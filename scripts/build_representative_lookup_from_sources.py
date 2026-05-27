#!/usr/bin/env python3
import csv
import datetime as dt
import io
import urllib.request
from pathlib import Path

import yaml


ZIP_DISTRICT_URL = "https://raw.githubusercontent.com/OpenSourceActivismTech/us-zipcodes-congress/master/zccd.csv"
LEGISLATORS_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml"
OUTPUT = Path("representative_lookup_from_us_zipcodes_congress.csv")

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def fetch_text(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def active_house_members(active_on):
    people = yaml.safe_load(fetch_text(LEGISLATORS_URL))
    members = {}
    for person in people:
        for term in person.get("terms", []):
            if term.get("type") != "rep":
                continue
            start = dt.date.fromisoformat(term["start"])
            end = dt.date.fromisoformat(term.get("end", "9999-12-31"))
            if not (start <= active_on < end):
                continue
            name = person.get("name", {})
            full_name = name.get("official_full") or " ".join(
                part for part in [name.get("first"), name.get("middle"), name.get("last"), name.get("suffix")] if part
            )
            key = (term["state"], str(term.get("district", 0)))
            members[key] = {
                "representative_name": full_name,
                "party": term.get("party", ""),
                "bioguide_id": person.get("id", {}).get("bioguide", ""),
            }
    return members


def main():
    active_on = dt.date.today()
    members = active_house_members(active_on)
    zip_rows = csv.DictReader(io.StringIO(fetch_text(ZIP_DISTRICT_URL)))

    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "zip",
                "state_abbr",
                "state",
                "congressional_district",
                "representative_name",
                "party",
                "bioguide_id",
                "lookup_status",
                "active_on",
                "source_zip_district",
                "source_member",
            ],
        )
        writer.writeheader()
        for row in zip_rows:
            state_abbr = row["state_abbr"]
            district = str(int(row["cd"])) if row["cd"].isdigit() else row["cd"]
            member = members.get((state_abbr, district), {})
            writer.writerow(
                {
                    "zip": row["zcta"],
                    "state_abbr": state_abbr,
                    "state": STATE_NAMES.get(state_abbr, state_abbr),
                    "congressional_district": district,
                    "representative_name": member.get("representative_name", ""),
                    "party": member.get("party", ""),
                    "bioguide_id": member.get("bioguide_id", ""),
                    "lookup_status": "matched_district_member" if member else "district_without_current_member",
                    "active_on": active_on.isoformat(),
                    "source_zip_district": ZIP_DISTRICT_URL,
                    "source_member": LEGISLATORS_URL,
                }
            )

    print(f"Wrote {OUTPUT}")
    print(f"House member district rows loaded: {len(members)}")


if __name__ == "__main__":
    main()
