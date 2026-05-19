import sys
from playwright.sync_api import sync_playwright
from genericFormFiller import GenericFormFiller
from questionCache import QuestionCache
import debugLogger

URL = sys.argv[1] if len(sys.argv) > 1 else "https://jobs.ashbyhq.com/tradeify/443c4534-8152-4364-826a-6acb21d89367"

debugLogger.clear()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(URL)
    page.wait_for_load_state("networkidle")

    # click Apply button if present to reveal the form
    apply_btn = page.query_selector("button:has-text('Apply'), a:has-text('Apply')")
    if apply_btn:
        apply_btn.click()
        page.wait_for_load_state("networkidle")

    cache = QuestionCache()
    filler = GenericFormFiller(cache)
    filler.fill_page(page)

    debugLogger.flush()
    input("\nDone — inspect the page, then press Enter to close.")
    browser.close()
