# Applymatic — Automate Your Job Applications

**[🌐 Live Page](https://apierce-ptak.github.io/Applymatic/)**

Applymatic is a **Python job application automation** tool that scrapes job listings and automatically submits applications on your behalf. Built with Playwright and Streamlit, it currently supports **LinkedIn Easy Apply** — handling multi-page forms, caching answers, and matching your profile to form fields so you never type the same answer twice. If you've been looking for a **Playwright LinkedIn scraper** or a reliable way to **automate job applications** at scale, Applymatic is built for that, with more platforms on the way. It runs cross-platform across Windows, Mac, and Linux.

---

## What Applymatic Does

- **Scrapes job listings** — currently supports LinkedIn; searches by keyword, location, distance, date posted, and Easy Apply filter
- **Auto-fills and submits Easy Apply forms** — handles text inputs, dropdowns, radio buttons, location autocomplete, and multi-page applications
- **Caches your answers** — saves responses to `questions.json` so repeated questions are answered automatically
- **Matches your profile** — maps `profile.json` fields (name, phone, salary, work authorization, years of experience by technology) directly to form fields
- **Three operating modes:**
  - **Scrape only** — find and save jobs to CSV without applying
  - **Scrape and apply** — search then immediately apply in one run
  - **Apply from CSV** — apply to a saved list of jobs at any time

---

## Bot Detection Avoidance

Applymatic supports two browser connection modes to reduce the chance of platforms flagging your activity:

- **Connect to existing browser** (recommended) — attach to an already logged-in Chrome or Edge instance via Chrome DevTools Protocol (CDP). LinkedIn sees your normal browser profile, cookies, and session history.
- **Launch new Chromium instance** — Playwright launches a fresh browser with a realistic user agent. Sessions are saved to `session.json` after first login so subsequent runs skip the login step.

---

## Setup

> **Requirements:** Python 3.8+ installed on your machine.

**1. Clone the repo:**
```bash
git clone https://github.com/yourusername/applymatic.git
cd applymatic
```

**2. Create and activate a virtual environment:**

Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

Mac / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Install the Chromium browser:**
```bash
playwright install chromium
```

**5. Run the app:**
```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`

---

## How to Automate Job Applications

### Set Up Your Profile

On first run, Applymatic automatically creates a `profile.json` file in the project folder. Open it and fill in your details — this is what gets mapped to application form fields:

```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "email": "jane@example.com",
  "phone": "5551234567",
  "phone_country_code": "1",
  "location": "New York, NY",
  "linkedin": "https://linkedin.com/in/janedoe",
  "desired_salary": "100000",
  "work_authorization": "Yes",
  "requires_sponsorship": "No",
  "notice_period": "2 weeks",
  "gender": "Prefer not to say",
  "veteran_status": "No",
  "disability_status": "No",
  "years_experience_default": "2",
  "years_experience_technologies": {
    "python": "3",
    "javascript": "2"
  },
  "default_answer": "No"
}
```

### Find Your Geo ID

LinkedIn uses a numeric Geo ID to identify locations. To find yours:

1. Go to [linkedin.com/jobs](https://www.linkedin.com/jobs)
2. Type your city in the **Location** bar and select it
3. Copy the number after `geoId=` in the URL

**Example:**
```
https://www.linkedin.com/jobs/search/?geoId=90000070
```
→ Geo ID for New York City is `90000070`

Paste this into the **Geo ID** field in the app's Search Parameters section.

---

## Project Structure

```
applymatic/
├── app.py            # Core logic, browser management, Playwright orchestration
├── ui.py             # Streamlit UI
├── applyClass.py     # Batch apply logic with stall detection
├── formFiller.py     # Form detection and field filling
├── loginClass.py     # Login handler with session persistence
├── questionCache.py  # Caches Q&A and manages profile.json
├── toolbox.py        # URL builder, scraper, CSV utilities, human delay
└── requirements.txt  # Python dependencies
```

---

## Security Notes

The following files are in `.gitignore` and are **never committed to the repo:**

| File | Contents |
|---|---|
| `cred.json` | Login credentials |
| `profile.json` | Your personal info |
| `jobs.csv` | Scraped job listings |
| `questions.json` | Cached application answers |
| `locations.json` | Geo ID cache |
| `session.json` | Saved browser session |

---

## Tech Stack

- [Python 3](https://python.org)
- [Streamlit](https://streamlit.io)
- [Playwright for Python](https://playwright.dev/python/)

---

## ⚠️ Disclaimer

This tool interacts with LinkedIn in ways that may violate their [Terms of Service](https://www.linkedin.com/legal/user-agreement). Your account could be restricted or banned. Use at your own risk. The author is not responsible for any consequences resulting from its use.

---

## GitHub Topics

`linkedin-automation` `job-search` `playwright` `python` `streamlit` `easy-apply` `job-bot` `career-automation` `linkedin-scraper` `job-application-bot`
