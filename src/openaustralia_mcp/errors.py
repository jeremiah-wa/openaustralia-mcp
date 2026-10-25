"""Errors raised by the API clients. They carry no MCP types; the tool layer turns them into messages."""


class ApiClientError(Exception):
    def __init__(self, api: str) -> None:
        super().__init__(api)
        self.api = api


class MissingKeyError(ApiClientError):
    def __init__(self, api: str, env_var: str, key_url: str) -> None:
        super().__init__(api)
        self.env_var = env_var
        self.key_url = key_url


class KeyRejectedError(ApiClientError):
    def __init__(self, api: str, key_url: str) -> None:
        super().__init__(api)
        self.key_url = key_url


class ApiError(ApiClientError):
    """The API answered with an `{error: ...}` body that isn't about the key."""

    def __init__(self, api: str, message: str) -> None:
        super().__init__(api)
        self.message = message


class ApiUnavailableError(ApiClientError):
    """Network failure, timeout, non-200 status or a body that isn't JSON.

    Holds the status only: HTTP library errors include the request URL, which contains the key.
    """

    def __init__(self, api: str, status: int | None = None) -> None:
        super().__init__(api)
        self.status = status
