import os
from dataclasses import dataclass, field

OPENAUSTRALIA_KEY_ENV = "OPENAUSTRALIA_API_KEY"


@dataclass(frozen=True)
class Config:
    # repr=False keeps keys out of logs and tracebacks that print the config.
    openaustralia_api_key: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> "Config":
        return cls(openaustralia_api_key=_read_key(OPENAUSTRALIA_KEY_ENV))


def _read_key(name: str) -> str | None:
    # An empty value counts as missing, so a blank entry in a client config behaves like no entry.
    return os.environ.get(name, "").strip() or None
