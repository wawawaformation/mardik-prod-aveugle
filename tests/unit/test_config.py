from mardik.config import load_settings


def test_load_settings_defaults_langfuse_to_disabled(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    settings = load_settings()

    assert settings.langfuse_host == "http://localhost:3000"
    assert settings.langfuse_public_key == ""
    assert settings.langfuse_secret_key == ""


def test_load_settings_reads_langfuse_env_vars(monkeypatch):
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse.example")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    settings = load_settings()

    assert settings.langfuse_host == "http://langfuse.example"
    assert settings.langfuse_public_key == "pk-test"
    assert settings.langfuse_secret_key == "sk-test"
