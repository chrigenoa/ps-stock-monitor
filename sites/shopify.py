from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def check_stock(url: str) -> str:
    """
    Controlla lo stato stock di un prodotto Shopify nel mercato italiano.

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
                locale="en-US",
                timezone_id="Europe/Rome",
                viewport={
                    "width": 1440,
                    "height": 1000,
                },
            )

            page = context.new_page()

            # ==========================================================
            # 1. APERTURA PAGINA
            # ==========================================================

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            page.wait_for_timeout(2500)

            # ==========================================================
            # 2. SELEZIONE MERCATO ITALIANO
            #
            # Shopify usa un input hidden country_code.
            # Non possiamo usare fill() perché l'input non è visibile.
            # Impostiamo quindi IT via JavaScript e inviamo il form.
            # ==========================================================

            localization_form = page.locator(
                'form[action="/localization"]'
            ).first

            if localization_form.count() == 0:
                browser.close()
                return "UNKNOWN"

            country_input = localization_form.locator(
                'input[name="country_code"]'
            ).first

            if country_input.count() == 0:
                browser.close()
                return "UNKNOWN"

            try:
                page.evaluate(
                    """
                    () => {
                        const input =
                            document.querySelector(
                                'form[action="/localization"] input[name="country_code"]'
                            );

                        if (!input) {
                            throw new Error(
                                "country_code input not found"
                            );
                        }

                        input.value = "IT";

                        const form = input.closest("form");

                        if (!form) {
                            throw new Error(
                                "localization form not found"
                            );
                        }

                        form.submit();
                    }
                    """
                )

            except Exception:
                browser.close()
                return "UNKNOWN"

            page.wait_for_timeout(4000)

            # ==========================================================
            # 3. VERIFICA CHE SHOPIFY ABBIA APPLICATO L'ITALIA
            # ==========================================================

            cookies = context.cookies()

            italian_localization = any(
                cookie["name"] == "localization"
                and cookie["value"] == "IT"
                for cookie in cookies
            )

            if not italian_localization:
                browser.close()
                return "UNKNOWN"

            # ==========================================================
            # 4. IDENTIFICAZIONE DEL PRODOTTO
            # ==========================================================

            product_title = page.locator("h1").first

            if product_title.count() == 0:
                browser.close()
                return "UNKNOWN"

            product_title_text = (
                product_title.inner_text()
                .strip()
                .lower()
            )

            if (
                "grand theft auto vi" not in product_title_text
                or "album" not in product_title_text
            ):
                browser.close()
                return "UNKNOWN"

            # ==========================================================
            # 5. CONTENITORE REALE DEL PRODOTTO
            #
            # Dal test diagnostico sappiamo che il contenitore corretto
            # è:
            #
            # section.product__info-container
            # ==========================================================

            product_container = page.locator(
                "section.product__info-container"
            ).first

            if product_container.count() == 0:
                browser.close()
                return "UNKNOWN"

            # ==========================================================
            # 6. CONTROLLO TESTUALE SOLD OUT
            # ==========================================================

            container_text = (
                product_container
                .inner_text()
                .strip()
                .lower()
            )

            if "sold out" in container_text:
                browser.close()
                return "OUT_OF_STOCK"

            # ==========================================================
            # 7. CONTROLLO PULSANTI DEL PRODOTTO
            # ==========================================================

            buttons = product_container.locator(
                "button"
            )

            available_button_found = False
            sold_out_button_found = False

            purchase_markers = [
                "add to cart",
                "pre-order now",
                "pre order now",
                "aggiungi al carrello",
                "acquista",
                "preordina",
            ]

            for i in range(buttons.count()):

                button = buttons.nth(i)

                try:
                    visible = button.is_visible()
                except Exception:
                    continue

                if not visible:
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
                    disabled = button.is_disabled()
                except Exception:
                    disabled = False

                # Sold Out esplicito
                if "sold out" in text:
                    sold_out_button_found = True
                    continue

                # Pulsante di acquisto attivo
                if (
                    not disabled
                    and any(
                        marker in text
                        for marker in purchase_markers
                    )
                ):
                    available_button_found = True
                    break

            # ==========================================================
            # 8. RISULTATO FINALE
            # ==========================================================

            if available_button_found:
                browser.close()
                return "AVAILABLE"

            if sold_out_button_found:
                browser.close()
                return "OUT_OF_STOCK"

            browser.close()
            return "UNKNOWN"

    except PlaywrightTimeoutError:
        return "ERROR"

    except Exception:
        return "ERROR"
