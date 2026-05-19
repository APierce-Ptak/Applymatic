import re
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

    def _check_salary_range(self, label, desired_salary):
        """Returns 'Yes'/'No' if the label contains a salary range and desired_salary falls within it."""
        try:
            s = str(desired_salary).replace(',', '').replace('$', '').strip().lower()
            salary = float(s[:-1]) * 1000 if s.endswith('k') else float(s)
            if salary < 1000:
                salary *= 1000
        except (ValueError, TypeError):
            return None
        m = re.search(r'\$?([\d]+)(k?)\s*[-–]\s*\$?([\d]+)(k?)', label.replace(',', ''), re.IGNORECASE)
        if not m:
            return None
        lo, lo_k = float(m.group(1)), m.group(2).lower()
        hi, hi_k = float(m.group(3)), m.group(4).lower()
        if lo_k == 'k' or (not lo_k and lo < 1000):
            lo *= 1000
        if hi_k == 'k' or (not hi_k and hi < 1000):
            hi *= 1000
        return "Yes" if lo <= salary <= hi else "No"

    def match_profile(self, label, options=None):
        label_lower = label.lower()

        # check technology-specific experience first
        if "year" in label_lower or "experience" in label_lower:
            # if the available options are yes/no style, don't inject a years value
            if options:
                options_lower = [str(o).lower() for o in options]
                if any(o in ("yes", "no") for o in options_lower):
                    return None
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
            "salary": self.cache.profile.get("desired_salary"),
            "desired pay": self.cache.profile.get("desired_salary"),
            "pay rate": self.cache.profile.get("desired_salary"),
            "compensation": self.cache.profile.get("desired_salary"),
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
                if options:
                    options_lower = [str(o).lower() for o in options]
                    if any(o in ("yes", "no") for o in options_lower):
                        return self._check_salary_range(label, value)
                    if not any(str(value).lower() == o for o in options_lower):
                        return None
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

                if fieldset.query_selector("input[type='radio']:checked"):
                    debugLogger.log(f"Already answered: {question_text}")
                    page.wait_for_timeout(300)
                    continue

                options = [
                    r.get_attribute("data-test-text-selectable-option__input")
                    for r in fieldset.query_selector_all("input[data-test-text-selectable-option__input]")
                    if r.get_attribute("data-test-text-selectable-option__input")
                ]

                if "sponsorship" in question_text.lower():
                    answer = "Yes" if self.requires_sponsorship else "No"
                else:
                    answer = self.match_profile(question_text, options=options) or self.cache.get_answer(question_text, options=options)

                if answer:
                    radio = fieldset.query_selector(f"input[data-test-text-selectable-option__input='{answer}']")
                    if not radio:
                        for r in fieldset.query_selector_all("input[data-test-text-selectable-option__input]"):
                            if (r.get_attribute("data-test-text-selectable-option__input") or "").lower() == str(answer).lower():
                                radio = r
                                break
                    if radio:
                        # click the label — it sits on top of the input and intercepts pointer events
                        radio_id = radio.get_attribute("id")
                        label_el = fieldset.query_selector(f"label[for='{radio_id}']") if radio_id else None
                        if label_el:
                            label_el.click()
                        else:
                            radio.check(force=True)
                        debugLogger.log(f"Radio set: {question_text} → {answer}")
                    else:
                        debugLogger.log(f"No radio match for '{question_text}': answer='{answer}', options={options}")
        except Exception as e:
            debugLogger.log(f"Radio buttons error: {e}")

    def _type_into(self, input_el, value):
        input_el.click()
        input_el.fill("")
        input_el.type(str(value), delay=40)

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
                answer = self.match_profile(label) or self.cache.get_answer(label, cached_only=True)
                if answer:
                    if any(word in label.lower() for word in ["city", "location", "where"]):
                        self.fill_location_autocomplete(page, input_el, str(answer))
                    else:
                        self._type_into(input_el, answer)
                        debugLogger.log(f"Text filled: {label} → {answer}")
                else:
                    debugLogger.log(f"No answer for text field: {label}")
        except Exception as e:
            debugLogger.log(f"Text inputs error: {e}")

    def _fill_numeric_inputs(self, page):
        try:
            for input_el in page.query_selector_all("[data-test-numeric-text-entity-form-component] input"):
                label = self.get_label(page, input_el)
                if not label:
                    continue
                if input_el.input_value().strip():
                    debugLogger.log(f"Already filled: {label}")
                    page.wait_for_timeout(300)
                    continue
                answer = self.match_profile(label)
                if not answer:
                    cached = self.cache.get_answer(label, cached_only=True)
                    try:
                        float(str(cached or '').replace(',', '').replace('$', '').strip())
                        answer = cached
                    except (ValueError, TypeError):
                        pass
                if answer:
                    self._type_into(input_el, answer)
                    debugLogger.log(f"Numeric filled: {label} → {answer}")
                else:
                    debugLogger.log(f"No answer for numeric field: {label}")
        except Exception as e:
            debugLogger.log(f"Numeric inputs error: {e}")

    def _fill_checkboxes(self, page):
        try:
            for fieldset in page.query_selector_all("[data-test-form-builder-boolean-form-component='true']"):
                label_el = fieldset.query_selector("[data-test-form-builder-boolean-form-component__title]")
                if not label_el:
                    continue
                question_text = label_el.inner_text().strip().split('\n')[0].strip()
                checkbox = fieldset.query_selector("input[type='checkbox']")
                if not checkbox:
                    continue
                if checkbox.is_checked():
                    debugLogger.log(f"Checkbox already checked: {question_text}")
                    continue
                answer = self.match_profile(question_text) or self.cache.get_answer(question_text, options=["Yes", "No"])
                if answer and str(answer).lower() in ("yes", "true", "1"):
                    checkbox.check()
                    debugLogger.log(f"Checkbox checked: {question_text}")
        except Exception as e:
            debugLogger.log(f"Checkbox error: {e}")

    def _fill_selects(self, page):
        try:
            for select in page.query_selector_all("[data-test-text-entity-list-form-select]"):
                label = self.get_label(page, select)
                if not label:
                    continue
                opts = page.evaluate("""
                    (el) => Array.from(el.options)
                        .filter(o => o.value && o.value !== 'Select an option')
                        .map(o => ({value: o.value, text: o.text.trim()}))
                """, select)
                option_values = [o["value"] for o in opts]
                current = select.input_value()
                if current.strip() and current in option_values:
                    debugLogger.log(f"Already selected: {label} = {current}")
                    page.wait_for_timeout(300)
                    continue
                answer = self.match_profile(label, options=option_values) or self.cache.get_answer(label, options=option_values)
                if answer:
                    ans_lower = str(answer).lower()
                    match = next((o["value"] for o in opts if o["value"].lower() == ans_lower), None)
                    if not match:
                        match = next((o["value"] for o in opts if o["text"].lower() == ans_lower), None)
                    if not match:
                        # numeric range fallback: "3-5 years" or "5+" style options
                        try:
                            num = float(str(answer).replace(',', '').replace('$', '').strip())
                            for o in opts:
                                rm = re.search(r'(\d+)\s*[-–]\s*(\d+)', o["text"])
                                if rm and float(rm.group(1)) <= num <= float(rm.group(2)):
                                    match = o["value"]
                                    break
                            if not match:
                                for o in opts:
                                    rm = re.search(r'(\d+)\s*\+', o["text"])
                                    if rm and num >= float(rm.group(1)):
                                        match = o["value"]
                        except (ValueError, TypeError):
                            pass
                    if match:
                        try:
                            select.select_option(value=match, timeout=2000)
                            debugLogger.log(f"Select set: {label} → {match}")
                        except Exception:
                            debugLogger.log(f"Could not select '{match}' for '{label}' — skipping")
                    else:
                        debugLogger.log(f"No matching option for '{label}': answer='{answer}', options={option_values}")
                else:
                    debugLogger.log(f"No answer for select: {label}")
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
                answer = self.match_profile(label) or self.cache.get_answer(label, cached_only=True)
                if answer:
                    textarea.fill(str(answer))
                    debugLogger.log(f"Textarea filled: {label} → {answer}")
        except Exception as e:
            debugLogger.log(f"Textareas error: {e}")

    def _fill_date_fields(self, page):
        from datetime import datetime
        try:
            for wrapper in page.query_selector_all("[data-test-form-builder-date-form-component]"):
                for select in wrapper.query_selector_all("select"):
                    if select.input_value().strip():
                        continue
                    opts = page.evaluate("""
                        (el) => Array.from(el.options)
                            .filter(o => o.value && o.value !== 'Select an option')
                            .map(o => ({value: o.value, text: o.text.trim()}))
                    """, select)
                    if not opts:
                        continue
                    label = self.get_label(page, select) or ""
                    name  = select.get_attribute("name") or ""
                    hint  = (label + " " + name).lower()
                    if "year" in hint:
                        year_str = str(datetime.now().year)
                        match = next((o["value"] for o in opts if o["value"] == year_str or o["text"] == year_str), opts[-1]["value"])
                        select.select_option(value=match)
                        debugLogger.log(f"Date year set → {match}")
                    elif "month" in hint:
                        select.select_option(value=opts[0]["value"])
                        debugLogger.log(f"Date month set → {opts[0]['value']}")
                for input_el in wrapper.query_selector_all("input[type='date']"):
                    if input_el.input_value().strip():
                        continue
                    input_el.fill(datetime.now().strftime("%Y-%m-%d"))
                    debugLogger.log("Date input filled with today")
        except Exception as e:
            debugLogger.log(f"Date fields error: {e}")

    def _log_unfilled_required(self, page):
        try:
            unfilled = page.evaluate("""
                () => [...document.querySelectorAll(
                    '[required], [aria-required="true"]'
                )]
                .filter(el => el.offsetParent !== null && (!el.value || el.value === 'Select an option'))
                .map(el => el.getAttribute('aria-label') || el.getAttribute('name') || el.tagName)
                .filter(Boolean)
            """)
            for field in unfilled:
                debugLogger.log(f"Still empty required field: {field}")
        except Exception:
            pass

    def fill_form_page(self, page):
        try:
            self._fill_top_choice(page)
            self._fill_follow_checkbox(page)
            self._fill_radio_buttons(page)
            self._fill_checkboxes(page)
            self._fill_text_inputs(page)
            self._fill_numeric_inputs(page)
            self._fill_selects(page)
            self._fill_textareas(page)
            self._fill_date_fields(page)
            page.wait_for_timeout(1000)
            self._log_unfilled_required(page)
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