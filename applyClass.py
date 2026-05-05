import json
import os
from questionCache import QuestionCache
from formFiller import FormFiller
from toolbox import human_delay

class AutoApply:
    def __init__(self, follow_companies=False, requires_sponsorship=False):
        self.cache = QuestionCache()
        self.filler = FormFiller(self.cache, follow_companies, requires_sponsorship)

    def navigate_to_job(self, page, job_url):
        try:
            page.goto(job_url)
            page.wait_for_load_state("load")
            human_delay(1500, 3000)

            button = page.query_selector("a[aria-label='Easy Apply to this job']")
            if not button:
                button = page.query_selector("[aria-label*='Easy Apply']")
            if not button:
                print(f"No Easy Apply button found at {job_url}")
                return False

            button.dispatch_event("click")
            human_delay(1500, 3000)
            return True

        except Exception as e:
            print(f"Error navigating to job: {e}")
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
                print("Modal closed")
        except Exception as e:
            print(f"Could not close modal: {e}")

    def auto_submit(self, page):
        submit_btn = page.query_selector("[data-live-test-easy-apply-submit-button]")
        if submit_btn:
            submit_btn.click()
            human_delay(1500, 3000)
            print("Application submitted!")
            self.close_modal(page)
            return True
        print("Submit button not found")
        return False

    def get_form_fingerprint(self, page):
        """Returns a string that identifies the current form state by its visible field labels."""
        try:
            labels = page.evaluate("""
                () => Array.from(document.querySelectorAll('label, legend'))
                    .map(el => el.innerText.trim())
                    .filter(t => t.length > 0)
                    .join('|')
            """)
            return labels
        except:
            return ""

    def apply_to_job(self, page, job):
        print(f"\nApplying to: {job['title']} at {job['company']}")

        if not self.navigate_to_job(page, job["url"]):
            return False

        max_pages = 10
        last_fingerprint = None
        stall_count = 0
        max_stalls = 2  # allow up to 2 retries on a stuck page before giving up

        for i in range(max_pages):
            print(f"Form page {i + 1}")

            # detect if we are stuck on the same form page
            current_fingerprint = self.get_form_fingerprint(page)
            if current_fingerprint and current_fingerprint == last_fingerprint:
                stall_count += 1
                print(f"Page did not advance — possible unfilled required field (stall {stall_count}/{max_stalls})")
                if stall_count >= max_stalls:
                    print("Stuck on same page too many times — skipping this job")
                    return False
            else:
                stall_count = 0
                last_fingerprint = current_fingerprint

            self.filler.fill_form_page(page)
            result = self.filler.handle_next_or_submit(page)

            if result == "submit":
                return self.auto_submit(page)
            elif result == "unknown":
                print("Could not find Next or Submit — stopping")
                return False

        return False

    def apply_single(self, page, job):
        return self.apply_to_job(page, job)

    def apply_batch(self, page, jobs):
        results = {"applied": 0, "failed": 0}

        for job in jobs:
            if isinstance(job, str):
                job = {"title": "Unknown", "company": "Unknown", "url": job}

            job = {k.strip(): v for k, v in job.items()}

            if "title" not in job or "url" not in job:
                print(f"Skipping job — missing required fields: {job}")
                results["failed"] += 1
                continue

            success = self.apply_to_job(page, job)
            if success:
                results["applied"] += 1
            else:
                results["failed"] += 1

            print(f"\nFinished: {job.get('title')} at {job.get('company')}")

        print(f"\nBatch complete — {results['applied']} applied, {results['failed']} failed")
        return results