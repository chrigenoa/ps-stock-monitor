import json
import os
import requests
import asyncio

from sites.playstation_direct import check_playstation_direct
from sites.shopify import check_shopify
from sites.amazon import check_amazon


STATE_FILE = "stock_state.json"


PRODUCTS = {
    "wolverine_covers": {
        "name": "Cover PS5 Pro Wolverine Battle Yellow Limited Edition",
        "site": "playstation_direct",
        "url": "https://direct.playstation.com/it-it/buy-accessories/playstation5-pro-console-covers-marvels-wolverine-battle-yellow-limited-edition",
    },

    "ps5_pro": {
        "name": "PlayStation 5 Pro",
        "site": "playstation_direct",
        "url": "https://direct.playstation.com/it-it/buy-consoles/playstation5-pro-console",
    },

    "wolverine_controller": {
        "name": "DualSense Wolverine Battle Yellow Limited Edition",
        "site": "playstation_direct",
        "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-marvels-wolverine-battle-yellow-limited-edition-for-ps5-pc-mac-mobile",
    },

    "gta_vi_black_controller": {
        "name": "DualSense GTA VI Black Limited Edition",
        "site": "playstation_direct",
        "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-grand-theft-auto-vi-black-limited-edition-for-ps5-pc-mac-mobile",
    },

    "gta_vi_white_controller": {
        "name": "DualSense GTA VI White Limited Edition",
        "site": "playstation_direct",
        "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-grand-theft-auto-vi-white-limited-edition-for-ps5-pc-mac-mobile",
    },

    "wolverine_adamantium_controller": {
        "name": "DualSense Wolverine Adamantium Limited Edition",
        "site": "playstation_direct",
        "url": "https://direct.playstation.com/it-it/buy-accessories/dualsense-wireless-controller-marvels-wolverine-adamantium-limited-edition-for-ps5-pc-mac-mobile",
    },

    "gta_vi_album_vinyl": {
        "name": "GTA VI The Album - Limited-Edition Vinyl",
        "site": "shopify",
        "url": "https://www.gtavi-thealbum.com/en-eu/products/grand-theft-auto-vi-the-album-limited-edition-vinyl",
    },

    "pokemon_30th_anniversary": {
        "name": "Pokémon Set Allenatore Fuoriclasse 30° Anniversario",
        "site": "amazon",
        "url": "https://www.amazon.it/dp/B0H9HFPRRD/",
    },
}


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


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram secrets non configurati.")
        return False

    url = (
        f"https://api.telegram.org/bot{token}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": message,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=30,
        )

        print(
            f"Telegram HTTP {response.status_code}: "
            f"{response.text}"
        )

        return response.ok

    except Exception as e:
        print(f"Errore Telegram: {e}")
        return False


def check_product(product):
    site = product["site"]

    if site == "playstation_direct":
        return check_playstation_direct(
            product["url"]
        )

    if site == "shopify":
        return check_shopify(
            product["url"]
        )

    if site == "amazon":
        return asyncio.run(
            check_amazon()
        )

    print(f"Sito non supportato: {site}")
    return "ERROR", None


def main():
    print("========================================")
    print("FULL STOCK MONITOR")
    print("========================================")

    state = load_state()

    for product_id, product in PRODUCTS.items():

        print()
        print("----------------------------------------")
        print(f"PRODUCT: {product['name']}")
        print(f"SITE: {product['site']}")
        print("----------------------------------------")

        try:
            result = check_product(product)

            # I parser restituiscono normalmente:
            # (status, eventuale prezzo)
            if isinstance(result, tuple):
                status = result[0]
                price = (
                    result[1]
                    if len(result) > 1
                    else None
                )
            else:
                status = result
                price = None

        except Exception as e:
            print(
                f"Errore durante il controllo "
                f"{product_id}: {e}"
            )

            status = "ERROR"
            price = None

        previous_status = state.get(
            product_id,
            "UNKNOWN",
        )

        print(f"Previous status: {previous_status}")
        print(f"Current status: {status}")

        if price is not None:
            print(
                f"Current price: {price:.2f} EUR"
            )

        # -------------------------------------------------
        # AVAILABLE
        # -------------------------------------------------

        if status == "AVAILABLE":

            # Notifica solamente quando passa
            # da uno stato diverso da AVAILABLE
            # a AVAILABLE.
            if previous_status != "AVAILABLE":

                message = (
                    "🟢 DISPONIBILE!\n\n"
                    f"{product['name']}\n"
                    f"{product['url']}"
                )

                if price is not None:
                    message += (
                        f"\n\n💰 Prezzo: "
                        f"{price:.2f} €"
                    )

                print(
                    "Invio notifica Telegram..."
                )

                send_telegram(message)

            else:
                print(
                    "Già AVAILABLE: nessuna "
                    "notifica Telegram."
                )

            # Salviamo AVAILABLE
            state[product_id] = "AVAILABLE"

        # -------------------------------------------------
        # OUT OF STOCK
        # -------------------------------------------------

        elif status == "OUT_OF_STOCK":

            state[product_id] = "OUT_OF_STOCK"

            print(
                "OUT_OF_STOCK salvato nello stato."
            )

        # -------------------------------------------------
        # UNKNOWN / ERROR
        # -------------------------------------------------

        elif status in ("UNKNOWN", "ERROR"):

            # IMPORTANTISSIMO:
            # non sovrascriviamo uno stato valido
            # con UNKNOWN o ERROR.
            print(
                f"{status}: mantengo lo stato "
                f"precedente ({previous_status})."
            )

        else:

            print(
                f"Stato sconosciuto: {status}. "
                f"Non modifico lo stato precedente."
            )

    save_state(state)

    print()
    print("========================================")
    print("STOCK STATE FINALE")
    print("========================================")

    print(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
