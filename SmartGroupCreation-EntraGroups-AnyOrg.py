import requests

# ------------------------
# CONFIG
# ------------------------
JAMF_URL = "https://yourcompany.jamfcloud.com"

CLIENT_ID = ""      # your API client ID
CLIENT_SECRET = ""  # your API client secret

# Test mode
DRY_RUN = False   # True = don't create, just print actions
TEST_GROUPS = ["Site 1", "Site 2"]  # Only process these groups

print("Script started")

# ------------------------
# AUTHENTICATE (OAuth Client Credentials Flow)
# ------------------------
print("Requesting token…")

resp = requests.post(
    f"{JAMF_URL}/api/oauth/token",
    data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
)

print(f"Token request status: {resp.status_code}")
print(f"Raw response: {resp.text}")

resp.raise_for_status()
token = resp.json()["access_token"]
print("Got token")

print(f"Starting get headers")

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# ------------------------
# GET COMPUTERS W/ EXTENSION ATTRIBUTES
# ------------------------
print(f"Get computer extension attributes")


comp_resp = requests.get(
    f"{JAMF_URL}/api/v2/computers-inventory?section=EXTENSION_ATTRIBUTES&section=USER_AND_LOCATION&page=0&page-size=100&sort=general.name:asc",
    headers=headers
)

print(f"Computers status: {comp_resp.status_code}")
print(f"Computers raw JSON: {comp_resp.text[:500]}...")  # preview first 500 chars

comp_json = comp_resp.json()

# handle both list and dict-with-results cases
if isinstance(comp_json, dict) and "results" in comp_json:
    computers = comp_json["results"]
elif isinstance(comp_json, list):
    computers = comp_json
else:
    computers = []

print(f"Parsed {len(computers)} computers from Jamf")

# Build {groupName: count}
group_map = {}
for comp in computers:
    eas = comp.get("userAndLocation", {}).get("extensionAttributes", [])
    for ea in eas:
        if ea.get("name") == "Entra Groups" and ea.get("values"):
            for g in ea["values"]:
                group_map[g.strip()] = group_map.get(g.strip(), 0) + 1


# ------------------------
# GET EXISTING SMART GROUPS
# ------------------------

print(f"Checking if matches existing group")

existing_resp = requests.get(
    f"{JAMF_URL}/api/v2/computer-groups/smart-groups?page=0&page-size=100&sort=id:asc",
    headers=headers
)
existing = existing_resp.json().get("results", [])
existing_names = [sg["name"] for sg in existing]

print(f"Found {len(existing_names)} existing smart groups")

# ------------------------
# CREATE SMART GROUPS FOR TEST GROUPS ONLY
# ------------------------
for group, count in group_map.items():
    if group not in TEST_GROUPS:
        print(f"Skipping {group} (not in TEST_GROUPS)")
        continue

    sg_name = f"SG_Entra_{group}"

    if count == 0:
        print(f"Skipping {sg_name} (no members)")
        continue

    if sg_name in existing_names:
        print(f"Already exists: {sg_name}")
        continue

    print(f"[TEST] Would create Smart Group: {sg_name} with {count} Macs")

    if not DRY_RUN:
        payload = {
            "name": sg_name,
            "criteria": [
                {
                    "name": "Entra Groups",
                    "priority": 0,
                    "andOr": "and",
                    "searchType": "like",
                    "value": group
                }
            ]
        }
        r = requests.post(f"{JAMF_URL}/api/v2/computer-groups/smart-groups", headers=headers, json=payload)
        if r.status_code in (200, 201):
            print(f"Created Smart Group: {sg_name}")
        else:
            print(f"Failed to create {sg_name}: {r.status_code} {r.text}")


print(f"End of script")
