from __future__ import annotations

from types import SimpleNamespace

from trace_topology.backends import OpenAIBackend


def test_openai_backend_classify_returns_model_label(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.responses = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            assert kwargs["model"] == "gpt-5-mini"
            assert "Classify relation between reasoning steps" in kwargs["instructions"]
            return SimpleNamespace(output_text="covalent")

    monkeypatch.setattr("trace_topology.backends._import_openai", lambda: FakeClient)
    backend = OpenAIBackend(api_key="test-key")

    result = backend.classify("A because B", "Therefore C")

    assert result.bond_type == "covalent"
    assert result.confidence == 0.7
    assert result.reason == "openai:gpt-5-mini"


def test_openai_backend_classify_falls_back_on_unparseable_output(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.responses = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            return SimpleNamespace(output_text="not sure")

    monkeypatch.setattr("trace_topology.backends._import_openai", lambda: FakeClient)
    backend = OpenAIBackend(model="gpt-5.2", api_key="test-key")

    result = backend.classify("A", "B")

    assert result.bond_type == "vanderwaals"
    assert result.confidence == 0.2
    assert result.reason == "openai:gpt-5.2:fallback"
