from app.tools import service

TOOL_DEFINITIONS = [
    {
        "name": "duplicate_check",
        "description": "Check whether a supplier already exists before onboarding.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "vat_id": {"type": "string"},
                "country": {"type": "string"},
                "address": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "create_onboarding",
        "description": "Create a supplier onboarding package across procurement, ERP and cloud systems.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "country": {"type": "string"},
                "vat_id": {"type": "string"},
                "address": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["name", "country"],
        },
    },
    {
        "name": "aggregate_status",
        "description": "Return aggregated onboarding status across connected systems.",
        "parameters": {
            "type": "object",
            "properties": {"onboarding_id": {"type": "string"}},
            "required": ["onboarding_id"],
        },
    },
]


def execute_tool(name: str, arguments: dict) -> dict:
    if name == "duplicate_check":
        result = service.duplicate_check(**arguments)
        return result.model_dump(mode="json")
    if name == "create_onboarding":
        return service.create_onboarding(**arguments)
    if name == "aggregate_status":
        result = service.aggregate_status(arguments["onboarding_id"])
        return result.model_dump(mode="json")
    raise ValueError(f"Unknown tool: {name}")
