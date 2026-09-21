import json
import os
import sys
from datetime import datetime, timezone

import requests

from sites.playstation_direct import check_stock


PRODUCTS = {
    "wolverine_battle_yellow_covers": {
        "name": "Wolverine Battle Yellow PS5 Pro Console Covers",
        "url": "https://direct.playstation.com/it-it/buy-accessories/playstation5-pro-console-covers-marvels-wolverine-battle-yellow-limited-edition",
    },

    "ps5_pro": {
        "name": "PlayStation 5 Pro",
        "url": "https://direct.playstation.com/it-it/buy-consoles/playstation5-pro-console",
    },

    "wolverine_battle_yellow_controller": {
        "name": "DualSense Wolverine Battle Yellow",
        "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-marvels-wolverine-battle-yellow-limited-edition-for-ps5-pc-mac-mobile",
    },

    "gta_vi_black_controller": {
        "name": "DualSense GTA VI Black",
        "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-grand-theft-auto-vi-black-limited-edition-for-ps5-pc-mac-mobile",
    },

    "gta_vi_white_controller": {
        "name": "DualSense GTA VI White",
        "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-grand-theft-auto-vi-white-limited-edition-for-ps5-pc-mac-mobile",
    },

    "wolverine_adamantium_controller": {
        "name": "DualSense Wolverine Adamantium",
        "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-marvels-wolverine-adamantium-limited-edition-for-ps5-pc-mac-mobile",
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
    """
    Invia su Telegram tutte le nuove disponibilità rilevate.
    """

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


def main():
    state = load_state()

    now = datetime.now(timezone.utc).isoformat()

    print("=" * 80)
    print("PLAYSTATION DIRECT STOCK MONITOR")
    print("=" * 80)
    print()

    notifications = []

    for product_id, product in PRODUCTS.items():

        print(f"Checking: {product['name']}")

        status = check_stock(product["url"])

        previous = state.get(product_id, {}).get("status")

        print(f"  Previous: {previous}")
        print(f"  Current:  {status}")

        # ============================================================
        # NOTIFICA
        # ============================================================

        if status == "AVAILABLE" and previous != "AVAILABLE":
            notifications.append(
                {
                    "id": product_id,
                    "name": product["name"],
                    "url": product["url"],
                }
            )

        # ============================================================
        # AGGIORNAMENTO STATO
        # ============================================================

        if status in ("AVAILABLE", "OUT_OF_STOCK"):
            state[product_id] = {
                "status": status,
                "last_check": now,
                "last_result": status,
            }

        else:
            # UNKNOWN / ERROR:
            # manteniamo l'ultimo stato affidabile.

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


if __name__ == "__main__":
    sys.exit(main())
