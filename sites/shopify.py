from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


PRODUCT_URL = (
    "https://www.gtavi-thealbum.com/en-eu/products/"
    "grand-theft-auto-vi-the-album-limited-edition-vinyl"
)


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
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )

            page = context.new_page()

            # ---------------------------------------------------------
            # 1. APERTURA PAGINA
            # ---------------------------------------------------------

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            page.wait_for_timeout(2500)

            # ---------------------------------------------------------
            # 2. SELEZIONE MERCATO ITALIANO
            # ---------------------------------------------------------

            localization_form = page.locator(
                'form[action="/localization"]'
            ).first

            if localization_form.count() == 0:
                browser.close()
                return "UNKNOWN"

            selector_button = localization_form.locator(
                "button.disclosure__button"
            ).first

            if selector_button.count() == 0:
                browser.close()
                return "UNKNOWN"

            try:
                selector_button.click(
                    force=True,
                    timeout=10000,
                )
            except Exception:
                browser.close()
                return "UNKNOWN"

            page.wait_for_timeout(500)

            italy_link = localization_form.locator(
                'a.disclosure__link[data-value="IT"]'
            ).first

            if italy_link.count() == 0:
                browser.close()
                return "UNKNOWN"

            # Il link può risultare hidden secondo Playwright,
            # ma il JS ufficiale del sito utilizza comunque proprio
            # questo elemento per impostare country_code=IT.
            #
            # force=True permette di attivare esattamente il
            # meccanismo previsto dal sito.

            try:
                italy_link.click(
                    force=True,
                    timeout=10000,
                )
            except Exception:
                browser.close()
                return "UNKNOWN"

            page.wait_for_timeout(2500)

            # ---------------------------------------------------------
            # 3. VERIFICA CHE SIAMO DAVVERO SUL MERCATO ITALIANO
            # ---------------------------------------------------------

            body_text = page.locator("body").inner_text()

            body_lower = body_text.lower()

            italian_market = (
                "€123,99" in body_text
                or "123,99" in body_text
            )

            # Se il sito non ha applicato il mercato italiano,
            # non prendiamo decisioni sullo stock.
            if not italian_market:
                browser.close()
                return "UNKNOWN"

            # ---------------------------------------------------------
            # 4. IDENTIFICAZIONE DEL PRODOTTO
            # ---------------------------------------------------------

            product_title = page.locator(
                "h1"
            ).first

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

            # ---------------------------------------------------------
            # 5. INDIVIDUAZIONE DELL'AREA PRODOTTO
            # ---------------------------------------------------------

            #
            # Shopify normalmente struttura la pagina in modo che
            # l'H1 appartenga al blocco principale del prodotto.
            #
            # Partiamo dall'H1 e risaliamo il DOM cercando un
            # contenitore che contenga anche l'area acquisto.
            #

            product_container = None

            candidates = [
                "xpath=ancestor::*[contains(@class,'product')]",
                "xpath=ancestor::*[contains(@class,'product__info')]",
                "xpath=ancestor::*[contains(@class,'product-form')]",
            ]

            for selector in candidates:

                candidate = product_title.locator(
                    selector
                ).first

                if candidate.count() == 0:
                    continue

                try:
                    text = candidate.inner_text().strip()

                    if len(text) > 0:
                        product_container = candidate
                        break

                except Exception:
                    continue

            # Se non riusciamo a individuare un contenitore
            # affidabile, analizziamo comunque il blocco vicino
            # all'H1, senza usare l'intera pagina.
            if product_container is None:

                product_container = product_title.locator(
                    "xpath=.."
                ).first

                if product_container.count() == 0:
                    browser.close()
                    return "UNKNOWN"

            # ---------------------------------------------------------
            # 6. CONTROLLO "SOLD OUT"
            # ---------------------------------------------------------

            container_text = (
                product_container
                .inner_text()
                .strip()
            )

            container_lower = container_text.lower()

            sold_out_markers = [
                "sold out",
                "sold-out",
                "soldout",
            ]

            for marker in sold_out_markers:

                if marker in container_lower:
                    browser.close()
                    return "OUT_OF_STOCK"

            # ---------------------------------------------------------
            # 7. CONTROLLO PULSANTI DI ACQUISTO
            # ---------------------------------------------------------

            purchase_buttons = product_container.locator(
                "button"
            )

            available_button_found = False

            for i in range(purchase_buttons.count()):

                button = purchase_buttons.nth(i)

                try:
                    if not button.is_visible():
                        continue
                except Exception:
                    continue

                try:
                    button_text = (
                        button.inner_text()
                        .strip()
                        .lower()
                    )
                except Exception:
                    button_text = ""

                try:
                    disabled = button.is_disabled()
                except Exception:
                    disabled = False

                if disabled:
                    continue

                purchase_markers = [
                    "add to cart",
                    "pre-order now",
                    "pre order now",
                    "aggiungi al carrello",
                    "acquista",
                    "preordina",
                ]

                if any(
                    marker in button_text
                    for marker in purchase_markers
                ):
                    available_button_found = True
                    break

            if available_button_found:
                browser.close()
                return "AVAILABLE"

            # ---------------------------------------------------------
            # 8. CONTROLLO FORM DI ACQUISTO
            # ---------------------------------------------------------

            forms = product_container.locator(
                'form[action*="/cart/add"]'
            )

            if forms.count() > 0:

                for i in range(forms.count()):

                    form = forms.nth(i)

                    try:
                        if not form.is_visible():
                            continue
                    except Exception:
                        continue

                    try:
                        form_text = (
                            form.inner_text()
                            .strip()
                            .lower()
                        )
                    except Exception:
                        form_text = ""

                    if any(
                        marker in form_text
                        for marker in (
                            "add to cart",
                            "pre-order now",
                            "pre order now",
                            "aggiungi al carrello",
                            "acquista",
                            "preordina",
                        )
                    ):
                        browser.close()
                        return "AVAILABLE"

            # ---------------------------------------------------------
            # 9. CONTROLLO ESPLICITO SOLD OUT NEL BLOCCO PRODOTTO
            # ---------------------------------------------------------

            if any(
                marker in container_lower
                for marker in (
                    "sold out",
                    "sold-out",
                    "soldout",
                )
            ):
                browser.close()
                return "OUT_OF_STOCK"

            # ---------------------------------------------------------
            # 10. NESSUNA EVIDENZA SUFFICIENTE
            # ---------------------------------------------------------

            browser.close()
            return "UNKNOWN"

    except PlaywrightTimeoutError:
        return "ERROR"

    except Exception:
        return "ERROR"
