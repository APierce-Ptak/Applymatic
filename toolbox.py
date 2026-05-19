from urllib.parse import urlencode
import csv
import os
import json
import random
import sqlite3
import time
import requests
from datetime import datetime
import debugLogger

DB_FILE = "jobs.db"


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
        debugLogger.log(f"Location cache hit: {city} → {cached['display']}")
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
        debugLogger.log(f"Geo ID lookup failed: {e}")
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
            debugLogger.log(f"Error parsing card: {e}")
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


def init_db(filename=DB_FILE):
    is_new = not os.path.exists(filename)
    conn = sqlite3.connect(filename)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id     TEXT PRIMARY KEY,
            title      TEXT,
            company    TEXT,
            location   TEXT,
            salary     TEXT,
            easy_apply INTEGER DEFAULT 0,
            url        TEXT,
            scraped_at TEXT,
            applied    TEXT DEFAULT ''
        )
    """)
    conn.commit()
    if is_new:
        _migrate_csv_to_db(conn)
    conn.close()


def _migrate_csv_to_db(conn):
    if not os.path.exists("jobs.csv"):
        return
    try:
        with open("jobs.csv", "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO jobs
                    (job_id, title, company, location, salary, easy_apply, url, scraped_at, applied)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get("job_id", ""),
                    row.get("title", ""),
                    row.get("company", ""),
                    row.get("location", ""),
                    row.get("salary", ""),
                    1 if str(row.get("easy_apply", "")).lower() in ("true", "1", "yes") else 0,
                    row.get("url", ""),
                    row.get("scraped_at", ""),
                    row.get("applied", ""),
                ))
            except Exception:
                pass
        conn.commit()
        debugLogger.log(f"Migrated {len(rows)} jobs from jobs.csv → jobs.db")
    except Exception as e:
        debugLogger.log(f"CSV migration failed: {e}")


def save_jobs_to_db(jobs, filename=DB_FILE):
    init_db(filename)
    conn = sqlite3.connect(filename)
    new_count = 0
    for job in jobs:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO jobs
                (job_id, title, company, location, salary, easy_apply, url, scraped_at, applied)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '')
            """, (
                job.get("job_id", ""),
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("salary", ""),
                1 if str(job.get("easy_apply", "")).lower() in ("true", "1", "yes") else 0,
                job.get("url", ""),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            if conn.execute("SELECT changes()").fetchone()[0]:
                new_count += 1
        except Exception as e:
            debugLogger.log(f"DB insert error: {e}")
    conn.commit()
    conn.close()
    debugLogger.log(f"Saved {new_count} new jobs to jobs.db")
    return new_count


def update_job_outcome(url, value, filename=DB_FILE):
    if not url:
        return
    try:
        init_db(filename)
        conn = sqlite3.connect(filename)
        conn.execute("UPDATE jobs SET applied = ? WHERE url = ?", (str(value), url))
        conn.commit()
        conn.close()
    except Exception as e:
        debugLogger.log(f"Could not update outcome: {e}")


def load_jobs_from_db(filename=DB_FILE):
    init_db(filename)
    try:
        conn = sqlite3.connect(filename)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM jobs WHERE applied NOT IN ('1', 'external')").fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        debugLogger.log(f"DB load error: {e}")
        return []


def get_job_count(filename=DB_FILE):
    init_db(filename)
    try:
        conn = sqlite3.connect(filename)
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def get_unapplied_count(filename=DB_FILE):
    init_db(filename)
    try:
        conn = sqlite3.connect(filename)
        count = conn.execute("SELECT COUNT(*) FROM jobs WHERE applied = ''").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def get_failed_count(filename=DB_FILE):
    init_db(filename)
    try:
        conn = sqlite3.connect(filename)
        count = conn.execute("SELECT COUNT(*) FROM jobs WHERE applied = '0'").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def get_all_jobs_for_table(filename=DB_FILE):
    init_db(filename)
    try:
        conn = sqlite3.connect(filename)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM jobs ORDER BY scraped_at DESC").fetchall()
        conn.close()
        return [{
            "Title":    row["title"],
            "Company":  row["company"],
            "Location": row["location"],
            "Type":     "Easy Apply" if row["easy_apply"] else "External",
        } for row in rows]
    except Exception as e:
        debugLogger.log(f"DB table read error: {e}")
        return []


def get_applied_labels(filename=DB_FILE):
    init_db(filename)
    try:
        conn = sqlite3.connect(filename)
        rows = conn.execute("SELECT title, company FROM jobs WHERE applied = '1'").fetchall()
        conn.close()
        return {f"{r[0]} at {r[1]}".lower() for r in rows}
    except Exception:
        return set()


def get_recent_jobs(limit=8, filename=DB_FILE):
    init_db(filename)
    try:
        conn = sqlite3.connect(filename)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY scraped_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception:
        return []