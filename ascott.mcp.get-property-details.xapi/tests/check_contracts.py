"""Validate the example requests and the example response against the JSON schemas.

The response example is what dwl/map-structured-content.dwl should produce for
examples/upstream-property-details.sample.json + examples/upstream-property-pois.sample.json.
Run: python -I tests/check_contracts.py   (needs: pip install jsonschema)
"""
import json, sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "src/main/resources/schemas"
EXAMPLES = ROOT / "examples"

def check(schema_file, example_file):
    schema = json.loads((SCHEMAS / schema_file).read_text(encoding="utf-8"))
    data = json.loads((EXAMPLES / example_file).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data), key=lambda e: list(e.path))
    for e in errors:
        print(f"FAIL {example_file}: /{'/'.join(map(str, e.path))}: {e.message}")
    if not errors:
        print(f"ok   {example_file}")
    return not errors

results = [
    check("get-property-details-request.schema.json", "request.json"),
    check("get-property-details-request.schema.json", "request-by-name.json"),
    check("structured-content.schema.json", "response.sample.json"),
    check("service-offerings-structured-content.schema.json", "service-offerings-response.sample.json"),
    check("room-rate-details-structured-content.schema.json", "room-rate-details-response.sample.json"),
]
sys.exit(0 if all(results) else 1)
