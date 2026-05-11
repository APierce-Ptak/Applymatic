from questionCache import QuestionCache
import debugLogger

class FormFiller:
    def __init__(self, cache: QuestionCache, follow_companies=False, requires_sponsorship=False):
        self.cache = cache
        self.follow_companies = follow_companies
        self.requires_sponsorship = requires_sponsorship

    def get_label(self, page, element):
        try:
            label = element.get_attribute("aria-label")
            if label:
                return label.strip().split('\n')[0].strip()
            el_id = element.get_attribute("id")
            if el_id:
                label_el = page.query_selector(f"label[for='{el_id}']")
                if label_el:
                    return label_el.inner_text().strip().split('\n')[0].strip()
            return None
        except:
            return None

    def match_profile(self, label):
        label_lower = label.lower()

        # check technology-specific experience first
        if "year" in label_lower or "experience" in label_lower:
            tech_map = self.cache.profile.get("years_experience_technologies", {})
            for tech, years in tech_map.items():
                if tech.lower() in label_lower:
                    debugLogger.log(f"Matched technology: {tech} → {years}")
                    return years
            # no specific technology matched — use default
            return self.cache.profile.get("years_experience_default", "1")

        # standard field mapping
        mapping = {
            "first name": self.cache.profile.get("first_name"),
            "last name": self.cache.profile.get("last_name"),
            "email": self.cache.profile.get("email"),
            "phone country code": self.cache.profile.get("phone_country_code"),
            "phone": self.cache.profile.get("phone"),
            "city": self.cache.profile.get("location"),
            "location": self.cache.profile.get("location"),
            "where": self.cache.profile.get("location"),
            "linkedin": self.cache.profile.get("linkedin"),
            "desired salary": self.cache.profile.get("desired_salary"),
            "expected salary": self.cache.profile.get("desired_salary"),
            "work authorization": self.cache.profile.get("work_authorization"),
            "authorized to work": self.cache.profile.get("work_authorization"),
            "require sponsorship": self.cache.profile.get("requires_sponsorship"),
            "notice period": self.cache.profile.get("notice_period"),
            "gender": self.cache.profile.get("gender"),
            "veteran": self.cache.profile.get("veteran_status"),
            "disability": self.cache.profile.get("disability_status"),
        }

        for keyword, value in mapping.items():
            if keyword in label_lower and value:
                return value

        return None

    def fill_location_autocomplete(self, page, input_el, value):
        try:
            input_el.click()
            input_el.fill("")
            page.wait_for_timeout(300)
            input_el.type(value, delay=50)
            page.wait_for_timeout(1500)  # wait for dropdown to appear

            # try multiple selectors for the dropdown suggestion
            suggestion = page.query_selector("[role='option']")
            if not suggestion:
                suggestion = page.query_selector(".basic-typeahead__selectable")
            if not suggestion:
                suggestion = page.query_selector(".typeahead-popup__option")
            if suggestion:
                suggestion.click()
                page.wait_for_timeout(500)
                debugLogger.log(f"Location autocomplete filled: {value}")
                return True

            debugLogger.log(f"No autocomplete suggestion found for: {value}")
            return False
        except Exception as e:
            debugLogger.log(f"Location autocomplete error: {e}")
            return False

    def _fill_top_choice(self, page):
        try:
            top_choice = page.query_selector('input[name="jobDetailsEasyApplyTopChoiceCheckbox"]')
            if top_choice and top_choice.is_checked():
                top_choice.uncheck()
                debugLogger.log("Top Choice unchecked")
        except Exception as e:
            debugLogger.log(f"Top choice error: {e}")

    def _fill_follow_checkbox(self, page):
        try:
            follow_checkbox = page.query_selector('input[id="follow-company-checkbox"]')
            if follow_checkbox:
                label = page.query_selector('label[for="follow-company-checkbox"]')
                if label:
                    is_checked = follow_checkbox.is_checked()
                    if is_checked and not self.follow_companies:
                        label.click(force=True)
                        page.wait_for_timeout(500)
                        debugLogger.log("Follow company unchecked")
                    elif not is_checked and self.follow_companies:
                        label.click(force=True)
                        page.wait_for_timeout(500)
                        debugLogger.log("Follow company checked")
        except Exception as e:
            debugLogger.log(f"Follow checkbox error: {e}")

    def _fill_sponsorship(self, page):
        try:
            fieldsets = page.query_selector_all(
                "fieldset[data-test-form-builder-radio-button-form-component='true']"
            )
            for fieldset in fieldsets:
                legend = fieldset.query_selector(
                    "[data-test-form-builder-radio-button-form-component__title]"
                )
                if legend and "sponsorship" in legend.inner_text().lower():
                    answer = "Yes" if self.requires_sponsorship else "No"
                    radio = fieldset.query_selector(
                        f"input[data-test-text-selectable-option__input='{answer}']"
                    )
                    if radio:
                        radio.check()
                        debugLogger.log(f"Visa sponsorship set to: {answer}")
        except Exception as e:
            debugLogger.log(f"Sponsorship error: {e}")

    def _fill_radio_buttons(self, page):
        try:
            all_fieldsets = page.query_selector_all(
                "fieldset[data-test-form-builder-radio-button-form-component='true']"
            )
            for fieldset in all_fieldsets:
                legend = fieldset.query_selector(
                    "[data-test-form-builder-radio-button-form-component__title]"
                )
                if not legend:
                    continue
                question_text = legend.inner_text().strip().split('\n')[0].strip()

                if "sponsorship" in question_text.lower():
                    continue

                if fieldset.query_selector("input[type='radio']:checked"):
                    debugLogger.log(f"Already answered: {question_text}")
                    page.wait_for_timeout(300)
                    continue

                options = [
                    r.get_attribute("data-test-text-selectable-option__input")
                    for r in fieldset.query_selector_all("input[data-test-text-selectable-option__input]")
                    if r.get_attribute("data-test-text-selectable-option__input")
                ]

                answer = self.match_profile(question_text) or self.cache.get_answer(question_text, options=options)
                if answer:
                    radio = fieldset.query_selector(f"input[data-test-text-selectable-option__input='{answer}']")
                    if radio:
                        radio.check()
                        debugLogger.log(f"Radio set: {question_text} → {answer}")
        except Exception as e:
            debugLogger.log(f"Radio buttons error: {e}")

    def _fill_text_inputs(self, page):
        try:
            for input_el in page.query_selector_all("[data-test-single-line-text-form-component] input"):
                label = self.get_label(page, input_el)
                if not label:
                    continue
                if input_el.input_value().strip():
                    debugLogger.log(f"Already filled: {label}")
                    page.wait_for_timeout(300)
                    continue
                answer = self.match_profile(label) or self.cache.get_answer(label)
                if answer:
                    if any(word in label.lower() for word in ["city", "location", "where"]):
                        self.fill_location_autocomplete(page, input_el, str(answer))
                    else:
                        input_el.fill(str(answer))
        except Exception as e:
            debugLogger.log(f"Text inputs error: {e}")

    def _fill_selects(self, page):
        try:
            for select in page.query_selector_all("[data-test-text-entity-list-form-select]"):
                label = self.get_label(page, select)
                if not label:
                    continue
                current = select.input_value()
                if current.strip() and current != "Select an option":
                    debugLogger.log(f"Already selected: {label} = {current}")
                    page.wait_for_timeout(300)
                    continue
                options = page.evaluate("""
                    (el) => Array.from(el.options)
                        .map(o => o.value)
                        .filter(v => v !== 'Select an option')
                """, select)
                answer = self.match_profile(label) or self.cache.get_answer(label, options=options)
                if answer:
                    try:
                        select.select_option(value=answer, timeout=2000)
                    except Exception:
                        debugLogger.log(f"Could not select '{answer}' for '{label}' — skipping")
        except Exception as e:
            debugLogger.log(f"Selects error: {e}")

    def _fill_textareas(self, page):
        try:
            for textarea in page.query_selector_all("textarea"):
                label = self.get_label(page, textarea)
                if not label:
                    continue
                if textarea.input_value().strip():
                    debugLogger.log(f"Already filled: {label}")
                    page.wait_for_timeout(300)
                    continue
                answer = self.match_profile(label) or self.cache.get_answer(label)
                if answer:
                    textarea.fill(str(answer))
        except Exception as e:
            debugLogger.log(f"Textareas error: {e}")

    def fill_form_page(self, page):
        try:
            self._fill_top_choice(page)
            self._fill_follow_checkbox(page)
            self._fill_sponsorship(page)
            self._fill_radio_buttons(page)
            self._fill_text_inputs(page)
            self._fill_selects(page)
            self._fill_textareas(page)
            page.wait_for_timeout(1000)
            return True
        except Exception as e:
            debugLogger.log(f"Error filling form: {e}")
            return False

    def handle_next_or_submit(self, page):
        try:
            next_btn = page.query_selector("[data-easy-apply-next-button]")
            if next_btn:
                next_btn.click()
                page.wait_for_timeout(1500)
                return "next"

            review_btn = page.query_selector("button[aria-label='Review your application']")
            if review_btn:
                review_btn.click()
                page.wait_for_timeout(1500)
                return "review"

            submit_btn = page.query_selector("[data-live-test-easy-apply-submit-button]")
            if submit_btn:
                return "submit"

            return "unknown"

        except Exception as e:
            debugLogger.log(f"Error handling next/submit: {e}")
            return "unknown"