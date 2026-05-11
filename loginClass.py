import os
import debugLogger

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
SESSION_FILE = "session.json"

class Login:
    def __init__(self):
        pass

    def loginTo(self, url, username, password, browser):
        try:
            if os.path.exists(SESSION_FILE):
                debugLogger.log("Session file found — attempting to restore...")
                context = browser.new_context(storage_state=SESSION_FILE, user_agent=USER_AGENT)
                page = context.new_page()
                page.goto("https://www.linkedin.com/feed/")
                page.wait_for_load_state("load")
                page.wait_for_timeout(2000)
                if "feed" in page.url or "jobs" in page.url:
                    debugLogger.log("Session restored — already logged in!")
                    return True, page
                debugLogger.log("Session expired — falling back to fresh login...")
                page.close()
                context.close()

            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            page.goto(url)
            page.wait_for_load_state("load")
            page.wait_for_timeout(3000)

            if "feed" in page.url or "jobs" in page.url:
                debugLogger.log("Already logged in!")
                return True, page

            try:
                page.wait_for_selector('input[name="session_key"]', timeout=8000)
            except Exception:
                debugLogger.log(f"Login form not found — page: {page.url}")
                return False, page

            page.fill('input[name="session_key"]', username)
            page.fill('input[name="session_password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_load_state("load")
            page.wait_for_timeout(2000)

            debugLogger.log(f"Post-submit URL: {page.url}")

            if "feed" in page.url or "jobs" in page.url:
                page.context.storage_state(path=SESSION_FILE)
                debugLogger.log(f"Session saved to {SESSION_FILE}")
                debugLogger.log("Login successful!")
                return True, page

            debugLogger.log(f"Login failed — unexpected page: {page.url}")
            return False, page

        except Exception as e:
            debugLogger.log(f"An error occurred during login: {str(e)}")
            return False, None
