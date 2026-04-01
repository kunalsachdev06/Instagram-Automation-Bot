from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

from instagrapi import Client, exceptions as ig_exc
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from bot.utils import build_retryable_exceptions, is_retryable_exception, safe_sleep


def _default_challenge_handler(username: str) -> str:
    return input(f"Enter the code sent to {username}: ")


class InstagramClient:
    """Wrapper around instagrapi with session persistence and helpers."""

    def __init__(self, settings: Any, logger: Any) -> None:
        self._settings = settings
        self._logger = logger
        self.client = Client()
        if settings.proxy:
            self.client.set_proxy(settings.proxy)
        if settings.user_agent:
            self.client.set_user_agent(settings.user_agent)
        self.client.challenge_code_handler = _default_challenge_handler

        self._session_path = Path(settings.session_path)
        self._session_backup_path = self._session_path.with_name("session_backup.json")
        self._username = settings.ig_username
        self._password = settings.ig_password
        self._retryable = build_retryable_exceptions()

    def login(self) -> None:
        """Login with session reuse; use fresh accounts and clean IPs if blocked."""
        if not self._username or not self._password:
            raise ValueError("Missing IG_USERNAME or IG_PASSWORD in .env")

        session = None
        session_loaded = False
        if self._session_path.exists():
            self._logger.info("Loading session", extra={"path": str(self._session_path)})
            session = self.client.load_settings(str(self._session_path))
            session_loaded = True
        elif self._session_backup_path.exists():
            self._logger.info(
                "Loading backup session",
                extra={"path": str(self._session_backup_path)},
            )
            session = self.client.load_settings(str(self._session_backup_path))
            session_loaded = True

        if session_loaded and session:
            try:
                self.client.set_settings(session)
                self._validate_session_or_relogin(session)
            except Exception as exc:
                self._logger.warning(
                    "Session login failed, falling back to password login",
                    extra={"error": str(exc)},
                )

        if not self._is_logged_in():
            try:
                self._login_with_retry(relogin=False)
            except ig_exc.ChallengeRequired:
                self._logger.warning("Login challenge required")
                self.client.challenge_resolve(self._username)
                self._login_with_retry(relogin=False)
            except ig_exc.TwoFactorRequired:
                self._logger.warning("Two-factor required")
                code = input("Enter the 2FA code: ")
                self.client.two_factor_login(self._username, self._password, code)
            except ig_exc.ReloginAttemptExceeded:
                self._logger.error(
                    "Relogin attempts exceeded. Delete session files and retry later.",
                )
                raise
            except ig_exc.BadPassword:
                self._logger.error(
                    "Bad password or IP blocked. Use a fresh test account + clean IP.",
                )
                raise

        self._session_path.parent.mkdir(parents=True, exist_ok=True)
        self.client.dump_settings(str(self._session_path))
        self.client.dump_settings(str(self._session_backup_path))
        self._logger.info("Logged in successfully")
        min_delay = max(120, self._settings.initial_post_login_delay)
        max_delay = max(min_delay, self._settings.initial_post_login_delay + 120)
        safe_sleep(min_delay, max_delay)

    @retry(
        retry=retry_if_exception(is_retryable_exception),
        wait=wait_exponential_jitter(initial=10, max=120),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _login_with_retry(self, relogin: bool = False) -> None:
        self.client.login(self._username, self._password, relogin=relogin)

    def _is_logged_in(self) -> bool:
        try:
            self.client.get_timeline_feed()
            return True
        except ig_exc.LoginRequired:
            return False

    def _validate_session_or_relogin(self, session: dict[str, Any]) -> None:
        try:
            self.client.get_timeline_feed()
        except ig_exc.LoginRequired:
            self._logger.info("Session invalid, reauthenticating")
            old_settings = self.client.get_settings()
            self.client.set_settings({})
            if isinstance(old_settings, dict) and "uuids" in old_settings:
                self.client.set_uuids(old_settings["uuids"])
            self._login_with_retry(relogin=True)

    @retry(
        retry=retry_if_exception(is_retryable_exception),
        wait=wait_exponential_jitter(initial=5, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def user_id_from_username(self, username: str) -> int:
        try:
            return int(self.client.user_id_from_username(username))
        except self._retryable as exc:
            self._logger.warning(
                "Public lookup failed, trying private lookup",
                extra={"error": str(exc)},
            )
            if hasattr(self.client, "user_info_by_username_v1"):
                info = self.client.user_info_by_username_v1(username)
            else:
                info = self.client.user_info_by_username(username)
            user_id = getattr(info, "pk", None) or getattr(info, "id", None)
            if not user_id:
                raise
            return int(user_id)

    @retry(
        retry=retry_if_exception(is_retryable_exception),
        wait=wait_exponential_jitter(initial=5, max=180),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    def fetch_followers_batch(
        self, user_id: int, max_id: Optional[str], batch_size: int
    ) -> Tuple[Iterable[Any], Optional[str]]:
        result = None
        if hasattr(self.client, "user_followers_v1"):
            try:
                if max_id is not None:
                    result = self.client.user_followers_v1(
                        user_id, amount=batch_size, max_id=max_id
                    )
                else:
                    result = self.client.user_followers_v1(user_id, amount=batch_size)
            except TypeError:
                self._logger.warning(
                    "user_followers_v1 does not accept max_id; falling back",
                )
                result = self.client.user_followers_v1(user_id, amount=batch_size)

        if result is None and hasattr(self.client, "user_followers"):
            try:
                if max_id is not None:
                    result = self.client.user_followers(
                        user_id, amount=batch_size, max_id=max_id
                    )
                else:
                    result = self.client.user_followers(user_id, amount=batch_size)
            except TypeError:
                result = self.client.user_followers(user_id, amount=batch_size)

        if result is None and hasattr(self.client, "user_followers_gql"):
            try:
                if max_id is not None:
                    result = self.client.user_followers_gql(
                        user_id, amount=batch_size, max_id=max_id
                    )
                else:
                    result = self.client.user_followers_gql(user_id, amount=batch_size)
            except TypeError:
                self._logger.warning(
                    "user_followers_gql does not accept max_id; falling back",
                )
                result = self.client.user_followers_gql(user_id, amount=batch_size)

        if isinstance(result, tuple) and len(result) == 2:
            users, next_max_id = result
        else:
            users, next_max_id = result, None

        if isinstance(users, dict):
            users_list = list(users.values())
        else:
            users_list = list(users)

        return users_list, next_max_id

    def follow_user(self, user_id: int) -> bool:
        return bool(self.client.user_follow(user_id))

    def send_dm(self, user_id: int, message: str) -> None:
        self.client.direct_send(message, user_ids=[user_id])
