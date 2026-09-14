from mardik.config import Settings
from mardik.llm import get_llm


def _settings(**overrides: str) -> Settings:
    base = dict(
        azure_endpoint="https://example.test/openai/v1",
        azure_api_key="test-key",
        azure_model="test-model",
        otel_endpoint="http://localhost:4317",
        service_name="mardik",
        environment="test",
        log_level="INFO",
        langfuse_host="http://localhost:3000",
        langfuse_public_key="",
        langfuse_secret_key="",
    )
    base.update(overrides)
    return Settings(**base)


def test_get_llm_targets_the_configured_openai_compatible_endpoint():
    llm = get_llm(_settings())

    assert llm.openai_api_base == "https://example.test/openai/v1"
    assert llm.model_name == "test-model"
