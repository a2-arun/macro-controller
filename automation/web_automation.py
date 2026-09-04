"""Browser automation for credential autofill.

Two defects are fixed here.

*The deadlock.* The original called input("Press Enter to close browser...")
inside a GUI application built with console=False. There is no stdin in the
packaged build, so that call blocked forever holding the driver open.

*The credential disclosure.* The original navigated to a URL, then typed the
password into whatever password field it found, with no check that the page it
landed on is the page it aimed at. A redirect, a typosquatted entry in
macros.json, or DNS interference sent the credential to an attacker.

The origin check below is a *policy* check -- a branch, which is better than
nothing but can be bypassed by anyone who can edit this file. Phase 2 replaces
it with a cryptographic guarantee: the origin becomes AEAD associated data, so
a record for one origin cannot be decrypted for another. See docs/ROADMAP.md
Part 3.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

PAGE_LOAD_TIMEOUT = 20
ELEMENT_TIMEOUT = 10


class OriginMismatch(RuntimeError):
    """The page reached is not the page the credential was stored for."""


def canonical_origin(url: str) -> str:
    """Reduce a URL to scheme://host[:port], lowercased.

    This is the value bound to a credential record. Getting canonicalisation
    right matters: it is the whole basis of the origin check, and later of the
    AEAD associated data.
    """
    parsed = urlparse(url if "://" in url else f"https://{url}")
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower().rstrip(".")

    # IDN homograph defence: compare punycode, not display form.
    try:
        host = host.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        pass

    port = parsed.port
    default_port = {"http": 80, "https": 443}.get(scheme)
    if port and port != default_port:
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


def handle_web_action(
    url: str,
    credentials: dict,
    on_error: Optional[callable] = None,
) -> None:
    """Open `url` and fill stored credentials, refusing on origin mismatch."""
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    expected = canonical_origin(url)
    driver = None

    try:
        options = webdriver.ChromeOptions()
        options.add_experimental_option("detach", True)  # survive driver.quit()
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        driver.get(url)

        # Verify *after* navigation, so redirects are caught.
        actual = canonical_origin(driver.current_url)
        if actual != expected:
            raise OriginMismatch(
                f"Refusing to fill credentials: expected {expected}, "
                f"landed on {actual}"
            )

        wait = WebDriverWait(driver, ELEMENT_TIMEOUT)
        username_field = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='text'], input[type='email']")
            )
        )
        username_field.clear()
        username_field.send_keys(credentials["username"])

        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")

        # Re-check immediately before releasing the secret. A page can navigate
        # between the first check and this point.
        if canonical_origin(driver.current_url) != expected:
            raise OriginMismatch("Origin changed while filling the form")

        password_field.clear()
        password_field.send_keys(credentials["password"])
        password_field.submit()

        logger.info("autofill submitted for %s", expected)

    except OriginMismatch:
        logger.error("origin mismatch for %s", url)
        # Close the browser rather than leave the user on a hostile page with
        # a half-filled form.
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
            driver = None
        raise

    except Exception as exc:
        logger.exception("autofill failed for %s", url)
        if on_error is not None:
            on_error(f"Login automation failed: {exc}")

    finally:
        # The browser stays open for the user (detach=True). Only release the
        # driver handle. No input() call, so nothing blocks.
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                logger.debug("driver already gone", exc_info=True)
