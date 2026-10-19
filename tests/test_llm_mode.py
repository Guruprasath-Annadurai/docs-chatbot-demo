"""LLM mode, with the OpenAI call replaced so no key or network is needed."""

import pytest

from app.rag import ChatService
from tests.conftest import SAMPLE_DOCS, make_settings


@pytest.fixture
def llm_service(tmp_path, embedder):
    svc = ChatService(make_settings(tmp_path, answer_mode="auto", openai_api_key="sk-test"), embedder)
    svc.ingest_folder(SAMPLE_DOCS)
    return svc


def test_llm_answer_keeps_only_cited_sources(llm_service, monkeypatch):
    monkeypatch.setattr(llm_service, "_ask_llm", lambda q, hits: "We open at 8:00 am on Sundays [1].")
    answer = llm_service.ask("What time do you open on Sunday?")
    assert answer.mode == "llm" and answer.found
    assert [s.source for s in answer.sources] == ["opening-hours.pdf"]


def test_llm_i_dont_know_is_passed_through(llm_service, monkeypatch):
    monkeypatch.setattr(llm_service, "_ask_llm", lambda q, hits: "I don't know")
    answer = llm_service.ask("Do you sell pizza by the slice?")
    assert not answer.found and answer.sources == []


def test_llm_not_called_when_nothing_matches(llm_service, monkeypatch):
    def boom(q, hits):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(llm_service, "_ask_llm", boom)
    assert not llm_service.ask("What is the capital of France?").found


def test_llm_failure_falls_back_to_extractive(llm_service, monkeypatch):
    def fail(q, hits):
        raise ConnectionError("no network")

    monkeypatch.setattr(llm_service, "_ask_llm", fail)
    answer = llm_service.ask("Do you deliver?")
    assert answer.found and answer.mode == "extractive"
    assert "couldn't be reached" in answer.note
