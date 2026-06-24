from app.agent.state import AgentState
from app.llm.factory import get_llm_provider
from app.tools.registry import execute_tool

_FALLBACK_RESPONSE = (
    "I didn't quite catch that. I can help with duplicate checks, starting onboarding, "
    "or checking status. Try a supplier name, VAT ID, or onboarding ID such as ONB-001."
)


def router_node(state: AgentState) -> AgentState:
    llm = get_llm_provider()
    history = state.get("messages", [])
    plan = llm.plan(state["user_message"], history=history)
    return {
        **state,
        "plan": plan,
        "tool_name": plan.get("tool"),
        "tool_args": plan.get("arguments", {}),
        "awaiting_confirmation": plan.get("requires_confirmation", False),
    }


def act_node(state: AgentState) -> AgentState:
    plan = state.get("plan", {})
    if plan.get("intent") == "help" and not plan.get("tool"):
        return {**state, "tool_result": {"help_text": plan.get("help_text", "")}}

    tool_name = state.get("tool_name")
    if not tool_name:
        return state

    try:
        result = execute_tool(tool_name, state.get("tool_args", {}))
    except ValueError as exc:
        result = {"status": "error", "message": str(exc)}
    return {**state, "tool_result": result}


def respond_node(state: AgentState) -> AgentState:
    plan = state.get("plan", {})
    tool_result = state.get("tool_result") or {}

    if plan.get("intent") == "help":
        response = plan.get("help_text") or tool_result.get("help_text") or _FALLBACK_RESPONSE
    elif state.get("tool_name") == "duplicate_check":
        response = _format_duplicate_response(tool_result)
    elif state.get("tool_name") == "create_onboarding":
        response = _format_onboarding_response(tool_result)
    elif state.get("tool_name") == "aggregate_status":
        response = _format_status_response(tool_result)
    else:
        response = _FALLBACK_RESPONSE

    metadata = {
        "intent": plan.get("intent"),
        "tool": state.get("tool_name"),
        "awaiting_confirmation": state.get("awaiting_confirmation", False),
        "tool_result": tool_result,
    }

    messages = list(state.get("messages", []))
    messages.append({"role": "user", "content": state["user_message"]})
    messages.append({"role": "assistant", "content": response})

    return {**state, "response_text": response, "metadata": metadata, "messages": messages}


def _format_duplicate_response(result: dict) -> str:
    candidates = result.get("candidates", [])
    if not candidates:
        return "No existing supplier match was found. You can proceed with a new supplier record request."

    lines = ["Duplicate check results:"]
    for candidate in candidates[:3]:
        supplier = candidate["supplier"]
        lines.append(
            f"- {supplier['name']} ({supplier.get('vat_id', 'no VAT')}): "
            f"{candidate['score']}% ({candidate['match_type']}) -> {candidate['recommendation']}. "
            f"Reason: {candidate['reason']}."
        )

    if result.get("is_duplicate"):
        lines.append("Recommendation: treat this as an existing supplier unless business rules say otherwise.")
    elif result.get("requires_review"):
        lines.append("Recommendation: route to human review before creating a new supplier record.")
    else:
        lines.append("Recommendation: no strong duplicate found.")
    return "\n".join(lines)


def _format_phase(phase: object) -> str:
    if phase is None:
        return "unknown"
    if hasattr(phase, "value"):
        return str(phase.value)
    return str(phase)


def _format_onboarding_response(result: dict) -> str:
    if result.get("requires_confirmation") or result.get("status") == "blocked":
        return (
            "Potential duplicate detected before onboarding. "
            "Please review the matches and reply with 'yes confirm' if you want to continue."
        )
    if result.get("status") == "existing":
        onboarding = result.get("onboarding", {})
        return (
            f"Onboarding {onboarding.get('id', 'N/A')} already exists for "
            f"{onboarding.get('supplier', {}).get('name', 'supplier')}. "
            f"Current phase: {_format_phase(onboarding.get('phase'))}."
        )
    if result.get("status") == "partial_failure":
        onboarding = result.get("onboarding", {})
        return (
            f"Onboarding {onboarding.get('id', 'N/A')} was partially created. "
            f"Procurement package exists, but ERP sync failed: {result.get('error')}. "
            "Status will be degraded until retry succeeds."
        )
    onboarding = result.get("onboarding", {})
    package = result.get("package", {})
    supplier_name = onboarding.get("supplier", {}).get("name", "supplier")
    return (
        f"Onboarding {onboarding.get('id', 'N/A')} started for {supplier_name}. "
        f"Procurement package {package.get('package_id', 'N/A')} created. "
        f"Current phase: {_format_phase(onboarding.get('phase'))}."
    )


def _format_status_response(result: dict) -> str:
    if result.get("status") == "error":
        return result.get("message", "Status lookup failed.")

    lines = [
        result.get("summary", "Status unavailable."),
        f"Health: {_format_phase(result.get('health', 'unknown'))}.",
        "System breakdown:",
    ]
    for system in result.get("systems", []):
        availability = "available" if system.get("available", True) else "unavailable"
        lines.append(f"- {system['system']}: {system['status']} ({availability})")
    next_steps = result.get("next_steps") or []
    if next_steps:
        lines.append("Next steps:")
        lines.extend(f"- {step}" for step in next_steps)
    return "\n".join(lines)
