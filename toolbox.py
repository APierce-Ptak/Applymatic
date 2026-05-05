from urllib.parse import urlencode
import csv
import os
import json
import random
import time
import requests
from datetime import datetime


def human_delay(min_ms=500, max_ms=2000):
    time.sleep(random.randint(min_ms, max_ms) / 1000)

BASE_URL = "https://www.linkedin.com"
LOCATIONS_FILE = "locations.json"


def load_locations():
    if os.path.exists(LOCATIONS_FILE):
        with open(LOCATIONS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_location(city, geo_id, display_name):
    locations = load_locations()
    locations[city.lower().strip()] = {"id": geo_id, "display": display_name}
    with open(LOCATIONS_FILE, "w") as f:
        json.dump(locations, f, indent=2)


def get_geo_id(city: str):
    """
    Looks up a LinkedIn geo ID for a given city string.
    Checks local cache first, falls back to LinkedIn's typeahead API.
    Returns (geo_id, display_name) or (None, None) if not found.
    """
    # check cache first
    locations = load_locations()
    key = city.lower().strip()
    if key in locations:
        cached = locations[key]
        print(f"Location cache hit: {city} → {cached['display']}")
        return cached["id"], cached["display"]

    # fall back to LinkedIn typeahead API
    try:
        url = "https://www.linkedin.com/jobs-guest/api/typeaheadHits"
        params = {"query": city, "type": "GEO"}
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()

        if data and len(data) > 0:
            top = data[0]
            save_location(city, top["id"], top["displayName"])
            return top["id"], top["displayName"]
        return None, None
    except Exception as e:
        print(f"Geo ID lookup failed: {e}")
        return None, None


def build_search_url(keyword, distance, geo_id, start=0, easy_apply=True, date_filter=None):
    """
    Build LinkedIn job search URL with pagination offset.
    """
    params = {
        "keywords": keyword,
        "origin": "JOB_SEARCH_PAGE_JOB_FILTER",
        "distance": distance,
        "geoId": geo_id,
        "start": start
    }

    if easy_apply:
        params["f_AL"] = "true"

    if date_filter:
        params["f_TPR"] = date_filter

    return f"{BASE_URL}/jobs/search/?{urlencode(params)}"


def scrape_job_cards(page):
    """
    Scrapes job cards from the current LinkedIn jobs search results page.
    """
    seen_ids = set()
    jobs = []

    page.wait_for_selector("div.job-card-container", timeout=10000)
    cards = page.query_selector_all("div.job-card-container")

    for card in cards:
        try:
            job_id = card.get_attribute("data-job-id")
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title_el = card.query_selector("a.job-card-list__title--link")
            title = title_el.inner_text().strip() if title_el else "N/A"

            company_el = card.query_selector("div.artdeco-entity-lockup__subtitle span")
            company = company_el.inner_text().strip() if company_el else "N/A"

            location_el = card.query_selector("div.artdeco-entity-lockup__caption li span")
            location = location_el.inner_text().strip() if location_el else "N/A"

            salary_el = card.query_selector("div.artdeco-entity-lockup__metadata li span")
            salary = salary_el.inner_text().strip() if salary_el else "N/A"

            easy_apply = card.query_selector("li span:has-text('Easy Apply')") is not None

            link_el = card.query_selector("a.job-card-list__title--link")
            href = link_el.get_attribute("href") if link_el else ""
            job_url = f"https://www.linkedin.com{href}" if href else "N/A"

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "easy_apply": easy_apply,
                "url": job_url
            })

        except Exception as e:
            print(f"Error parsing card: {e}")
            continue

    return jobs


def scroll_job_list(page):
    page.wait_for_selector(".scaffold-layout__list-item", timeout=10000)

    for _ in range(6):
        page.evaluate("""
            () => {
                const item = document.querySelector('[data-occludable-job-id]');
                if (!item) return;
                let el = item.parentElement;
                while (el) {
                    if (el.scrollHeight > el.clientHeight) {
                        el.scrollTop += 600;
                        break;
                    }
                    el = el.parentElement;
                }
            }
        """)
        human_delay(800, 1800)


def save_jobs_to_csv(jobs, filename="jobs.csv"):
    """
    Saves job results to a CSV file, appending new jobs and skipping duplicates by job_id.
    Always ensures header row exists.
    """
    fieldnames = ["job_id", "title", "company", "location", "salary", "easy_apply", "url", "scraped_at"]

    existing_ids = set()
    file_exists = os.path.exists(filename)

    # treat empty file same as no file
    if file_exists and os.path.getsize(filename) == 0:
        file_exists = False

    if file_exists:
        with open(filename, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_ids.add(row["job_id"])

    new_jobs = [j for j in jobs if j["job_id"] not in existing_ids]

    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for job in new_jobs:
            job["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow(job)

    print(f"Saved {len(new_jobs)} new jobs to {filename} ({len(existing_ids)} already existed)")
    return len(new_jobs)