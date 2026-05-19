import json
import os
import debugLogger

PROFILE_FILE = "profile.json"
QUESTIONS_FILE = "questions.json"

class QuestionCache:
    def __init__(self):
        self.profile = self.load_profile()
        self.questions = self.load_questions()

    def load_profile(self):
        if os.path.exists(PROFILE_FILE):
            with open(PROFILE_FILE, "r") as f:
                return json.load(f)
        
        # create a default profile.json on first run
        default = {
            "first_name": "NewUser",
            "last_name": "NewUser_lastName",
            "email": "",
            "phone": "",
            "phone_country_code": "1",
            "location": "",
            "linkedin": "",
            "desired_salary": "",
            "work_authorization": "Yes",
            "requires_sponsorship": "No",
            "notice_period": "2 weeks",
            "gender": "Prefer not to say",
            "veteran_status": "No",
            "disability_status": "No",
            "years_experience_default": "1",
            "years_experience_technologies": {},
            "default_answer": "No"
        }
        with open(PROFILE_FILE, "w") as f:
            json.dump(default, f, indent=2)
        debugLogger.log(f"Created default {PROFILE_FILE} — please fill in your details before applying.")
        return default

    def load_questions(self):
        if os.path.exists(QUESTIONS_FILE):
            try:
                with open(QUESTIONS_FILE, "r") as f:
                    content = f.read().strip()
                    if not content:
                        return {}
                    return json.loads(content)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_questions(self):
        with open(QUESTIONS_FILE, "w") as f:
            json.dump(self.questions, f, indent=2)

    def _normalize_yes_no(self, value):
        return {"yes": "Yes", "no": "No", "y": "Yes", "n": "No", "true": "Yes", "false": "No"}.get(value.lower(), value)

    def get_answer(self, question_text, options=None, cached_only=False):
        cleaned = question_text.strip().split('\n')[0].strip()
        key = cleaned.lower()

        if key in self.questions:
            cached = self._normalize_yes_no(self.questions[key])
            debugLogger.log(f"Cached: {cleaned} → {cached}")
            return cached

        if cached_only:
            return None

        default = self.profile.get("default_answer")

        if options:
            if default and default in options:
                debugLogger.log(f"Using default: {cleaned} → {default}")
                self.questions[key] = default
                self.save_questions()
                return default

            # case-insensitive default match
            match = next((o for o in options if str(o).lower() == str(default).lower()), None) if default else None
            if match:
                debugLogger.log(f"Using default (case-insensitive): {cleaned} → {match}")
                self.questions[key] = match
                self.save_questions()
                return match

            # fall back to first option rather than blocking on input()
            answer = options[0]
            debugLogger.log(f"No default match — using first option for: {cleaned} → {answer}")
        else:
            if default:
                debugLogger.log(f"Using default for: {cleaned} → {default}")
                self.questions[key] = default
                self.save_questions()
                return default

            debugLogger.log(f"No answer and no default for: {cleaned} — skipping")
            return None

        self.questions[key] = answer
        self.save_questions()
        return answer