"""T-03 get_service_offerings: a Python copy of dwl/service-offerings.dwl, checked against schema 0.1.0.

The DataWeave is the implementation; keep this copy in step with it. It maps the real 51052 response
(examples/upstream-property-details-51052.json), writes examples/service-offerings-51052-response.sample.json and
validates it, then runs edge cases. Run: python -I tests/check_t03.py   (needs: pip install jsonschema)
"""
import copy, json, re, sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/T03-get-service-offerings.structured-content.schema.json").read_text(encoding="utf-8"))


def text(v):
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    return None


def first(o, keys):
    if not isinstance(o, dict):
        return None
    for k in keys:
        t = text(o.get(k))
        if t is not None:
            return t
    return None


def objects(v):
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def obj(v):
    return v if isinstance(v, dict) else {}


def slug(v):
    s = re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", (text(v) or "").lower()))
    return s or None


def dflt(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def skip_nulls(v):
    if isinstance(v, dict):
        return {k: skip_nulls(x) for k, x in v.items() if x is not None}
    if isinstance(v, list):
        return [skip_nulls(x) for x in v if x is not None]
    return v


def map_services(src, req, props):
    src, req = obj(src), obj(req)
    base = dflt(text(props.get("t03.assetbaseurl")), text(props.get("asset.baseUrl")), "https://www.discoverasr.com")

    def absolute(v):
        s = text(v)
        if s is None:
            return None
        if re.fullmatch(r"https?://\S+", s):
            return s
        if re.fullmatch(r"/\S*", s):
            return base + s
        return None

    def digits(v):
        s = text(v)
        return s if (s is not None and re.fullmatch(r"[0-9]+", s)) else None

    services = [s for s in ({
        "service_name": first(f, ["title", "name"]), "service_location": first(f, ["location"]),
        "operating_hours": first(f, ["operatingHours"]), "description": first(f, ["description"]),
        "thumbnail_url": first(f, ["thumbnailImage"]), "contact_number": first(f, ["contactNumber", "phone"]),
        "external_service_url": absolute(f.get("facilityUrl"))} for f in objects(obj(src.get("facilities")).get("facilityDetails")))
        if s["service_name"] is not None]
    cc = (first(src, ["countryCode"]) or "").upper()
    return skip_nulls({
        "meta": {"property_code": dflt(digits(req.get("propertyCode")), digits(src.get("propertyCode"))),
                 "property_name": dflt(first(src, ["propertyEnName", "propertyName"]), text(req.get("propertyCode"))),
                 "brand_code": dflt(slug(src.get("brand")), slug(src.get("brandName")), "ascott"),
                 "country_code": cc if re.fullmatch(r"[A-Z]{2}", cc) else None,
                 "phone": first(src, ["phone"]), "asset_base_url": base, "total_results": len(services)},
        "services": services})


def validate(name, data):
    errors = list(Draft202012Validator(SCHEMA, format_checker=FormatChecker()).iter_errors(data))
    for e in errors:
        print(f"FAIL {name}: /{'/'.join(map(str, e.path))}: {e.message[:150]}")
    if not errors:
        print(f"ok   {name} validates against T-03 0.1.0")
    return not errors


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    return cond


src = json.loads((ROOT / "examples/upstream-property-details-51052.json").read_text(encoding="utf-8"))["propertyList"][0]
PROPS = {"t03.assetbaseurl": "https://www.discoverasr.com"}
REQ = {"propertyCode": "51052", "language": "en"}
results = []
out = map_services(src, REQ, PROPS)
(ROOT / "examples/service-offerings-51052-response.sample.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
results.append(validate("51052 real payload", out))
results.append(check("8 services, in upstream order", [s["service_name"] for s in out["services"]][:3] == ["Gymnasium", "Infinity Swimming Pool", "Restaurant"] and out["meta"]["total_results"] == 8))
results.append(check("empty location / hours / facilityUrl left out", "service_location" not in out["services"][4] and "operating_hours" not in out["services"][4] and all("external_service_url" not in s for s in out["services"])))
results.append(check("meta: brand_code from brandName, country SG, phone", out["meta"]["brand_code"] == "ascott-the-residence" and out["meta"]["country_code"] == "SG" and out["meta"]["phone"] == "+65 6577 1688"))

s2 = copy.deepcopy(src)
s2["facilities"]["facilityDetails"][0]["facilityUrl"] = "/en/ascott-the-residence/singapore/ascott-raffles-place-singapore/amenities"
s2["facilities"]["facilityDetails"][1]["facilityUrl"] = "not a url"
s2["facilities"]["facilityDetails"].append({"title": "", "description": "no title"})
r = map_services(s2, REQ, PROPS)
results.append(validate("facilityUrl and untitled cases", r))
results.append(check("relative facilityUrl made absolute, junk dropped, untitled item dropped",
                     r["services"][0]["external_service_url"].startswith("https://www.discoverasr.com/en/") and "external_service_url" not in r["services"][1] and r["meta"]["total_results"] == 8))

s3 = copy.deepcopy(src); s3["facilities"] = {}
r = map_services(s3, REQ, {})
results.append(validate("no facilities, no t03 key", r))
results.append(check("empty services is valid, asset base falls back", r["services"] == [] and r["meta"]["total_results"] == 0 and r["meta"]["asset_base_url"] == "https://www.discoverasr.com"))

r = map_services(src, {}, PROPS)
results.append(validate("no request code (falls back to upstream)", r))
sys.exit(0 if all(results) else 1)
