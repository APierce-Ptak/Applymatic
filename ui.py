import os
import csv
import streamlit as st

@st.dialog("👋 Welcome to Applymatic")
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
→ Geo ID is `90000070` *(New York City)*

Once you have it, paste it into the **Geo ID** field under Search Parameters.
    """)
    if st.button("Got it", type="primary", key="first_run_ack"):
        st.session_state.dismissed_guide = True
        st.rerun()

def _csv_job_count():
    if not os.path.exists("jobs.csv"):
        return 0
    try:
        with open("jobs.csv", "r", newline="", encoding="utf-8") as f:
            return sum(1 for _ in csv.DictReader(f))
    except Exception:
        return 0

def render(run_scrape_only, run_scrape_and_apply, run_apply_from_csv, load_creds, save_creds, launch_browser_with_debugging):

    st.set_page_config(page_title="Applymatic", layout="wide")
    st.title("🚀 Applymatic")

    profile_name = ""
    if os.path.exists("profile.json"):
        try:
            import json
            with open("profile.json") as f:
                profile_name = json.load(f).get("first_name", "")
        except Exception:
            pass

    is_first_run = profile_name == "NewUser" or profile_name == ""
    if is_first_run and not st.session_state.get("dismissed_guide", False):
        _first_run_guide()

    # --- Browser ---
    st.header("Browser")
    browser_mode = st.radio(
        "Browser mode",
        ["Launch new Chromium instance (safer)", "Connect to existing browser"],
        key="browser_mode_radio"
    )

    browser_type = None
    cdp_port = 9222

    if browser_mode == "Connect to existing browser":
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            browser_type = st.selectbox("Browser", ["Chrome", "Edge"], key="browser_type_select")
        with col_b2:
            cdp_port = st.number_input("CDP Port", value=9222, step=1, key="cdp_port_input")

        if st.button("🚀 Launch Browser with Debugging", key="launch_browser_btn"):
            success, message = launch_browser_with_debugging(browser_type, cdp_port)
            if success:
                st.success(message)
            else:
                st.error(message)

        st.info("ℹ️ Launch your browser with debugging enabled, make sure you are logged into LinkedIn, then click Start.")

    st.divider()

    # --- Credentials (new Chromium only) ---
    email = ""
    password = ""
    if browser_mode == "Launch new Chromium instance (safer)":
        creds = load_creds()
        st.header("Credentials")
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("Email", value=creds["email"], key="email_input")
        with col2:
            password = st.text_input("Password", value=creds["password"], type="password", key="password_input")

        if st.button("💾 Save Credentials", key="save_creds_btn"):
            save_creds(email, password)
            st.success("Credentials saved")

        st.divider()

    # --- Mode ---
    st.header("Mode")
    mode = st.radio("Select mode", ["Scrape only", "Scrape and apply", "Apply from CSV"], key="mode_radio")

    keyword = distance = geo_id = date_filter = easy_apply = pages = None

    if mode in ["Scrape only", "Scrape and apply"]:
        st.header("Search Parameters")
        pages = st.slider("Pages to scrape", min_value=1, max_value=10, value=3, step=1, key="pages_slider")

        col3, col4 = st.columns(2)
        with col3:
            keyword = st.text_input("Job Title / Keyword", value="Software Engineer", key="keyword_input")
            distance = st.slider("Distance (miles)", min_value=5, max_value=100, value=50, step=5, key="distance_slider")
        with col4:
            geo_id = st.number_input("Geo ID", value=90000070, step=1, key="geo_id_input")

            date_filter = st.selectbox("Date Posted", options=[
                ("Past 1 hour", "r3600"),
                ("Past 6 hours", "r21600"),
                ("Past 12 hours", "r43200"),
                ("Past 24 hours", "r86400"),
                ("Past week", "r604800"),
                ("Past month", "r2592000"),
                ("Any time", None)
            ], format_func=lambda x: x[0], key="date_filter_select")

        easy_apply = st.toggle("Easy Apply Only", value=True, key="easy_apply_toggle")

    follow_companies = requires_sponsorship = max_applications = None
    if mode in ["Scrape and apply", "Apply from CSV"]:
        st.header("Apply Options")
        col5, col6 = st.columns(2)
        with col5:
            follow_companies = st.toggle("Follow companies after applying", value=False, key="follow_toggle")
            requires_sponsorship = st.toggle("Requires visa sponsorship", value=False, key="sponsorship_toggle")
        with col6:
            max_applications = st.number_input("Max applications", min_value=1, max_value=50, value=10, step=1, key="max_apps_input")

    csv_jobs = _csv_job_count()
    if mode == "Apply from CSV":
        if csv_jobs == 0:
            st.warning("⚠️ jobs.csv is empty — run a scrape first to populate it.")
        else:
            st.info(f"Will apply to {csv_jobs} jobs saved in jobs.csv")

    st.divider()

    start_disabled = mode == "Apply from CSV" and csv_jobs == 0
    if st.button("🚀 Start", type="primary", key="start_btn", disabled=start_disabled):
        with st.spinner("Running..."):
            shared = dict(
                email=email,
                password=password,
                browser_mode="existing" if browser_mode == "Connect to existing browser" else "new",
                browser_type=browser_type or "Chrome",
                cdp_port=int(cdp_port),
            )

            if mode == "Scrape only":
                all_jobs, error = run_scrape_only(
                    keyword=keyword, distance=distance,
                    geo_id=geo_id, easy_apply=easy_apply,
                    date_filter=date_filter[1], pages=pages,
                    **shared
                )

            elif mode == "Scrape and apply":
                all_jobs, error = run_scrape_and_apply(
                    keyword=keyword, distance=distance,
                    geo_id=geo_id, easy_apply=easy_apply,
                    date_filter=date_filter[1], pages=pages,
                    follow_companies=follow_companies,
                    requires_sponsorship=requires_sponsorship,
                    max_applications=int(max_applications),
                    **shared
                )

            elif mode == "Apply from CSV":
                all_jobs, error = run_apply_from_csv(
                    follow_companies=follow_companies,
                    requires_sponsorship=requires_sponsorship,
                    max_applications=int(max_applications),
                    **shared
                )

        if error:
            st.error(error)
        else:
            if mode == "Apply from CSV":
                st.success(f"Batch complete — {all_jobs['applied']} applied, {all_jobs['failed']} failed")
            else:
                st.success(f"Found {len(all_jobs)} unique jobs")
                st.divider()
                st.header("Results")
                for job in all_jobs:
                    with st.expander(f"{job['title']} — {job['company']}"):
                        st.write(f"📍 {job['location']}")
                        st.write(f"💰 {job['salary']}")
                        st.write(f"⚡ Easy Apply: {'Yes' if job['easy_apply'] else 'No'}")
                        st.markdown(f"[View Job]({job['url']})")
