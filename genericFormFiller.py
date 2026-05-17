from questionCache import QuestionCache
import debugLogger


class GenericFormFiller:
    def __init__(self, cache: QuestionCache):
        self.cache = cache

    def get_label(self, page, element):
        try:
            label = element.get_attribute("aria-label")
            if label:
                return label.strip()

            el_id = element.get_attribute("id")
            if el_id:
                label_el = page.query_selector(f"label[for='{el_id}']")
                if label_el:
                    return label_el.inner_text().strip().split('\n')[0].strip()

            placeholder = element.get_attribute("placeholder")
            if placeholder:
                return placeholder.strip()

            name = element.get_attribute("name")
            if name:
                return name.replace("_", " ").replace("-", " ").strip()

            label_text = page.evaluate("""
                (el) => {
                    // check preceding siblings at each level
                    let node = el;
                    for (let i = 0; i < 6; i++) {
                        let sib = node.previousElementSibling;
                        while (sib) {
                            const t = sib.innerText?.trim();
                            if (t) return t;
                            sib = sib.previousElementSibling;
                        }
                        // also check for label/legend inside parent
                        const parent = node.parentElement;
                        if (!parent) break;
                        const found = parent.querySelector('label, legend, [class*="label"], [class*="heading"]');
                        if (found && found !== el && found.innerText.trim()) return found.innerText.trim();
                        node = parent;
                    }
                    return null;
                }
            """, element)
            if label_text:
                return label_text.split('\n')[0].strip()

        except Exception:
            pass
        return None

    def match_profile(self, label):
        label_lower = label.lower()

        if "year" in label_lower or "experience" in label_lower:
            tech_map = self.cache.profile.get("years_experience_technologies", {})
            for tech, years in tech_map.items():
                if tech.lower() in label_lower:
                    return years
            return self.cache.profile.get("years_experience_default", "1")

        first = self.cache.profile.get("first_name", "")
        last  = self.cache.profile.get("last_name", "")
        mapping = {
            "first name":          first,
            "last name":           last,
            "full name":           f"{first} {last}".strip(),
            "name":                f"{first} {last}".strip(),
            "email":               self.cache.profile.get("email"),
            "phone":               self.cache.profile.get("phone"),
            "city":                self.cache.profile.get("location"),
            "location":            self.cache.profile.get("location"),
            "linkedin":            self.cache.profile.get("linkedin"),
            "website":             self.cache.profile.get("website") or self.cache.profile.get("linkedin"),
            "portfolio":           self.cache.profile.get("website") or self.cache.profile.get("linkedin"),
            "github":              self.cache.profile.get("github") or self.cache.profile.get("linkedin"),
            "salary":              self.cache.profile.get("desired_salary"),
            "compensation":        self.cache.profile.get("desired_salary"),
            "work authorization":  self.cache.profile.get("work_authorization"),
            "sponsorship":         self.cache.profile.get("requires_sponsorship"),
            "gender":              self.cache.profile.get("gender"),
            "veteran":             self.cache.profile.get("veteran_status"),
            "disability":          self.cache.profile.get("disability_status"),
        }

        for keyword, value in mapping.items():
            if keyword in label_lower and value:
                return value

        return None

    def _fill_text_inputs(self, page):
        selectors = "input[type='text'], input[type='email'], input[type='tel'], input[type='number'], input[type='url'], input:not([type])"

        # pass 1: fill regular fields, collect location fields for after
        # location autocomplete causes React re-renders that stale other element refs
        location_els = []
        try:
            for el in page.query_selector_all(selectors):
                try:
                    if not el.is_visible():
                        continue
                    current = el.input_value().strip()
                    if current:
                        continue
                    label = self.get_label(page, el)
                    if not label:
                        continue
                    placeholder = el.get_attribute("placeholder") or ""
                    is_location = any(w in label.lower() for w in ["city", "location", "where"]) \
                        or placeholder in ("Start typing...", "Search location", "Search for location")
                    if is_location:
                        location_els.append(label)
                        continue
                    answer = self.match_profile(label)
                    if answer:
                        el.click()
                        el.fill(str(answer))
                        debugLogger.log(f"[Generic] Text filled: {label} → {answer}")
                    else:
                        debugLogger.log(f"[Generic] No profile match for: {label}")
                except Exception as e:
                    debugLogger.log(f"[Generic] Error on field: {e}")
        except Exception as e:
            debugLogger.log(f"[Generic] Text inputs error: {e}")

        # pass 2: fill location fields — re-query fresh refs after pass 1
        location = self.cache.profile.get("location")
        if location_els and location:
            try:
                for el in page.query_selector_all(selectors):
                    try:
                        if not el.is_visible():
                            continue
                        if el.input_value().strip():
                            continue
                        placeholder = el.get_attribute("placeholder") or ""
                        label = self.get_label(page, el) or ""
                        is_location = any(w in label.lower() for w in ["city", "location", "where"]) \
                            or placeholder in ("Start typing...", "Search location", "Search for location")
                        if is_location:
                            self._fill_location_autocomplete(page, el, location)
                    except Exception as e:
                        debugLogger.log(f"[Generic] Location field error: {e}")
            except Exception as e:
                debugLogger.log(f"[Generic] Location pass error: {e}")

    def _fill_selects(self, page):
        try:
            for el in page.query_selector_all("select"):
                if not el.is_visible():
                    continue
                current = el.input_value()
                if current.strip():
                    continue
                label = self.get_label(page, el)
                if not label:
                    continue
                opts = page.evaluate("""
                    (el) => Array.from(el.options)
                        .filter(o => o.value)
                        .map(o => ({value: o.value, text: o.text.trim()}))
                """, el)
                option_values = [o["value"] for o in opts]
                answer = self.match_profile(label) or self.cache.get_answer(label, options=option_values)
                if answer:
                    ans_lower = str(answer).lower()
                    match = next((o["value"] for o in opts if o["value"].lower() == ans_lower), None)
                    if not match:
                        match = next((o["value"] for o in opts if o["text"].lower() == ans_lower), None)
                    if match:
                        el.select_option(value=match)
                        debugLogger.log(f"[Generic] Select set: {label} → {match}")
                    else:
                        debugLogger.log(f"[Generic] No option match for: {label} answer={answer}")
                else:
                    debugLogger.log(f"[Generic] No answer for select: {label}")
        except Exception as e:
            debugLogger.log(f"[Generic] Selects error: {e}")

    def _fill_textareas(self, page):
        try:
            for el in page.query_selector_all("textarea"):
                if not el.is_visible():
                    continue
                if el.input_value().strip():
                    continue
                label = self.get_label(page, el)
                if not label:
                    continue
                answer = self.match_profile(label)
                if answer:
                    el.fill(str(answer))
                    debugLogger.log(f"[Generic] Textarea filled: {label}")
                else:
                    debugLogger.log(f"[Generic] No profile match for textarea: {label}")
        except Exception as e:
            debugLogger.log(f"[Generic] Textareas error: {e}")

    def _upload_resume(self, page):
        import os
        resume_path = os.path.abspath("resume.pdf")
        if not os.path.exists(resume_path):
            debugLogger.log("[Generic] resume.pdf not found — skipping upload")
            return
        try:
            for el in page.query_selector_all("input[type='file']"):
                if not el.is_visible():
                    continue
                el.set_input_files(resume_path)
                page.wait_for_timeout(2000)
                debugLogger.log("[Generic] Resume uploaded")
                break  # only upload to the first file input (resume slot)
        except Exception as e:
            debugLogger.log(f"[Generic] Resume upload error: {e}")

    def _scan_required_fields(self, page):
        """Log all required fields and their current fill status before filling."""
        try:
            fields = page.evaluate("""
                () => [...document.querySelectorAll('[required], [aria-required="true"]')]
                    .filter(el => el.offsetParent !== null)
                    .map(el => ({
                        tag:      el.tagName,
                        label:    el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('name') || '',
                        filled:   !!(el.value && el.value.trim()),
                        type:     el.getAttribute('type') || ''
                    }))
            """)
            debugLogger.log(f"[Generic] Required fields found: {len(fields)}")
            for f in fields:
                status = "filled" if f["filled"] else "EMPTY"
                debugLogger.log(f"[Generic]   [{status}] {f['tag']} type={f['type']} label={f['label']}")
        except Exception as e:
            debugLogger.log(f"[Generic] Required field scan error: {e}")

    def _fill_location_autocomplete(self, page, el, value):
        """Type a location value and select the first suggestion from the dropdown."""
        try:
            el.click()
            el.fill("")
            page.wait_for_timeout(300)
            el.type(value, delay=50)
            page.wait_for_timeout(1500)
            suggestion = (
                page.query_selector("[role='option']")
                or page.query_selector("[role='listbox'] li")
                or page.query_selector("[role='listbox'] [role='option']")
                or page.query_selector(".autocomplete__option")
                or page.query_selector("[class*='option']")
            )
            if suggestion:
                suggestion.click()
                page.wait_for_timeout(500)
                debugLogger.log(f"[Generic] Location autocomplete filled: {value}")
                return True

            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            debugLogger.log(f"[Generic] No autocomplete suggestion for: {value}")
            return False
        except Exception as e:
            debugLogger.log(f"[Generic] Location autocomplete error: {e}")
            return False

    def _log_unfilled_required(self, page):
        try:
            unfilled = page.evaluate("""
                () => [...document.querySelectorAll('[required], [aria-required="true"]')]
                    .filter(el => el.offsetParent !== null && (!el.value || el.value === ''))
                    .map(el => el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('name') || el.tagName)
                    .filter(Boolean)
            """)
            for field in unfilled:
                debugLogger.log(f"[Generic] Still empty required field: {field}")
        except Exception:
            pass

    def fill_page(self, page):
        try:
            self._scan_required_fields(page)
            self._upload_resume(page)
            self._fill_text_inputs(page)
            self._fill_selects(page)
            self._fill_textareas(page)
            page.wait_for_timeout(1000)
            self._log_unfilled_required(page)
            return True
        except Exception as e:
            debugLogger.log(f"[Generic] Fill page error: {e}")
            return False
