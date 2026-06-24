from app.llm.mock import MockLLM
from app.tools.registry import execute_tool


def test_duplicate_prompt_extracts_real_vat_not_supplier_word():
    plan = MockLLM().plan("Does supplier FreshFarm GmbH already exist? VAT DE123456789")
    assert plan["arguments"]["vat_id"] == "DE123456789"
    assert plan["arguments"]["name"] == "FreshFarm GmbH"


def test_duplicate_prompt_finds_existing_supplier():
    plan = MockLLM().plan("Does supplier FreshFarm GmbH already exist? VAT DE123456789")
    result = execute_tool(plan["tool"], plan["arguments"])
    assert result["is_duplicate"] is True
    assert result["candidates"][0]["score"] == 100.0


def test_start_onboarding_extracts_vat_and_name():
    plan = MockLLM().plan("Start onboarding for NewOrganic Ltd, UK, VAT GB987654321")
    assert plan["arguments"]["name"] == "NewOrganic Ltd"
    assert plan["arguments"]["vat_id"] == "GB987654321"
    assert plan["arguments"]["country"] == "GB"


def test_greeting_returns_friendly_help():
    plan = MockLLM().plan("Hi! Can you help me?")
    assert plan["intent"] == "help"
    assert plan["tool"] is None
    assert "Hello!" in plan["help_text"]
    assert "onboarding" in plan["help_text"].lower()
