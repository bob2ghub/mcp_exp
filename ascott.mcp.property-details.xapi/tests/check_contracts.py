"""Static checks that need no Mule runtime.

- Every Mule XML file and log4j2.xml is well-formed.
- Every JSON file under src/main/resources and examples/ parses.
- The example requests match schemas/request.schema.json.
- examples/response.sample.json matches schemas/structured-content.schema.json.

Run: python -I tests/check_contracts.py   (needs: pip install jsonschema)
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "src/main/resources/schemas"
EXAMPLES = ROOT / "examples"
ok = True


def fail(msg):
    global ok
    ok = False
    print("FAIL", msg)


for xml_file in sorted((ROOT / "src/main").rglob("*.xml")):
    try:
        ET.parse(xml_file)
        print("ok   xml ", xml_file.relative_to(ROOT))
    except ET.ParseError as e:
        fail(f"{xml_file.relative_to(ROOT)}: {e}")

for json_file in sorted(list((ROOT / "src/main/resources").rglob("*.json")) + list(EXAMPLES.glob("*.json"))):
    try:
        json.loads(json_file.read_text(encoding="utf-8"))
    except ValueError as e:
        fail(f"{json_file.relative_to(ROOT)}: {e}")


def check(schema_file, example_file):
    schema = json.loads((SCHEMAS / schema_file).read_text(encoding="utf-8"))
    data = json.loads((EXAMPLES / example_file).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data), key=lambda e: list(e.path))
    for e in errors:
        fail(f"{example_file}: /{'/'.join(map(str, e.path))}: {e.message}")
    if not errors:
        print("ok   json", example_file, "against", schema_file)


check("request.schema.json", "request.json")
check("request.schema.json", "request-by-name.json")
check("structured-content.schema.json", "response.sample.json")
sys.exit(0 if ok else 1)
