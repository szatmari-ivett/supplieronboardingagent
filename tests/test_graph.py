from app.agent.graph import run_agent, run_agent_stream


def test_help_skips_tool_execution():
    result = run_agent("What can you help me with?", session_id="graph-help")
    assert result["metadata"]["intent"] == "help"
    assert result["metadata"]["tool"] is None
    assert "onboarding" in result["response"].lower()
    assert "I could not determine" not in result["response"]


def test_greeting_returns_help_response():
    result = run_agent("Hi! Can you help me?", session_id="graph-greeting")
    assert result["metadata"]["intent"] == "help"
    assert "Hello!" in result["response"]
    assert "I could not determine" not in result["response"]


def test_run_agent_stream_emits_progress_and_message():
    events = list(run_agent_stream("What can you help me with?", session_id="graph-stream"))
    event_types = [event["type"] for event in events]

    assert "progress" in event_types
    assert event_types[-2] == "message"
    assert event_types[-1] == "done"
    assert events[-2]["response"]


def test_duplicate_flow_runs_tool():
    result = run_agent(
        "Does supplier FreshFarm GmbH already exist? VAT DE123456789",
        session_id="graph-dup",
    )
    assert result["metadata"]["tool"] == "duplicate_check"
    assert result["metadata"]["tool_result"]["is_duplicate"] is True


def test_status_error_response_is_user_friendly():
    result = run_agent("What is the status of onboarding ONB-999?", session_id="status-missing")
    assert "ONB-999" in result["response"]
    assert "Agent execution failed" not in result["response"]
