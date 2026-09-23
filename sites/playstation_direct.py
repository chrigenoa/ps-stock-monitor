from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def check_playstation_direct(url: str) -> str:
    """
    Controlla lo stato stock di un prodotto PlayStation Direct.

    Restituisce esclusivamente:
        AVAILABLE
        OUT_OF_STOCK
        UNKNOWN
        ERROR
    """

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            context = browser.new_context(
                locale="it-IT",
                viewport={
                    "width": 1440,
                    "height": 1000,
                },
            )

            page = context.new_page()

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            # Lasciamo terminare il rendering dinamico del componente prodotto.
            page.wait_for_timeout(1500)

            # Troviamo l'H1 del prodotto.
            h1 = page.locator("h1").first

            if h1.count() == 0:
                browser.close()
                return "UNKNOWN"

            # Nel DOM attuale di PlayStation Direct il componente
            # prodotto è il parent diretto dell'H1.
            hero = h1.locator("xpath=..")

            if hero.count() == 0:
                browser.close()
                return "UNKNOWN"

            # Usiamo SOLO i pulsanti add-to-cart del prodotto principale.
            buttons = hero.locator("button.add-to-cart")

            count = buttons.count()

            if count == 0:
                browser.close()
                return "UNKNOWN"

            # Cerchiamo un pulsante principale realmente visibile
            # e utilizzabile.
            for i in range(count):
                button = buttons.nth(i)

                try:
                    visible = button.is_visible()
                    enabled = button.is_enabled()
                except Exception:
                    continue

                if visible and enabled:
                    try:
                        text = button.inner_text().strip().lower()
                    except Exception:
                        text = ""

                    if "aggiungi al carrello" in text:
                        browser.close()
                        return "AVAILABLE"

            # Esiste il pulsante principale ma non è utilizzabile:
            # nello stato attuale del sito significa prodotto non disponibile.
            browser.close()
            return "OUT_OF_STOCK"

    except PlaywrightTimeoutError:
        return "ERROR"

    except Exception:
        return "ERROR"
