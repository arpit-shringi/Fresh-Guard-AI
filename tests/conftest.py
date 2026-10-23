# Keep the whole suite offline and free: never call the real Groq API from tests,
# even if a GROQ_API_KEY is present in .env on the developer's machine.
import pytest

import config


@pytest.fixture(autouse=True)
def _no_real_groq_key(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")


class FakeGroqClient:
    """Mimics groq.Groq().chat.completions.create(...) and records the calls."""
    def __init__(self, content: str):
        self.content, self.calls = content, []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        msg = type("Msg", (), {"content": self.content})()
        choice = type("Choice", (), {"message": msg})()
        return type("Resp", (), {"choices": [choice]})()
