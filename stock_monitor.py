import json
import os
import sys
from datetime import datetime, timezone

import requests

from sites.playstation_direct import check_stock as check_playstation_direct
from sites.shopify import check_stock as check_shopify

PRODUCTS = {
"wolverine_battle_yellow_covers": {
"name": "Wolverine Battle Yellow PS5 Pro Console Covers",
"site": "playstation_direct",
"url": "https://direct.playstation.com/it-it/buy-accessories/playstation5-pro-console-covers-marvels-wolverine-battle-yellow-limited-edition",
},

"ps5_pro": {
    "name": "PlayStation 5 Pro",
    "site": "playstation_direct",
    "url": "https://direct.playstation.com/it-it/buy-consoles/playstation5-pro-console",
},

"wolverine_battle_yellow_controller": {
    "name": "DualSense Wolverine Battle Yellow",
    "site": "playstation_direct",
    "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-marvels-wolverine-battle-yellow-limited-edition-for-ps5-pc-mac-mobile",
},

"gta_vi_black_controller": {
    "name": "DualSense GTA VI Black",
    "site": "playstation_direct",
    "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-grand-theft-auto-vi-black-limited-edition-for-ps5-pc-mac-mobile",
},

"gta_vi_white_controller": {
    "name": "DualSense GTA VI White",
    "site": "playstation_direct",
    "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-grand-theft-auto-vi-white-limited-edition-for-ps5-pc-mac-mobile",
},

"wolverine_adamantium_controller": {
    "name": "DualSense Wolverine Adamantium",
    "site": "playstation_direct",
    "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-marvels-wolverine-adamantium-limited-edition-for-ps5-pc-mac-mobile",
},

"gta_vi_album_vinyl": {
    "name": "GTA VI The Album - Limited-Edition Vinyl",
    "site": "shopify",
    "url": "https://www.gtavi-thealbum.com/en-eu/products/grand-theft-auto-vi-the-album-limited-edition-vinyl",
},


}

STATE_FILE = "stock_state.json"

def load_state():
if not os.path.exists(STATE_FILE):
return {}

try:
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
except Exception:
    return {}


def save_state(state):
with open(STATE_FILE, "w", encoding="utf-8") as f:
json.dump(
state,
f,
indent=2,
ensure_ascii=False,
)

def send_telegram(notifications):
token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")

if not token or not chat_id:
    print("Telegram credentials not configured.")
    return False

telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"

success = True

for item in notifications:
    message = (
        "🟢 DISPONIBILE\n\n"
        f"{item['name']}\n\n"
        f"{item['url']}"
    )

    try:
        response = requests.post(
            telegram_url,
            data={
                "chat_id": chat_id,
                "text": message,
            },
            timeout=20,
        )

        print(f"Telegram HTTP: {response.status_code}")
        print(f"Telegram response: {response.text}")

        if not response.ok:
            success = False

    except Exception as e:
        print(f"Telegram error: {e}")
        success = False

return success


def check_product(product):
site = product.get("site")
url = product["url"]

if site == "playstation_direct":
    return check_playstation_direct(url)

if site == "shopify":
    return check_shopify(url)

print(f"Unknown site adapter: {site}")
return "UNKNOWN"


def main():
state = load_state()
now = datetime.now(timezone.utc).isoformat()


print("=" * 80)
print("PLAYSTATION / SHOPIFY STOCK MONITOR")
print("=" * 80)
print()

notifications = []

for product_id, product in PRODUCTS.items():
    print(f"Checking: {product['name']}")
    print(f"  Site: {product['site']}")

    status = check_product(product)
    previous = state.get(product_id, {}).get("status")

    print(f"  Previous: {previous}")
    print(f"  Current:  {status}")

    if status == "AVAILABLE" and previous != "AVAILABLE":
        notifications.append(
            {
                "id": product_id,
                "name": product["name"],
                "url": product["url"],
            }
        )

    if status in ("AVAILABLE", "OUT_OF_STOCK"):
        state[product_id] = {
            "status": status,
            "last_check": now,
            "last_result": status,
        }

    else:
        previous_data = state.get(product_id, {})

        state[product_id] = {
            "status": previous_data.get("status"),
            "last_check": now,
            "last_result": status,
        }

    print()

save_state(state)

print("=" * 80)
print("SUMMARY")
print("=" * 80)

if notifications:
    print()
    print("NEW AVAILABLE PRODUCTS:")

    for item in notifications:
        print(f"- {item['name']}")
        print(f"  {item['url']}")

    print()
    print("Sending Telegram notifications...")

    telegram_ok = send_telegram(notifications)

    if telegram_ok:
        print("Telegram notifications sent successfully.")
    else:
        print("Telegram notification failed.")

else:
    print("No new availability detected.")

print()
print("=" * 80)

return 0


if **name** == "**main**":
sys.exit(main)
