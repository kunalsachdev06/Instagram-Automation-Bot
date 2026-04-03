from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any, List

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


class SeleniumInstagramClient:
    """Selenium-based Instagram client for UI automation."""

    def __init__(self, settings: Any, logger: Any) -> None:
        self._settings = settings
        self._logger = logger
        options = ChromeOptions()
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")
        options.add_argument("--start-maximized")
        options.add_argument("--profile-directory=Profile 1")
        if settings.user_agent:
            options.add_argument(f"--user-agent={settings.user_agent}")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 20)
        self.driver.maximize_window()

    def login(self) -> None:
        print("USING SELENIUM CLIENT")
        self._logger.info("Opening Instagram login page")
        self.driver.get("https://www.instagram.com/accounts/login/")
        time.sleep(5)

        print("Current URL:", self.driver.current_url)
        print("Page Title:", self.driver.title)

        WebDriverWait(self.driver, 20).until(
            ec.presence_of_element_located((By.TAG_NAME, "body"))
        )

        inputs = self.driver.find_elements(By.TAG_NAME, "input")
        print(f"Inputs detected: {len(inputs)}")
        if len(inputs) == 0:
            self.driver.refresh()
            time.sleep(5)
            inputs = self.driver.find_elements(By.TAG_NAME, "input")

        visible_inputs = []
        for el in inputs:
            if el.is_displayed() and el.is_enabled():
                visible_inputs.append(el)

        username_input = None
        password_input = None

        for el in visible_inputs:
            input_type = (el.get_attribute("type") or "").lower()
            if input_type == "password":
                password_input = el
            elif input_type in ["text", "email"]:
                username_input = el

        if not username_input or not password_input:
            raise Exception("Visible login inputs not found")

        self.driver.execute_script("arguments[0].scrollIntoView(true);", username_input)
        self.driver.execute_script("arguments[0].click();", username_input)

        print("Using visible login inputs only")

        username_input.send_keys(self._settings.ig_username)
        self._human_pause()
        try:
            self.safe_click(password_input)
            password_input.send_keys(self._settings.ig_password)
        except Exception:
            self.driver.execute_script(
                "arguments[0].value = arguments[1];",
                password_input,
                self._settings.ig_password,
            )

        WebDriverWait(self.driver, 10).until(
            lambda d: (username_input.get_attribute("value") or "")
            and (password_input.get_attribute("value") or "")
        )

        self._logger.info(
            "Credentials filled. Click Log In manually; waiting for login to complete..."
        )
        try:
            WebDriverWait(self.driver, 90).until(
                lambda d: d.find_elements(By.XPATH, "//nav")
                or d.find_elements(By.XPATH, "//p[@id='slfErrorAlert']")
                or d.find_elements(By.XPATH, "//input[@name='verificationCode']")
                or d.find_elements(By.XPATH, "//div[contains(text(),'Save your login info')]")
                or "accounts/login" not in d.current_url
            )
        except TimeoutException:
            self._handle_login_failure("Login did not complete in time")
            raise

        try:
            WebDriverWait(self.driver, 45).until(
                lambda d: d.find_elements(By.XPATH, "//nav")
                or d.find_elements(By.XPATH, "//p[@id='slfErrorAlert']")
                or d.find_elements(By.XPATH, "//input[@name='verificationCode']")
                or d.find_elements(By.XPATH, "//h2[contains(text(),'Page isn')]")
                or "accounts/login" not in d.current_url
            )
        except TimeoutException:
            self._handle_login_failure("Login failed or timed out")
            raise

        if self.driver.find_elements(By.XPATH, "//p[@id='slfErrorAlert']"):
            self._handle_login_failure("Login error displayed on page")
            raise RuntimeError("Instagram login error displayed")

        if self.driver.find_elements(By.XPATH, "//h2[contains(text(),'Page isn')]"):
            self._handle_login_failure("Page isn't available after login")
            raise RuntimeError("Instagram redirected to unavailable page")

        self.driver.get("https://www.instagram.com/")
        assert "instagram.com" in self.driver.current_url

        try:
            self.wait.until(
                ec.presence_of_element_located((By.XPATH, "//input[@name='verificationCode']"))
            )
            self._logger.error("Instagram triggered verification (manual intervention needed)")
            input("Complete verification manually and press Enter...")
        except TimeoutException:
            pass

        self._logger.info("Current URL", extra={"url": self.driver.current_url})

        self.handle_popups()
        self._logger.info("Logged in successfully")

    def _handle_login_failure(self, message: str) -> None:
        self._logger.error(
            message,
            extra={"url": self.driver.current_url, "title": self.driver.title},
        )
        try:
            Path(self._settings.logs_dir).mkdir(parents=True, exist_ok=True)
            screenshot_path = Path(self._settings.logs_dir) / "login_failure.png"
            self.driver.save_screenshot(str(screenshot_path))
            html_path = Path(self._settings.logs_dir) / "login_failure.html"
            html_path.write_text(self.driver.page_source, encoding="utf-8")
            self._logger.error(
                "Saved login diagnostics",
                extra={"screenshot": str(screenshot_path), "html": str(html_path)},
            )
        except Exception as exc:
            self._logger.error("Failed to save login diagnostics", extra={"error": str(exc)})

        input("Login failed. Inspect the browser, then press Enter to exit...")

    def get_followers(self, username: str) -> List[str]:
        self._logger.info("Opening profile", extra={"target": username})
        self.driver.get(f"https://www.instagram.com/{username}/")
        WebDriverWait(self.driver, 10).until(
            ec.presence_of_element_located((By.XPATH, "//header"))
        )
        assert "instagram.com" in self.driver.current_url
        self._logger.info("Current URL", extra={"url": self.driver.current_url})

        scroll_box = None
        for attempt in range(3):
            try:
                followers_btn = WebDriverWait(self.driver, 10).until(
                    ec.element_to_be_clickable(
                        (By.XPATH, "//a[contains(@href,'/followers')]")
                    )
                )
                WebDriverWait(self.driver, 10).until(
                    ec.visibility_of(followers_btn)
                )
                self.safe_click(followers_btn)
                scroll_box = WebDriverWait(self.driver, 15).until(
                    lambda d: d.find_elements(
                        By.XPATH, "//div[@role='dialog']//div[contains(@class,'_aano')]"
                    )
                    or d.find_elements(By.XPATH, "//div[@role='dialog']")
                )
                if isinstance(scroll_box, list):
                    scroll_box = scroll_box[0]
                break
            except TimeoutException:
                self._logger.warning(
                    "Retrying followers modal",
                    extra={"attempt": attempt + 1},
                )

        if scroll_box is None:
            self._logger.warning("Fallback to direct URL")
            self.driver.get(f"https://www.instagram.com/{username}/followers/")
            time.sleep(5)
            try:
                scroll_box = WebDriverWait(self.driver, 15).until(
                    lambda d: d.find_elements(
                        By.XPATH, "//div[@role='dialog']//div[contains(@class,'_aano')]"
                    )
                    or d.find_elements(By.XPATH, "//div[@role='dialog']")
                )
                if isinstance(scroll_box, list):
                    scroll_box = scroll_box[0]
            except TimeoutException as exc:
                self._logger.error(
                    "Followers modal failed to open",
                    extra={"url": self.driver.current_url},
                )
                snippet = self.driver.page_source[:1000]
                self._logger.error("Page source snippet", extra={"snippet": snippet})
                try:
                    Path(self._settings.logs_dir).mkdir(parents=True, exist_ok=True)
                    screenshot_path = Path(self._settings.logs_dir) / "followers_failure.png"
                    self.driver.save_screenshot(str(screenshot_path))
                    html_path = Path(self._settings.logs_dir) / "followers_failure.html"
                    html_path.write_text(self.driver.page_source, encoding="utf-8")
                    self._logger.error(
                        "Saved followers diagnostics",
                        extra={"screenshot": str(screenshot_path), "html": str(html_path)},
                    )
                except Exception as diag_exc:
                    self._logger.error(
                        "Failed to save followers diagnostics",
                        extra={"error": str(diag_exc)},
                    )
                raise exc

        self._logger.info("Modal opened successfully")

        try:
            WebDriverWait(self.driver, 10).until(
                lambda d: d.find_elements(By.XPATH, "//div[@role='dialog']//div[contains(@class,'_aano')]//li")
                or d.find_elements(By.XPATH, "//div[@role='dialog']//div[contains(@class,'_aano')]//span")
                or d.find_elements(By.XPATH, "//div[@role='dialog']//li")
            )
        except TimeoutException:
            self._logger.warning("Followers list did not render in time")

        self.scroll_modal(scroll_box)
        try:
            active_modal = self.driver.find_element(By.XPATH, "//div[@role='dialog']")
            usernames = self._collect_usernames(active_modal)
        except StaleElementReferenceException:
            active_modal = self.driver.find_element(By.XPATH, "//div[@role='dialog']")
            usernames = self._collect_usernames(active_modal)
        if not usernames:
            if scroll_box.find_elements(By.XPATH, ".//*[contains(text(),'This Account is Private')]"):
                self._logger.warning("Target account is private; followers not accessible")
            else:
                self._logger.warning("No followers found in modal")
        self._logger.info("Followers collected", extra={"count": len(usernames)})
        return usernames

    def follow_user(self, username: str) -> None:
        self._logger.info("Following user", extra={"user": username})
        self.driver.get(f"https://www.instagram.com/{username}/")
        self.wait_for_element((By.XPATH, "//header"))
        assert "instagram.com" in self.driver.current_url

        try:
            button = self.wait_for_element(
                (By.XPATH, "//button[normalize-space()='Follow']"),
                timeout=8,
            )
            WebDriverWait(self.driver, 10).until(ec.visibility_of(button))
            self.safe_click(button)
            self._human_pause()
        except TimeoutException:
            self._logger.info("Already following or follow button not available", extra={"user": username})

    def send_dm(self, username: str, message: str) -> None:
        self._logger.info("Sending DM", extra={"user": username})
        self.driver.get(f"https://www.instagram.com/{username}/")
        self.wait_for_element((By.XPATH, "//header"))
        assert "instagram.com" in self.driver.current_url

        try:
            message_button = self.wait_for_element(
                (By.XPATH, "//button[normalize-space()='Message']"),
                timeout=8,
            )
            WebDriverWait(self.driver, 10).until(ec.visibility_of(message_button))
            self.safe_click(message_button)
        except TimeoutException:
            self._logger.warning("DM disabled or message button not found", extra={"user": username})
            return

        try:
            textbox = self.wait.until(
                ec.presence_of_element_located((By.XPATH, "//div[@role='textbox']"))
            )
            textbox.click()
            textbox.send_keys(message)
            textbox.send_keys(Keys.ENTER)
            self._human_pause()
        except TimeoutException:
            self._logger.warning("DM textbox not found", extra={"user": username})

    def wait_for_element(self, locator: tuple[str, str], timeout: int = 20):
        return WebDriverWait(self.driver, timeout).until(ec.presence_of_element_located(locator))

    def scroll_modal(self, modal, max_scrolls: int = 60) -> None:
        last_count = 0
        for _ in range(max_scrolls):
            try:
                scroll_box = self.driver.find_element(
                    By.XPATH,
                    "//div[@role='dialog']//div[contains(@class,'_aano')]",
                )
                users = scroll_box.find_elements(By.XPATH, ".//li")
            except StaleElementReferenceException:
                time.sleep(1)
                continue
            except Exception:
                try:
                    scroll_box = self.driver.find_element(By.XPATH, "//div[@role='dialog']")
                    users = scroll_box.find_elements(By.XPATH, ".//li")
                except Exception:
                    time.sleep(1)
                    continue

            self._logger.info("Followers loaded", extra={"count": len(users)})
            if len(users) == last_count:
                break
            last_count = len(users)
            self.driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight",
                scroll_box,
            )
            time.sleep(random.uniform(2, 4))

    def _collect_usernames(self, modal) -> List[str]:
        anchors = modal.find_elements(By.XPATH, ".//a[contains(@href,'/')]")
        usernames: List[str] = []

        for anchor in anchors:
            href = anchor.get_attribute("href") or ""
            if href and "instagram.com" in href:
                username = href.split("/")[-2]
                if username and username not in usernames:
                    usernames.append(username)

        return usernames

    def handle_popups(self) -> None:
        for _ in range(3):
            try:
                btn = WebDriverWait(self.driver, 5).until(
                    ec.element_to_be_clickable((By.XPATH, "//button[text()='Not Now']"))
                )
                self.safe_click(btn)
                self._human_pause()
            except TimeoutException:
                break

    def safe_click(self, element) -> None:
        try:
            element.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", element)

    def _human_pause(self) -> None:
        delay = random.uniform(2, 6)
        time.sleep(delay)
