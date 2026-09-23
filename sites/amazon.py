import re
from playwright.async_api import async_playwright


ASIN = "B0H9HFPRRD"
PRODUCT_URL = f"https://www.amazon.it/dp/{ASIN}/"
ZIP_CODE = "00100"


async def set_delivery_location(page):
    await page.goto(
        "https://www.amazon.it/",
        wait_until="domcontentloaded",
        timeout=60000,
    )

    await page.wait_for_timeout(3000)

    body = await page.locator("body").inner_text()

    # Amazon può mostrare una pagina intermedia
    # "Continua con gli acquisti"
    if "Fai clic sul pulsante qui sotto per continuare" in body:
        buttons = page.get_by_text(
            "Continua con gli acquisti",
            exact=True,
        )

        for i in range(await buttons.count()):
            button = buttons.nth(i)

            if await button.is_visible():
                await button.click()
                await page.wait_for_timeout(4000)
                break

    # Apri il popup della località
    ingress = page.locator("#glow-ingress-block")

    if await ingress.count() == 0:
        return False

    if not await ingress.is_visible():
        return False

    await ingress.click()
    await page.wait_for_timeout(1500)

    # Inserisci CAP italiano
    zip_input = page.locator("#GLUXZipUpdateInput")

    if await zip_input.count() == 0:
        return False

    if not await zip_input.is_visible():
        return False

    await zip_input.fill(ZIP_CODE)

    # Pulsante reale di conferma del CAP
    confirm = page.locator(
        "#GLUXZipInputSection input[type='submit']"
    )

    if await confirm.count() == 0:
        return False

    if not await confirm.is_visible():
        return False

    await confirm.click()
    await page.wait_for_timeout(2000)

    # Amazon mostra il CAP confermato
    confirmed = page.locator("#GLUXZipConfirmationValue")

    if await confirmed.count() == 0:
        return False

    if not await confirmed.is_visible():
        return False

    value = (await confirmed.inner_text()).strip()

    if ZIP_CODE not in value:
        return False

    return True


async def get_offer_listing(page):
    await page.goto(
        PRODUCT_URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    await page.wait_for_timeout(4000)

    body = await page.locator("body").inner_text()

    # Pagina intermedia/anomala
    if "Fai clic sul pulsante qui sotto per continuare" in body:
        return None

    # Verifica che sia realmente il prodotto corretto
    title = page.locator("#productTitle")

    if await title.count() == 0:
        return None

    title_text = " ".join(
        (await title.first.inner_text()).split()
    )

    if "Pokémon" not in title_text:
        return None

    # Link "Visualizza tutte le opzioni di acquisto"
    offer_link = page.locator(
        "a[href*='/gp/offer-listing/'], "
        "a[href*='offer-listing']"
    )

    for i in range(await offer_link.count()):
        link = offer_link.nth(i)

        if await link.is_visible():
            href = await link.get_attribute("href")

            if href:
                if href.startswith("/"):
                    href = "https://www.amazon.it" + href

                return href

    return None


def extract_price(text):
    """
    Estrae un prezzo in formato italiano.

    Esempi:
    114,90 €
    55,00 €
    1.234,90 €
    """

    match = re.search(
        r"(\d{1,4}(?:\.\d{3})*,\d{2})\s*€",
        text,
    )

    if not match:
        return None

    value = match.group(1)

    value = value.replace(".", "")
    value = value.replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return None


def is_amazon_seller(seller_text):
    """
    Restituisce True solo quando il testo identifica
    esplicitamente Amazon come venditore.

    NON considera sufficiente:
    - Spedito da Amazon
    - Logistica di Amazon
    - Prime

    perché anche un venditore terzo può utilizzare
    la logistica Amazon.
    """

    text = " ".join(seller_text.split()).lower()

    amazon_patterns = [
        "venduto da amazon.it",
        "venditore amazon.it",
        "venduto da amazon",
        "venditore amazon",
    ]

    for pattern in amazon_patterns:
        if pattern in text:
            return True

    return False


async def check_amazon():
    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        context = await browser.new_context(
            locale="it-IT",
            timezone_id="Europe/Rome",
        )

        page = await context.new_page()

        try:
            print("=== AMAZON STOCK CHECK ===")
            print(f"ASIN: {ASIN}")

            # -------------------------------------------------
            # 1. IMPOSTA LOCALITÀ ITALIANA
            # -------------------------------------------------

            print("1. Impostazione località italiana...")

            location_ok = await set_delivery_location(page)

            if not location_ok:
                print(
                    "UNKNOWN: impossibile impostare la località"
                )

                return "UNKNOWN", None

            print(
                f"Località impostata: CAP {ZIP_CODE}"
            )

            # -------------------------------------------------
            # 2. APRE IL PRODOTTO
            # -------------------------------------------------

            print("2. Apertura prodotto...")

            offer_url = await get_offer_listing(page)

            if not offer_url:
                print(
                    "UNKNOWN: pagina prodotto/offerte "
                    "non disponibile"
                )

                return "UNKNOWN", None

            print("Offer listing URL trovata:")
            print(offer_url)

            # -------------------------------------------------
            # 3. APRE LA LISTA DELLE OFFERTE
            # -------------------------------------------------

            print("3. Apertura lista offerte...")

            await page.goto(
                offer_url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            await page.wait_for_timeout(4000)

            body = await page.locator("body").inner_text()

            # Pagina intermedia
            if (
                "Fai clic sul pulsante qui sotto "
                "per continuare"
            ) in body:
                print(
                    "UNKNOWN: pagina intermedia Amazon"
                )

                return "UNKNOWN", None

            # Verifica Amazon challenge senza tentare
            # alcun bypass
            if (
                "Robot Check" in body
                or "Inserisci i caratteri" in body
            ):
                print(
                    "UNKNOWN: Amazon ha richiesto "
                    "una verifica"
                )

                return "UNKNOWN", None

            # -------------------------------------------------
            # 4. LEGGE LE OFFERTE REALI
            # -------------------------------------------------

            offers = page.locator("div#aod-offer")

            count = await offers.count()

            print(
                f"Offerte reali trovate: {count}"
            )

            if count == 0:
                print(
                    "OUT_OF_STOCK: nessuna offerta"
                )

                return "OUT_OF_STOCK", None

            amazon_available = False
            amazon_price = None

            # -------------------------------------------------
            # 5. ANALIZZA OGNI OFFERTA
            # -------------------------------------------------

            for i in range(count):

                offer = offers.nth(i)

                if not await offer.is_visible():
                    continue

                text = " ".join(
                    (await offer.inner_text()).split()
                )

                price = extract_price(text)

                # Venditore
                seller_locator = offer.locator(
                    "#aod-offer-soldBy"
                )

                seller = ""

                if await seller_locator.count():

                    seller = " ".join(
                        (
                            await seller_locator
                            .first
                            .inner_text()
                        ).split()
                    )

                # Pulsante reale "Aggiungi al carrello"
                cart_button = offer.locator(
                    "span.aod-atc-generic-btn-desktop"
                )

                has_cart = False

                for j in range(
                    await cart_button.count()
                ):

                    button = cart_button.nth(j)

                    if await button.is_visible():
                        has_cart = True
                        break

                seller_is_amazon = is_amazon_seller(
                    seller
                )

                print(
                    f"OFFERTA {i + 1}: "
                    f"prezzo={price} "
                    f"venditore={seller!r} "
                    f"amazon={seller_is_amazon} "
                    f"carrello={has_cart}"
                )

                # -------------------------------------------------
                # SOLO AMAZON PUÒ PRODURRE AVAILABLE
                # -------------------------------------------------

                if seller_is_amazon and has_cart:

                    amazon_available = True

                    if price is not None:
                        amazon_price = price

                    print(
                        ">>> OFFERTA AMAZON "
                        "ACQUISTABILE <<<"
                    )

            # -------------------------------------------------
            # 6. RISULTATO
            # -------------------------------------------------

            if amazon_available:

                print(
                    "AVAILABLE: Amazon vende "
                    "direttamente il prodotto"
                )

                if amazon_price is not None:
                    print(
                        f"Prezzo Amazon: "
                        f"{amazon_price:.2f} EUR"
                    )

                return (
                    "AVAILABLE",
                    amazon_price,
                )

            # Ci sono eventualmente offerte di terzi,
            # ma nessuna offerta Amazon acquistabile.
            print(
                "OUT_OF_STOCK: nessuna offerta "
                "Amazon direttamente acquistabile"
            )

            return (
                "OUT_OF_STOCK",
                None,
            )

        except Exception as e:

            print(f"ERROR: {e}")

            return "ERROR", None

        finally:

            await browser.close()


if __name__ == "__main__":

    import asyncio

    status, price = asyncio.run(
        check_amazon()
    )

    print("========================================")
    print(f"STATUS: {status}")
    print(f"AMAZON PRICE: {price}")
    print("========================================")
