import json
import os
from questionCache import QuestionCache
from formFiller import FormFiller
from toolbox import human_delay
import debugLogger

class AutoApply:
    def __init__(self, follow_companies=False, requires_sponsorship=False):
        self.cache = QuestionCache()
        self.filler = FormFiller(self.cache, follow_companies, requires_sponsorship)

    def navigate_to_job(self, page, job_url):
        try:
            page.goto(job_url)
            page.wait_for_load_state("load")
            human_delay(1500, 3000)

            # Check for previously submitted before looking for the apply button
            already_submitted = page.evaluate("""
                () => Array.from(document.querySelectorAll('p'))
                    .some(p => p.innerText.trim() === 'Application submitted')
            """)
            if already_submitted:
                return None

            closed = page.evaluate("""
                () => document.body.innerText.includes('No longer accepting applications')
            """)
            if closed:
                return "closed"

            button = page.query_selector("a[aria-label='Easy Apply to this job']")
            if not button:
                button = page.query_selector("[aria-label*='Easy Apply']")
            if not button:
                debugLogger.log(f"No Easy Apply button found at {job_url}")
                return False

            button.dispatch_event("click")
            human_delay(1500, 3000)
            return True

        except Exception as e:
            debugLogger.log(f"Error navigating to job: {e}")
            return False

    def close_modal(self, page):
        try:
            done_btn = page.wait_for_selector(
                "button:has-text('Done')",
                timeout=5000
            )
            if done_btn:
                done_btn.click()
                human_delay(800, 1500)
                debugLogger.log("Modal closed")
        except Exception as e:
            debugLogger.log(f"Could not close modal: {e}")

    def auto_submit(self, page):
        submit_btn = page.query_selector("[data-live-test-easy-apply-submit-button]")
        if submit_btn:
            submit_btn.click()
            human_delay(1500, 3000)
            debugLogger.log("Application submitted!")
            self.close_modal(page)
            return True
        debugLogger.log("Submit button not found")
        return False

    def get_form_fingerprint(self, page):
        try:
            return page.evaluate("""
                () => {
                    const fields = [
                        ...document.querySelectorAll('[data-test-single-line-text-form-component] input'),
                        ...document.querySelectorAll('[data-test-text-entity-list-form-select]'),
                        ...document.querySelectorAll('[data-test-form-builder-radio-button-form-component] input[type="radio"]'),
                        ...document.querySelectorAll('textarea'),
                    ];
                    return fields
                        .map(el => el.getAttribute('name') || el.getAttribute('id') || el.getAttribute('aria-label') || el.tagName)
                        .join('|');
                }
            """)
        except:
            return ""

    def apply_to_job(self, page, job):
        debugLogger.log(f"\nApplying to: {job['title']} at {job['company']}")

        nav_result = self.navigate_to_job(page, job["url"])
        if nav_result is None:
            debugLogger.log(f"Previously submitted — skipping: {job['title']} at {job['company']}")
            return None
        if nav_result == "closed":
            debugLogger.log(f"No longer accepting applications — skipping: {job['title']} at {job['company']}")
            return None
        if not nav_result:
            return False

        max_pages = 10
        last_fingerprint = None
        stall_count = 0
        max_stalls = 2  # allow up to 2 retries on a stuck page before giving up

        for i in range(max_pages):
            debugLogger.log(f"Form page {i + 1}")

            # detect if we are stuck on the same form page
            current_fingerprint = self.get_form_fingerprint(page)
            if current_fingerprint and current_fingerprint == last_fingerprint:
                stall_count += 1
                debugLogger.log(f"Page did not advance — possible unfilled required field (stall {stall_count}/{max_stalls})")
                if stall_count >= max_stalls:
                    debugLogger.log("Stuck on same page too many times — skipping this job")
                    return False
            else:
                stall_count = 0
                last_fingerprint = current_fingerprint

            self.filler.fill_form_page(page)
            result = self.filler.handle_next_or_submit(page)

            if result == "submit":
                return self.auto_submit(page)
            elif result == "unknown":
                debugLogger.log("Could not find Next or Submit — stopping")
                return False
            else:
                # Next or Review was found and clicked — form is advancing, reset stall counter
                stall_count = 0
                human_delay(1500, 2500)

        return False

    def apply_single(self, page, job):
        return self.apply_to_job(page, job)

    def apply_batch(self, page, jobs, max_applications=None):
        results = {"applied": 0, "failed": 0, "skipped": 0}

        for job in jobs:
            if max_applications is not None and results["applied"] >= max_applications:
                debugLogger.log(f"Reached {max_applications} successful applications — stopping")
                break

            if isinstance(job, str):
                job = {"title": "Unknown", "company": "Unknown", "url": job}

            job = {k.strip(): v for k, v in job.items()}

            if "title" not in job or "url" not in job:
                debugLogger.log(f"Skipping job — missing required fields: {job}")
                results["failed"] += 1
                continue

            result = self.apply_to_job(page, job)
            if result is True:
                results["applied"] += 1
                max_str = f"/{max_applications}" if max_applications is not None else ""
                debugLogger.log(f"[{results['applied']}{max_str}] Applied: {job.get('title')} at {job.get('company')}")
            elif result is None:
                results["skipped"] += 1
                debugLogger.log(f"Skipped: {job.get('title')} at {job.get('company')}")
            else:
                results["failed"] += 1
                debugLogger.log(f"Failed: {job.get('title')} at {job.get('company')}")

        debugLogger.log(f"\nBatch complete — {results['applied']} applied, {results['skipped']} skipped, {results['failed']} failed")
        return results