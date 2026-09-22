from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def check_stock(url: str) -> str:
    """
    Controlla lo stato stock di un prodotto Amazon.

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
                timezone_id="Europe/Rome",
                viewport={
                    "width": 1440,
                    "height": 1000,
                },
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )

            page = context.new_page()

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            page.wait_for_timeout(4000)

            title = page.title().strip().lower()

            body_text = (
                page.locator("body")
                .inner_text()
                .strip()
                .lower()
            )

            # ---------------------------------------------------------
            # 1. Controlli anti-bot / CAPTCHA
            # ---------------------------------------------------------

            anti_bot_markers = [
                "captcha",
                "robot check",
                "enter the characters you see below",
                "sorry, we just need to make sure you're not a robot",
                "type the characters you see in this image",
            ]

            if any(
                marker in title or marker in body_text
                for marker in anti_bot_markers
            ):
                browser.close()
                return "UNKNOWN"

            # ---------------------------------------------------------
            # 2. Verifica che siamo realmente sulla pagina prodotto
            # ---------------------------------------------------------

            asin = page.locator(
                'input[name="ASIN"]'
            ).first

            asin_found = asin.count() > 0

            product_title = page.locator(
                "#productTitle"
            ).first

            product_title_found = product_title.count() > 0

            if not asin_found and not product_title_found:
                browser.close()
                return "UNKNOWN"

            if product_title_found:
                product_title_text = (
                    product_title.inner_text()
                    .strip()
                    .lower()
                )

                if not product_title_text:
                    browser.close()
                    return "UNKNOWN"

            # ---------------------------------------------------------
            # 3. Controllo esplicito di indisponibilità
            # ---------------------------------------------------------

            out_of_stock_markers = [
                "currently unavailable",
                "currently unavailable.",
                "non disponibile",
                "non disponibile.",
                "prodotto non disponibile",
                "temporaneamente non disponibile",
                "esaurito",
                "al momento non disponibile",
            ]

            if any(
                marker in body_text
                for marker in out_of_stock_markers
            ):
                browser.close()
                return "OUT_OF_STOCK"

            # ---------------------------------------------------------
            # 4. Controllo pulsanti di acquisto
            # ---------------------------------------------------------

            purchase_selectors = [
                "#add-to-cart-button",
                "#buy-now-button",
                "input[name='submit.add-to-cart']",
                "input[name='submit.buy-now']",
                "#add-to-cart-button-ubb",
            ]

            for selector in purchase_selectors:

                buttons = page.locator(selector)

                count = buttons.count()

                for i in range(count):

                    button = buttons.nth(i)

                    try:
                        visible = button.is_visible()
                    except Exception:
                        continue

                    if not visible:
                        continue

                    try:
                        disabled = button.is_disabled()
                    except Exception:
                        disabled = False

                    if disabled:
                        continue

                    try:
                        aria_disabled = button.get_attribute(
                            "aria-disabled"
                        )
                    except Exception:
                        aria_disabled = None

                    if aria_disabled == "true":
                        continue

                    try:
                        text = (
                            button.inner_text()
                            .strip()
                            .lower()
                        )
                    except Exception:
                        text = ""

                    try:
                        value = (
                            button.get_attribute("value")
                            or ""
                        ).strip().lower()
                    except Exception:
                        value = ""

                    combined = f"{text} {value}"

                    purchase_markers = [
                        "add to cart",
                        "aggiungi al carrello",
                        "buy now",
                        "acquista ora",
                    ]

                    if any(
                        marker in combined
                        for marker in purchase_markers
                    ):
                        browser.close()
                        return "AVAILABLE"

            # ---------------------------------------------------------
            # 5. Alcune pagine Amazon mostrano l'offerta tramite
            #    un contenitore con messaggi di acquisto.
            # ---------------------------------------------------------

            purchase_area_selectors = [
                "#buybox",
                "#buybox_feature_div",
                "#buyBoxAccordion",
                "#desktop_buybox",
                "#rightCol",
            ]

            for selector in purchase_area_selectors:

                area = page.locator(selector).first

                if area.count() == 0:
                    continue

                try:
                    if not area.is_visible():
                        continue
                except Exception:
                    continue

                try:
                    area_text = (
                        area.inner_text()
                        .strip()
                        .lower()
                    )
                except Exception:
                    continue

                if not area_text:
                    continue

                # Se l'area contiene chiaramente un'opzione
                # acquistabile, controlliamo anche i suoi pulsanti.
                area_buttons = area.locator("button, input")

                for i in range(area_buttons.count()):

                    button = area_buttons.nth(i)

                    try:
                        if not button.is_visible():
                            continue
                    except Exception:
                        continue

                    try:
                        disabled = button.is_disabled()
                    except Exception:
                        disabled = False

                    if disabled:
                        continue

                    try:
                        text = (
                            button.inner_text()
                            .strip()
                            .lower()
                        )
                    except Exception:
                        text = ""

                    try:
                        value = (
                            button.get_attribute("value")
                            or ""
                        ).strip().lower()
                    except Exception:
                        value = ""

                    combined = f"{text} {value}"

                    purchase_markers = [
                        "add to cart",
                        "aggiungi al carrello",
                        "buy now",
                        "acquista ora",
                    ]

                    if any(
                        marker in combined
                        for marker in purchase_markers
                    ):
                        browser.close()
                        return "AVAILABLE"

            # ---------------------------------------------------------
            # 6. Se Amazon ci mostra chiaramente una condizione
            #    di esaurimento, la consideriamo OUT_OF_STOCK.
            # ---------------------------------------------------------

            explicit_out_markers = [
                "unavailable",
                "non disponibile",
                "esaurito",
            ]

            if any(
                marker in body_text
                for marker in explicit_out_markers
            ):
                browser.close()
                return "OUT_OF_STOCK"

            # ---------------------------------------------------------
            # 7. Situazione non determinabile con sicurezza
            # ---------------------------------------------------------

            browser.close()
            return "UNKNOWN"

    except PlaywrightTimeoutError:
        return "ERROR"

    except Exception:
        return "ERROR"
