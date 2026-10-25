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
