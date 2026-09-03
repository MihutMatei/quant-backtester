"""Entrypoint: evaluate the latest bar, act once, exit.

Invoked on a schedule (cron/systemd timer) rather than run as a daemon loop.
"""


def main():
    raise NotImplementedError


if __name__ == "__main__":
    main()
