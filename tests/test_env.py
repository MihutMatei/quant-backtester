"""core.env must never override a real environment variable."""
import os

from core.env import load_dotenv


def write(tmp_path, text):
    p = tmp_path / ".env"
    p.write_text(text)
    return p


def test_reads_key_values(tmp_path, monkeypatch):
    monkeypatch.delenv("SOME_KEY", raising=False)
    load_dotenv(write(tmp_path, "SOME_KEY=abc123\n"))
    assert os.environ["SOME_KEY"] == "abc123"


def test_strips_quotes(tmp_path, monkeypatch):
    monkeypatch.delenv("QUOTED", raising=False)
    load_dotenv(write(tmp_path, "QUOTED='sh h'\n"))
    assert os.environ["QUOTED"] == "sh h"


def test_skips_comments_and_blanks(tmp_path, monkeypatch):
    monkeypatch.delenv("REAL", raising=False)
    load_dotenv(write(tmp_path, "# a comment\n\n   \nREAL=yes\n"))
    assert os.environ["REAL"] == "yes"


def test_does_not_override_the_real_environment(tmp_path, monkeypatch):
    # In Docker the process gets real env vars; a stray .env must not win.
    monkeypatch.setenv("PRESET", "from-environment")
    load_dotenv(write(tmp_path, "PRESET=from-file\n"))
    assert os.environ["PRESET"] == "from-environment"


def test_missing_file_is_a_noop(tmp_path):
    assert load_dotenv(tmp_path / "nope.env") is False


def test_returns_true_when_loaded(tmp_path):
    assert load_dotenv(write(tmp_path, "X=1\n")) is True


def test_ignores_lines_without_equals(tmp_path):
    assert load_dotenv(write(tmp_path, "garbage line\n")) is True
