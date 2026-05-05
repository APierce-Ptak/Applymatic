import json
import os
import csv
import platform
import subprocess
from playwright.sync_api import sync_playwright
import loginClass
import toolbox
import applyClass

CRED_FILE = "cred.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

BROWSER_PATHS = {
    "Chrome": {
        "Windows": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "Darwin":  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "Linux":   "/usr/bin/google-chrome",
    },
    "Edge": {
        "Windows": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "Darwin":  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "Linux":   "/usr/bin/microsoft-edge",
    },
}

def load_creds():
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, "r") as f:
            return json.load(f)
    return {"email": "", "password": ""}

def save_creds(email, password):
    with open(CRED_FILE, "w") as f:
        json.dump({"email": email, "password": password}, f)

def launch_browser_with_debugging(browser_type, cdp_port):
    system = platform.system()
    exe = BROWSER_PATHS.get(browser_type, {}).get(system)
    if not exe or not os.path.exists(exe):
        return False, f"{browser_type} not found at expected path for {system}"
    try:
        subprocess.Popen([
            exe,
            f"--remote-debugging-port={cdp_port}",
            "--no-first-run",
            "--no-default-browser-check",
        ])
        return True, f"{browser_type} launched with debugging on port {cdp_port}"
    except Exception as e:
        return False, f"Failed to launch {browser_type}: {e}"

def get_browser_page(p, browser_mode, cdp_port, email, password):
    if browser_mode == "existing":
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
            return browser, page, False
        except Exception as e:
            print(f"CDP connection failed: {e}")
            return None, None, False
    else:
        browser = p.chromium.launch(headless=False)
        success, page = loginClass.Login().loginTo(
            url="https://www.linkedin.com/login",
            username=email,
            password=password,
            browser=browser,
        )
        if not success:
            browser.close()
            return None, None, True
        return browser, page, True

def scrape(page, keyword, distance, geo_id, easy_apply, date_filter, pages):
    all_jobs = []
    seen_ids = set()

    for page_num in range(pages):
        url = toolbox.build_search_url(
            keyword=keyword, distance=distance,
            geo_id=geo_id, easy_apply=easy_apply,
            date_filter=date_filter, start=page_num * 25
        )
        page.goto(url)
        page.wait_for_load_state("load")
        toolbox.scroll_job_list(page)

        jobs = toolbox.scrape_job_cards(page)
        for job in jobs:
            if job["job_id"] not in seen_ids:
                seen_ids.add(job["job_id"])
                all_jobs.append(job)

        print(f"Page {page_num + 1} scraped — {len(all_jobs)} total unique")

    toolbox.save_jobs_to_csv(all_jobs)
    return all_jobs, None

def apply(page, jobs, follow_companies, requires_sponsorship, max_applications=50):
    applier = applyClass.AutoApply(
        follow_companies=follow_companies,
        requires_sponsorship=requires_sponsorship
    )
    return applier.apply_batch(page, jobs[:max_applications])

def load_jobs_from_csv():
    jobs = []
    if os.path.exists("jobs.csv"):
        with open("jobs.csv", "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                jobs.append(row)
    return jobs

def _finish(browser, should_close):
    if should_close:
        browser.close()
    else:
        browser.disconnect()

def run_scrape_only(email, password, keyword, distance, geo_id, easy_apply, date_filter, pages,
                    browser_mode, browser_type, cdp_port):
    with sync_playwright() as p:
        browser, page, should_close = get_browser_page(p, browser_mode, cdp_port, email, password)
        if browser is None:
            return None, f"Could not connect to {browser_type}. Make sure it was launched with debugging enabled and you are logged into LinkedIn."
        all_jobs, error = scrape(page, keyword, distance, geo_id, easy_apply, date_filter, pages)
        _finish(browser, should_close)
    return all_jobs, error

def run_scrape_and_apply(email, password, keyword, distance, geo_id, easy_apply, date_filter, pages,
                         follow_companies, requires_sponsorship, max_applications,
                         browser_mode, browser_type, cdp_port):
    with sync_playwright() as p:
        browser, page, should_close = get_browser_page(p, browser_mode, cdp_port, email, password)
        if browser is None:
            return None, f"Could not connect to {browser_type}. Make sure it was launched with debugging enabled and you are logged into LinkedIn."
        all_jobs, error = scrape(page, keyword, distance, geo_id, easy_apply, date_filter, pages)
        if error:
            _finish(browser, should_close)
            return None, error
        jobs = load_jobs_from_csv()
        if jobs:
            apply(page, jobs, follow_companies, requires_sponsorship, max_applications)
        _finish(browser, should_close)
    return all_jobs, None

def run_apply_from_csv(email, password, follow_companies, requires_sponsorship, max_applications,
                       browser_mode, browser_type, cdp_port):
    jobs = load_jobs_from_csv()
    if not jobs:
        return None, "No jobs found in jobs.csv"
    with sync_playwright() as p:
        browser, page, should_close = get_browser_page(p, browser_mode, cdp_port, email, password)
        if browser is None:
            return None, f"Could not connect to {browser_type}. Make sure it was launched with debugging enabled and you are logged into LinkedIn."
        results = apply(page, jobs, follow_companies, requires_sponsorship, max_applications)
        _finish(browser, should_close)
    return results, None


# entry point
from ui import render
render(run_scrape_only, run_scrape_and_apply, run_apply_from_csv, load_creds, save_creds, launch_browser_with_debugging)
