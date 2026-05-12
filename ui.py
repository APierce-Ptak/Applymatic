import os
import sys
import csv
import json
from dataclasses import dataclass
import streamlit as st

DEMO_MODE     = "--demo"  in sys.argv
FRESH_INSTALL = "--fresh" in sys.argv

# ── Demo fixtures (used when DEMO_MODE=1) ─────────────────────────────────────
_DEMO_JOBS = [
    {"Title": "Software Engineer II",        "Company": "Stripe",       "Location": "Seattle, WA", "Type": "Easy Apply"},
    {"Title": "Senior Backend Engineer",      "Company": "Vercel",       "Location": "Remote",      "Type": "Easy Apply"},
    {"Title": "Platform Engineer",            "Company": "Cloudflare",   "Location": "Austin, TX",  "Type": "Easy Apply"},
    {"Title": "Full Stack Engineer",          "Company": "Linear",       "Location": "Remote",      "Type": "Easy Apply"},
    {"Title": "Staff Software Engineer",      "Company": "Figma",        "Location": "San Francisco, CA", "Type": "Easy Apply"},
    {"Title": "ML Infrastructure Engineer",   "Company": "Anthropic",    "Location": "Remote",      "Type": "Easy Apply"},
    {"Title": "Frontend Engineer",            "Company": "Notion",       "Location": "New York, NY","Type": "Easy Apply"},
    {"Title": "DevOps Engineer",              "Company": "HashiCorp",    "Location": "Remote",      "Type": "Easy Apply"},
]
_DEMO_APPLIED = {
    "software engineer ii at stripe",
    "senior backend engineer at vercel",
    "platform engineer at cloudflare",
}
_DEMO_METRICS = {
    "scraped":      247,
    "applied":       61,
    "in_queue":      38,
    "success_rate": "74%",
    "last_run":     "2 hours ago",
}


@dataclass
class JobCard:
    title:    str
    company:  str
    status:   str        # "applied" | "skipped" | "failed" | "scraped"
    time:     str
    location: str = ""
    url:      str = ""
    salary:   str = ""
    easy_apply: bool = False

    @property
    def label(self) -> str:
        return f"{self.title} at {self.company}"

    @property
    def dot_color(self) -> str:
        return {
            "applied": "#22c55e",
            "skipped": "#eab308",
            "failed":  "#ef4444",
            "scraped": "#60a5fa",
        }.get(self.status, "#aaa")

    @classmethod
    def from_debug(cls, label: str, status: str, time: str) -> "JobCard":
        parts   = label.rsplit(" at ", 1)
        title   = parts[0] if len(parts) == 2 else label
        company = parts[1] if len(parts) == 2 else ""
        return cls(title=title, company=company, status=status, time=time)

    @classmethod
    def from_csv_row(cls, row: dict, time: str = "") -> "JobCard":
        return cls(
            title      = row.get("title",    "?"),
            company    = row.get("company",  "?"),
            status     = "scraped",
            time       = time or row.get("scraped_at", "")[:10],
            location   = row.get("location", ""),
            url        = row.get("url",      ""),
            salary     = row.get("salary",   ""),
            easy_apply = str(row.get("easy_apply", "")).lower() in ("true", "1", "yes"),
        )

_CONFIG_FILE = "config.json"

def _load_config():
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_config(updates):
    cfg = _load_config()
    cfg.update(updates)
    with open(_CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

EASY_APPLY_BASE_TIME = 2  # minutes saved per application

@st.dialog("Welcome to Applymatic")
def _first_run_guide():
    st.markdown("""
**Before you start, you'll need a Geo ID** — a number LinkedIn uses to identify your target location.

**How to find it:**
1. Go to **linkedin.com/jobs** in your browser
2. Type your city in the **Location** search bar and select it from the dropdown
3. Look at the URL and copy the number after `geoId=`

**Example URL:**
```
https://www.linkedin.com/jobs/search/?geoId=90000070&keywords=...
```
Geo ID is `90000070` *(New York City)*

Paste it into the **Geo ID** field inside the Advanced expander.
    """)
    if st.button("Got it", type="primary", key="first_run_ack"):
        st.session_state.dismissed_guide = True
        st.rerun()

def _csv_job_count():
    if DEMO_MODE:
        return _DEMO_METRICS["scraped"]
    if FRESH_INSTALL:
        return 0
    if not os.path.exists("jobs.csv"):
        return 0
    try:
        with open("jobs.csv", "r", newline="", encoding="utf-8") as f:
            return sum(1 for _ in csv.DictReader(f))
    except Exception:
        return 0

def _load_jobs_for_table():
    if DEMO_MODE:
        return list(_DEMO_JOBS)
    if FRESH_INSTALL:
        return []
    if os.path.exists("jobs.csv"):
        try:
            rows = []
            with open("jobs.csv", "r", newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    rows.append({
                        "Title":    row.get("title", ""),
                        "Company":  row.get("company", ""),
                        "Location": row.get("location", ""),
                        "Type":     "Easy Apply" if str(row.get("easy_apply", "")).lower() in ("true", "1", "yes") else "External",
                    })
            if rows:
                return rows
        except Exception:
            pass
    return []

def _get_last_run() -> str:
    if FRESH_INSTALL:
        return ""
    if not os.path.exists("debug.json"):
        return ""
    try:
        from datetime import datetime
        with open("debug.json", "r", encoding="utf-8") as f:
            log = json.load(f).get("log", [])
        if not log:
            return ""
        dt = datetime.fromisoformat(log[0]["ts"])
        m  = int((datetime.now() - dt).total_seconds() // 60)
        if m < 60:   return f"{m}m ago"
        if m < 1440: return f"{m // 60}h ago"
        return f"{m // 1440}d ago"
    except Exception:
        return ""

def _load_applied_set() -> set:
    if DEMO_MODE:
        return set(_DEMO_APPLIED)
    if FRESH_INSTALL:
        return set()
    if os.path.exists("applied.json"):
        try:
            with open("applied.json", "r", encoding="utf-8") as f:
                return {e["label"].lower() for e in json.load(f)}
        except Exception:
            pass
    return set()

def _load_recent_activity(limit=8):
    """
    Pull activity from two sources:
    1. debug.json — applied/skipped/failed outcomes from the last run (color-coded)
    2. jobs.csv   — recently scraped jobs not already in debug results (blue, scraped-only)
    """
    from datetime import datetime

    def _fmt_time(ts):
        try:
            dt = datetime.fromisoformat(ts)
            m  = int((datetime.now() - dt).total_seconds() // 60)
            if m < 60:   return f"{m}m ago"
            if m < 1440: return f"{m // 60}h ago"
            return f"{m // 1440}d ago"
        except Exception:
            return ts[:10] if ts else ""

    cards: list[JobCard] = []
    seen  = set()

    if FRESH_INSTALL:
        return []

    if DEMO_MODE:
        demo_activity = [
            JobCard("Software Engineer II",      "Stripe",     "applied", "3h ago",  location="Seattle, WA", easy_apply=True),
            JobCard("Senior Backend Engineer",    "Vercel",     "applied", "3h ago",  location="Remote",      easy_apply=True),
            JobCard("Platform Engineer",          "Cloudflare", "applied", "3h ago",  location="Austin, TX",  easy_apply=True),
            JobCard("Full Stack Engineer",        "Linear",     "skipped", "3h ago",  location="Remote",      easy_apply=True),
            JobCard("Staff Software Engineer",    "Figma",      "failed",  "1d ago",  location="San Francisco, CA", easy_apply=True),
            JobCard("ML Infrastructure Engineer", "Anthropic",  "scraped", "2d ago",  location="Remote",      easy_apply=True),
            JobCard("Frontend Engineer",          "Notion",     "scraped", "2d ago",  location="New York, NY",easy_apply=True),
            JobCard("DevOps Engineer",            "HashiCorp",  "scraped", "3d ago",  location="Remote",      easy_apply=True),
        ]
        return demo_activity[:limit]

    if os.path.exists("debug.json"):
        try:
            with open("debug.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            summary    = data.get("summary", {}).get("jobs", {})
            log        = data.get("log", [])
            time_label = _fmt_time(log[0]["ts"]) if log else ""
            for status in ("applied", "skipped", "failed"):
                for label in summary.get(status, []):
                    cards.append(JobCard.from_debug(label, status, time_label))
                    seen.add(label.lower())
        except Exception:
            pass

    if len(cards) < limit and os.path.exists("jobs.csv"):
        try:
            with open("jobs.csv", "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            for row in rows[-limit:][::-1]:
                card = JobCard.from_csv_row(row)
                if card.label.lower() not in seen:
                    cards.append(card)
                    seen.add(card.label.lower())
                if len(cards) >= limit:
                    break
        except Exception:
            pass

    return cards[:limit]

def _render_job_card(card: JobCard):
    """Self-contained job card: invisible at rest, highlighted on hover, expands on click."""
    badge_bg    = card.dot_color + "22"
    status_icon = {"applied": "✓", "skipped": "–", "failed": "✗", "scraped": "·"}.get(card.status, "·")
    label       = f"{status_icon}  {card.title}  ·  {card.company}"

    with st.expander(label, expanded=False):
        top, badge_col = st.columns([3, 1])
        with top:
            if card.location:
                st.caption(card.location)
            if card.salary and card.salary not in ("", "N/A"):
                st.caption(card.salary)
            if card.time:
                st.caption(card.time)
        with badge_col:
            st.markdown(
                f'<div style="text-align:right;">'
                f'<span style="font-size:11px; background:{badge_bg}; color:{card.dot_color}; '
                f'padding:2px 9px; border-radius:4px; font-weight:500;">{card.status}</span></div>',
                unsafe_allow_html=True,
            )
        if card.url and card.url not in ("", "N/A"):
            st.markdown(f"[View on LinkedIn →]({card.url})")

def render(run_scrape_only, run_scrape_and_apply, run_apply_from_csv, load_creds, save_creds, launch_browser_with_debugging):

    st.set_page_config(page_title="Applymatic", layout="wide")

    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

h1, h2, h3 {
    font-weight: 500;
    letter-spacing: -0.02em;
}

.stButton > button {
    border-radius: 6px;
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
}

.stButton > button[kind="primary"] {
    background-color: #2563eb;
    border: none;
    color: white;
    font-weight: 500;
}

.stButton > button[kind="primary"]:hover {
    background-color: #1d4ed8;
}

div[data-testid="stExpander"] {
    border: 1px solid transparent;
    border-radius: 8px;
    transition: border-color 0.18s ease, box-shadow 0.18s ease;
    margin-bottom: 2px;
}

div[data-testid="stExpander"]:hover {
    border-color: rgba(37, 99, 235, 0.25);
    box-shadow: 0 2px 12px rgba(37, 99, 235, 0.08);
}

.stTextInput > div > div > input {
    border-radius: 6px;
    font-size: 13px;
}

.stSelectbox > div > div {
    border-radius: 6px;
    font-size: 13px;
}

hr {
    opacity: 0.15;
}
</style>
""", unsafe_allow_html=True)

    # ── Session state ──────────────────────────────────────────────────
    for key, default in [
        ("last_result", None),
        ("last_error",  None),
        ("last_mode",   None),
        ("job_filter",  "all"),
        ("dismissed_guide", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── First-run guide ────────────────────────────────────────────────
    profile_name = ""
    if os.path.exists("profile.json"):
        try:
            with open("profile.json") as f:
                profile_name = json.load(f).get("first_name", "")
        except Exception:
            pass
    if profile_name in ("NewUser", "") and not st.session_state.dismissed_guide:
        _first_run_guide()

    # ── Header ─────────────────────────────────────────────────────────
    col_logo, col_status = st.columns([3, 1])
    with col_logo:
        demo_badge  = '<div style="font-size:11px; background:#fef9c3; color:#854d0e; padding:2px 8px; border-radius:4px; font-weight:500;">Demo</div>'         if DEMO_MODE     else ""
        fresh_badge = '<div style="font-size:11px; background:#e0f2fe; color:#075985; padding:2px 8px; border-radius:4px; font-weight:500;">Fresh Install</div>' if FRESH_INSTALL else ""
        st.markdown(f"""
<div style="display:flex; align-items:center; gap:10px; padding:0.5rem 0 1.5rem 0;">
    <div style="font-size:22px; font-weight:500; letter-spacing:-0.02em;">⚡ Applymatic</div>
    <div style="font-size:11px; background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:4px; font-weight:500;">Beta</div>
    {demo_badge}{fresh_badge}
</div>
""", unsafe_allow_html=True)
    with col_status:
        last_run_label = _DEMO_METRICS["last_run"] if DEMO_MODE else _get_last_run()
        st.markdown(f"""
<div style="text-align:right; padding-top:1rem; font-size:12px; color:#888;">{"Last run: " + last_run_label if last_run_label else "No runs yet"}</div>
""", unsafe_allow_html=True)

    # ── Metrics ────────────────────────────────────────────────────────
    csv_count     = _csv_job_count()
    applied_count = _DEMO_METRICS["applied"] if DEMO_MODE else len(_load_applied_set())
    minutes_saved = applied_count * EASY_APPLY_BASE_TIME
    time_saved_str = (
        f"{minutes_saved // 60}h {minutes_saved % 60}m" if minutes_saved >= 60
        else f"{minutes_saved}m" if minutes_saved > 0
        else "—"
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Jobs scraped", str(csv_count) if (DEMO_MODE or csv_count) else "—")
    with m2:
        st.metric("Applied", str(applied_count) if (DEMO_MODE or applied_count) else "—")
    with m3:
        st.metric("Time saved", time_saved_str)
    with m4:
        st.metric("Success rate", _DEMO_METRICS["success_rate"] if DEMO_MODE else "—")
    with m5:
        st.metric("In queue", str(_DEMO_METRICS["in_queue"]) if DEMO_MODE else (str(csv_count) if csv_count else "—"))

    st.divider()

    # ── Safe defaults (overridden by widgets below) ────────────────────
    email            = ""
    password         = ""
    browser_type     = None
    cdp_port         = 9222
    browser_mode     = "Launch new Chromium instance (safer)"
    follow_companies    = False
    requires_sponsorship = False
    max_applications = 10

    # ── Two-column layout ──────────────────────────────────────────────
    col_left, col_right = st.columns([1.4, 1])

    # ════ LEFT — Quick Run ════════════════════════════════════════════
    with col_left:
        st.markdown("**Quick Run**")

        keyword = st.text_input("Job title", value="Software Engineer", key="keyword_input")

        loc_col, date_col = st.columns(2)
        with loc_col:
            location_text = st.text_input("Location", value="Seattle, WA", key="location_input")
        with date_col:
            date_filter = st.selectbox("Date posted", options=[
                ("Past 24 hours", "r86400"),
                ("Past week",     "r604800"),
                ("Past month",    "r2592000"),
                ("Past 12 hours", "r43200"),
                ("Past 6 hours",  "r21600"),
                ("Past 1 hour",   "r3600"),
                ("Any time",      None),
            ], format_func=lambda x: x[0], key="date_filter_select")

        tog1, tog2 = st.columns(2)
        with tog1:
            easy_apply = st.toggle("Easy Apply only", value=True, key="easy_apply_toggle")
        with tog2:
            auto_apply = st.toggle("Auto apply", value=False, key="auto_apply_toggle")

        distance = st.slider("Distance (miles)", min_value=5, max_value=100, value=50, step=5, key="distance_slider")
        pages    = st.slider("Pages to scrape",  min_value=1, max_value=10,  value=3,  step=1, key="pages_slider")

        # Advanced — Geo ID + location lookup
        with st.expander("Advanced"):
            geo_id = st.number_input(
                "Geo ID",
                value=_load_config().get("geo_id", 104116203),
                step=1,
                key="geo_id_input",
                help="LinkedIn's numeric location identifier. Use the button below to look it up from the Location field.",
            )
            if st.button("Look up Geo ID from location", key="lookup_geo_btn"):
                try:
                    from toolbox import get_geo_id
                    found_id, display = get_geo_id(location_text)
                    if found_id:
                        _save_config({"geo_id": int(found_id)})
                        st.success(f"{display} → {found_id}")
                        st.rerun()
                    else:
                        st.error("Could not find a Geo ID for that location.")
                except Exception as e:
                    st.error(f"Lookup failed: {e}")

        # Advanced — Browser, credentials, apply settings
        with st.expander("Browser & Credentials"):
            browser_mode = st.radio(
                "Browser mode",
                ["Launch new Chromium instance (safer)", "Connect to existing browser"],
                key="browser_mode_radio",
            )

            if browser_mode == "Connect to existing browser":
                b1, b2 = st.columns(2)
                with b1:
                    browser_type = st.selectbox("Browser", ["Chrome", "Edge"], key="browser_type_select")
                with b2:
                    cdp_port = st.number_input("CDP Port", value=9222, step=1, key="cdp_port_input")
                if st.button("Launch Browser with Debugging", key="launch_browser_btn"):
                    ok, msg = launch_browser_with_debugging(browser_type, cdp_port)
                    st.success(msg) if ok else st.error(msg)
                st.info("Launch your browser with debugging enabled, log into LinkedIn, then click Start.")
            else:
                creds = load_creds()
                c1, c2 = st.columns(2)
                with c1:
                    email = st.text_input("Email", value=creds["email"], key="email_input")
                with c2:
                    password = st.text_input("Password", value=creds["password"], type="password", key="password_input")
                if st.button("Save Credentials", key="save_creds_btn"):
                    save_creds(email, password)
                    st.success("Credentials saved")

            st.divider()
            a1, a2, a3 = st.columns(3)
            with a1:
                follow_companies = st.toggle("Follow companies", value=False, key="follow_toggle")
            with a2:
                requires_sponsorship = st.toggle("Needs sponsorship", value=False, key="sponsorship_toggle")
            with a3:
                max_applications = st.number_input("Max apps", min_value=1, max_value=50, value=10, step=1, key="max_apps_input")

        # Action buttons
        st.write("")
        btn1, btn2, btn3 = st.columns([1, 1, 1.2])
        with btn1:
            scrape_clicked = st.button("Scrape only",  key="btn_scrape", use_container_width=True)
        with btn2:
            queue_clicked  = st.button("Apply queue",  key="btn_queue",  use_container_width=True)
        with btn3:
            start_clicked  = st.button("Start", type="primary", key="btn_start", use_container_width=True)

    # ════ RIGHT — Recent Activity ════════════════════════════════════
    with col_right:
        st.markdown("**Recent Activity**")

        activity = _load_recent_activity()
        if not activity:
            st.caption("No activity yet — run a scrape or apply session to see results here.")

        for card in activity:
            _render_job_card(card)

    # ── Run logic ──────────────────────────────────────────────────────
    action = None
    if scrape_clicked:
        action = "scrape_only"
    elif queue_clicked:
        action = "apply_queue"
    elif start_clicked:
        action = "scrape_and_apply" if auto_apply else "scrape_only"

    if action:
        if geo_id is not None:
            _save_config({"geo_id": int(geo_id)})

        shared = dict(
            email=email,
            password=password,
            browser_mode="existing" if browser_mode == "Connect to existing browser" else "new",
            browser_type=browser_type or "Chrome",
            cdp_port=int(cdp_port),
        )

        with st.spinner("Running..."):
            if action == "scrape_only":
                result, error = run_scrape_only(
                    keyword=keyword, distance=distance,
                    geo_id=geo_id, easy_apply=easy_apply,
                    date_filter=date_filter[1], pages=pages,
                    **shared,
                )
                st.session_state.last_result = result
                st.session_state.last_error  = error
                st.session_state.last_mode   = "scrape_only"

            elif action == "scrape_and_apply":
                result, error = run_scrape_and_apply(
                    keyword=keyword, distance=distance,
                    geo_id=geo_id, easy_apply=easy_apply,
                    date_filter=date_filter[1], pages=pages,
                    follow_companies=follow_companies,
                    requires_sponsorship=requires_sponsorship,
                    max_applications=int(max_applications),
                    **shared,
                )
                st.session_state.last_result = result
                st.session_state.last_error  = error
                st.session_state.last_mode   = "scrape_and_apply"

            elif action == "apply_queue":
                if csv_count == 0:
                    st.warning("jobs.csv is empty — run a scrape first.")
                else:
                    result, error = run_apply_from_csv(
                        follow_companies=follow_companies,
                        requires_sponsorship=requires_sponsorship,
                        max_applications=int(max_applications),
                        **shared,
                    )
                    st.session_state.last_result = result
                    st.session_state.last_error  = error
                    st.session_state.last_mode   = "apply_queue"

    # ── Jobs queue table ───────────────────────────────────────────────
    st.divider()
    st.markdown("**Jobs Queue**")

    f1, f2, f3, _ = st.columns([1, 1, 1, 6])
    with f1:
        if st.button("All",        key="filter_all"):     st.session_state.job_filter = "all"
    with f2:
        if st.button("Easy Apply", key="filter_easy"):    st.session_state.job_filter = "easy"
    with f3:
        if st.button("Applied",    key="filter_applied"): st.session_state.job_filter = "applied"

    applied_set = _load_applied_set()

    rows = _load_jobs_for_table()
    if st.session_state.job_filter == "easy":
        rows = [r for r in rows if r["Type"] == "Easy Apply"]
    elif st.session_state.job_filter == "applied":
        rows = [r for r in rows if f"{r['Title']} at {r['Company']}".lower() in applied_set]

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No jobs match the current filter.")

    # ── Results ────────────────────────────────────────────────────────
    if st.session_state.last_error:
        st.error(st.session_state.last_error)
    elif st.session_state.last_result is not None:
        mode   = st.session_state.last_mode
        result = st.session_state.last_result

        st.divider()
        st.markdown("**Results**")

        if mode == "apply_queue":
            st.success(f"Batch complete — {result['applied']} applied, {result['skipped']} skipped, {result['failed']} failed")

        elif mode == "scrape_and_apply":
            scraped = result["jobs"]
            ar      = result["apply_results"]
            st.success(f"Scraped {len(scraped)} jobs")
            if ar:
                st.success(f"Applied {ar['applied']} — {ar['skipped']} skipped, {ar['failed']} failed")
            for job in scraped:
                with st.expander(f"{job['title']} — {job['company']}"):
                    st.write(job["location"])
                    st.write(job["salary"])
                    st.write(f"Easy Apply: {'Yes' if job['easy_apply'] else 'No'}")
                    st.markdown(f"[View on LinkedIn]({job['url']})")

        elif mode == "scrape_only":
            st.success(f"Found {len(result)} unique jobs")
            for job in result:
                with st.expander(f"{job['title']} — {job['company']}"):
                    st.write(job["location"])
                    st.write(job["salary"])
                    st.write(f"Easy Apply: {'Yes' if job['easy_apply'] else 'No'}")
                    st.markdown(f"[View on LinkedIn]({job['url']})")
