"""Runtime configuration, sourced from the environment.

Credentials are read from env vars only - never committed as module globals.
"""


def load_config():
    """Build the bot config from environment variables."""
    raise NotImplementedError
