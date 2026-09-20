"""Generate the implemented v1 contract. Does not describe unimplemented resources."""

import json
from pathlib import Path

string = {"type": "string"}
uuid = {"type": "string", "format": "uuid"}
error = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {"code": string, "message": string},
        }
    },
}
profile = {
    "type": "object",
    "properties": {
        key: string
        for key in [
            "name",
            "username",
            "role",
            "country",
            "city",
            "bio",
            "portfolio",
            "availability",
            "skills_text",
        ]
    },
}
profile["properties"].update(
    {
        key: {"type": "boolean"}
        for key in [
            "published",
            "city_public",
            "portfolio_public",
            "photo_public",
            "availability_public",
        ]
    }
)
profile["required"] = ["name", "role"]
scenario = {
    "type": "object",
    "required": [
        "platform",
        "streams",
        "low_rate",
        "midpoint_rate",
        "high_rate",
        "share",
        "deduction_percent",
        "currency",
        "market",
        "period_start",
        "period_end",
        "rate_source",
        "rate_effective_date",
        "rate_version",
    ],
    "properties": {
        key: string for key in ["platform", "market", "rate_source", "rate_version"]
    },
}
scenario["properties"].update(
    {
        key: {
            "type": "string",
            "pattern": r"^\d+(\.\d+)?$",
            "description": "Decimal string, never a binary floating point value.",
        }
        for key in [
            "low_rate",
            "midpoint_rate",
            "high_rate",
            "share",
            "deduction_percent",
            "tax_percent",
        ]
    }
)
scenario["properties"].update(
    {
        key: {"type": "string", "format": "date"}
        for key in ["period_start", "period_end", "rate_effective_date"]
    }
)
scenario["properties"].update(
    streams={"type": "integer", "minimum": 0, "maximum": 10**12},
    currency={"type": "string", "enum": ["USD", "NGN", "EUR", "GBP"]},
)
release = {
    "type": "object",
    "required": ["title", "type", "date", "stage"],
    "properties": {
        "title": string,
        "type": {"type": "string", "enum": ["Single", "EP", "Album"]},
        "date": {"type": "string", "format": "date"},
        "stage": {
            "type": "string",
            "enum": ["planning", "production", "delivery", "promotion", "released"],
        },
        "needs": string,
        "campaign_plan": string,
        "reminders_enabled": {"type": "boolean"},
    },
}
income = {
    "type": "object",
    "required": ["source", "date", "category", "currency", "amount"],
    "properties": {
        key: string
        for key in [
            "source",
            "work",
            "platform",
            "territory",
            "note",
            "amount",
            "category",
            "currency",
        ]
    },
}
income["properties"]["date"] = {"type": "string", "format": "date"}
schemas = {
    "ProfileInput": profile,
    "ScenarioInput": scenario,
    "ReleaseInput": release,
    "IncomeInput": income,
    "ConnectionInput": {
        "type": "object",
        "required": ["recipient"],
        "properties": {"recipient": uuid},
    },
    "ConnectionAction": {
        "type": "object",
        "required": ["action"],
        "properties": {
            "action": {"type": "string", "enum": ["accept", "decline", "cancel"]}
        },
    },
    "MessageInput": {
        "type": "object",
        "required": ["body"],
        "properties": {"body": {"type": "string", "minLength": 1, "maxLength": 8000}},
    },
    "GoalsInput": {
        "type": "object",
        "required": ["goals"],
        "properties": {
            "goals": {"type": "array", "maxItems": 3, "items": string},
        },
    },
    "CreditInput": {
        "type": "object",
        "required": ["work", "role", "source"],
        "properties": {
            "work": string,
            "role": string,
            "source": {"type": "string", "format": "uri"},
            "date": {"type": "string", "format": "date"},
        },
    },
    "CollaborationInput": {
        "type": "object",
        "required": ["title", "brief"],
        "properties": {
            "title": string,
            "brief": string,
            "role_needed": string,
            "genre": string,
        },
    },
    "ReportInput": {
        "type": "object",
        "required": ["reason"],
        "properties": {
            "reason": {"type": "string", "minLength": 10, "maxLength": 4000},
            "user": uuid,
            "opportunity": {"type": "integer"},
        },
    },
    "Error": error,
}
paths = {}
resources = [
    ("/profiles/me", ["get", "put"], "ProfileInput"),
    ("/connections", ["get", "post"], "ConnectionInput"),
    ("/connections/{connection_id}", ["post"], "ConnectionAction"),
    ("/connections/{connection_id}/messages", ["get", "post"], "MessageInput"),
    ("/royalty-calculations", ["get", "post"], "ScenarioInput"),
    ("/release-projects", ["get", "post"], "ReleaseInput"),
    ("/manual-income", ["get", "post"], "IncomeInput"),
    ("/notifications", ["get"], None),
    ("/royalty-statements", ["get"], None),
    ("/royalty-statements/{statement_id}/transactions", ["get"], None),
    ("/goals", ["get", "put"], "GoalsInput"),
    ("/credits", ["get", "post"], "CreditInput"),
    ("/collaborations", ["get", "post"], "CollaborationInput"),
    ("/opportunities", ["get"], None),
    ("/ai-conversations", ["get", "delete"], None),
    ("/ai-conversations/{conversation_id}", ["get", "delete"], None),
    ("/subscriptions/me", ["get"], None),
    ("/entitlements", ["get"], None),
    ("/reports", ["get", "post"], "ReportInput"),
]
for path, methods, schema in resources:
    operations = {}
    for method in methods:
        params = []
        for part in path.split("/"):
            if part.startswith("{"):
                params.append(
                    {"name": part[1:-1], "in": "path", "required": True, "schema": uuid}
                )
        if method == "get":
            params.append(
                {
                    "name": "page",
                    "in": "query",
                    "schema": {"type": "integer", "minimum": 1},
                }
            )
        else:
            params.extend(
                [
                    {
                        "name": "Idempotency-Key",
                        "in": "header",
                        "required": True,
                        "schema": uuid,
                    },
                    {
                        "name": "X-CSRFToken",
                        "in": "header",
                        "required": True,
                        "schema": string,
                    },
                ]
            )
        success = "201" if method == "post" and schema != "ConnectionAction" else "200"
        operation = {
            "summary": method.upper() + " " + path,
            "parameters": params,
            "responses": {
                success: {
                    "description": "Resource data in a data envelope. Lists include pagination with page, pages and count; page size is 20."
                }
            },
        }
        for status in (
            "400",
            "401",
            "402",
            "403",
            "404",
            "405",
            "409",
            "413",
            "415",
            "422",
            "429",
        ):
            operation["responses"][status] = {
                "description": "Request rejected",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                },
            }
        if method not in ("get", "delete") and schema:
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/" + schema}
                    }
                },
            }
        operations[method] = operation
    paths[path] = operations
contract = {
    "openapi": "3.1.0",
    "info": {
        "title": "SoundBridge implemented resource API",
        "version": "1.0.0",
        "description": "Session authentication and email verification required. Obtain the CSRF cookie through /api/auth/session. PUT replaces editable profile fields. Money is returned as decimal strings. This contract covers only routes implemented in apiv1/resource_urls.py; other workflows currently use Django forms. A 402 response means an approved plan limit was reached.",
    },
    "servers": [{"url": "/api/v1"}],
    "security": [{"sessionCookie": []}],
    "paths": paths,
    "components": {
        "securitySchemes": {
            "sessionCookie": {
                "type": "apiKey",
                "in": "cookie",
                "name": "soundbridge_session",
            }
        },
        "schemas": schemas,
    },
}
(root := Path(__file__).resolve().parents[1] / "docs").mkdir(exist_ok=True)
(root / "openapi.json").write_text(json.dumps(contract, indent=2) + "\n")
