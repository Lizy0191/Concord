"""Offline bootstrap of schema types when the npm registry is unavailable.

This handles only the constructs present in this project's generated OpenAPI. It fails
on unsupported schema constructs. Normal regeneration uses openapi-typescript (pnpm generate).
Never edit generated DTOs by hand.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "frontend/openapi.json").read_text())


def convert(node):
    if "$ref" in node:
        return 'components["schemas"][' + json.dumps(node["$ref"].split("/")[-1]) + "]"
    if "const" in node:
        return json.dumps(node["const"])
    if "enum" in node:
        return " | ".join(json.dumps(x) for x in node["enum"])
    for key, separator in [("anyOf", " | "), ("oneOf", " | "), ("allOf", " & ")]:
        if key in node:
            return "(" + separator.join(convert(x) for x in node[key]) + ")"
    kind = node.get("type")
    if kind == "array":
        if "prefixItems" in node:
            return "[" + ", ".join(convert(x) for x in node["prefixItems"]) + "]"
        return f"Array<{convert(node.get('items', {}))}>"
    if kind == "object" or "properties" in node:
        if "properties" not in node:
            extra = node.get("additionalProperties", {})
            return f"Record<string, {convert(extra) if isinstance(extra, dict) else 'unknown'}>"
        required = set(node.get("required", []))
        fields = [
            json.dumps(k) + ("" if k in required else "?") + ": " + convert(v) + ";"
            for k, v in node["properties"].items()
        ]
        return "{ " + " ".join(fields) + " }"
    return {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "null": "null",
        None: "unknown",
    }[kind]


lines = [
    "// Generated from frontend/openapi.json. DO NOT EDIT. Regenerate: pnpm generate.",
    "export interface components { schemas: {",
]
for name, schema in sorted(SCHEMA["components"]["schemas"].items()):
    lines.append("  " + json.dumps(name) + ": " + convert(schema) + ";")
lines.append("}; }")
(ROOT / "frontend/src/api/schema.ts").write_text("\n".join(lines) + "\n")
print("Generated", len(SCHEMA["components"]["schemas"]), "schema bindings")
