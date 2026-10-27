"""T-05 get_promotions (t05-get-promotions.xml): checks the pieces it chains, in Python.

1. dwl/promotions-validate-request.dwl (mirrored here);
2. the inline /v1/searchvoucher body in the flow (mirrored here);
3. dwl/promotions-response.dwl (mirrored here) on examples/upstream-searchvoucher.SYNTHETIC.json, validated against the
   owner's schema T05 0.2.0. That upstream sample is SYNTHETIC (field names from ODX_Search_Purchase_Voucher_Flow): replace
   it with a real response and re-run.

Run: python -I tests/check_t05.py   (needs: pip install jsonschema)
"""
import copy, html, json, re, sys
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
OUT_VALIDATOR = Draft202012Validator(json.loads((ROOT / "schemas/T05-get-promotions.structured-content.schema.json").read_text(encoding="utf-8")), format_checker=FormatChecker())
IN_VALIDATOR = Draft202012Validator(json.loads((ROOT / "schemas/T05-get-promotions.input.schema.json").read_text(encoding="utf-8")), format_checker=FormatChecker())
PROPS = {"property.currency": "SGD", "default.language": "en", "asset.baseUrl": "https://www.discoverasr.com"}
LANGUAGES = ["en", "zh-Hans", "zh-Hant", "fr", "de", "es", "ko", "ja", "id", "vi", "th"]
COUNTRY_NAMES = {"SG": "Singapore", "MY": "Malaysia", "ID": "Indonesia", "TH": "Thailand", "VN": "Vietnam", "JP": "Japan", "CN": "China"}


def text(v):
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    return None


# ---------------------------------------------------------------- dwl/promotions-validate-request.dwl

def validate_request(body, props=PROPS):
    ok = isinstance(body, dict)
    body = body if ok else {}
    country = (text(body.get("countryCode")) or "").upper()
    city, code, name = text(body.get("city")), text(body.get("propertyCode")), text(body.get("voucherName"))
    cats_in = body.get("voucherCategory")
    cats = []
    if isinstance(cats_in, list):
        for c in (text(x) if isinstance(x, str) else None for x in cats_in):
            if c is not None and c.lower() not in [y.lower() for y in cats]:
                cats.append(c)
    cur = text(body.get("currencyCode"))
    cur = cur.upper() if cur else None
    lang = text(body.get("language"))
    errors = [
        None if ok else "Request body must be a JSON object.",
        "countryCode is required." if country == "" else (None if re.fullmatch(r"[A-Z]{2}", country) else "countryCode must be two letters."),
        "city must be a non-blank string." if body.get("city") is not None and city is None else None,
        None if code is None or re.fullmatch(r"[0-9]{1,20}", code) else "propertyCode must be digits only.",
        "voucherName must be a non-blank string." if body.get("voucherName") is not None and name is None else None,
        ("voucherCategory must be an array." if cats_in is not None and not isinstance(cats_in, list) else
         ("voucherCategory must hold non-blank strings." if isinstance(cats_in, list) and (not cats or any((text(x) if isinstance(x, str) else None) is None for x in cats_in)) else None)),
        None if cur is None or re.fullmatch(r"[A-Z]{3}", cur) else "currencyCode must be an ISO 4217 code.",
    ]
    return {"errors": [e for e in errors if e], "request": {
        "countryCode": country, "city": city, "propertyCode": code, "voucherName": name,
        "voucherCategory": cats or None, "currency": cur or props["property.currency"],
        "language": lang if lang in LANGUAGES else props["default.language"]}}


def search_body(r, trace="trace-1"):
    out = {"messageId": trace, "language": r["language"], "voucherName": r["voucherName"], "country": r["countryCode"],
           "voucherCategory": r["voucherCategory"], "propertyCode": None if r["propertyCode"] is None else [r["propertyCode"]],
           "currency": r["currency"], "sortBy": "latest", "private": False, "channel": "mobile"}
    return {k: v for k, v in out.items() if v is not None}


# ---------------------------------------------------------------- dwl/promotions-response.dwl

def num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip():
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


def as_list(v):
    items = v if isinstance(v, list) else (v.split(",") if isinstance(v, str) else [])
    out = []
    for x in (text(i) for i in items):
        if x is not None and x not in out:
            out.append(x)
    return out


def iso_date(v):
    s = text(v)
    if s is None:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    for f in ("%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            pass
    return None


def details_url(v):
    s = text(v)
    if s is None:
        return None
    if re.match(r"^https?://", s):
        return re.sub(r"^(https?://[^/]+)/+", r"\1/", s)
    return "/" + s.lstrip("/")


def plain(v):
    s = text(v)
    if s is None:
        return None
    s = re.sub(r"(?i)</p>", "\n\n", re.sub(r"(?i)<\s*br\s*/?>", "\n", s))
    s = re.sub(r"<[^>]*>", "", s)
    for a, b in (("&nbsp;", " "), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&amp;", "&")):
        s = s.replace(a, b)
    s = re.sub(r"[ \t]*\n[ \t]*", "\n", re.sub(r"\s*\n\s*\n\s*", "\n\n", re.sub(r"[ \t]+", " ", s))).strip()
    return s or None


def money(n):
    return float(f"{n:.2f}") if n is not None else None


def voucher(v, props=PROPS):
    vid = text(v.get("voucherProgrammeCode"))
    level = (text(v.get("applicableLevel")) or "").lower()
    props_ = as_list(v.get("propertyCode"))
    countries = [c.upper() for c in as_list(v.get("countryCode")) if re.fullmatch(r"[A-Za-z]{2}", c)]
    price = num(v.get("preferredCurrencyPromoPrice"))
    price = price if price is not None else num(v.get("promoPrice"))
    p = num(v.get("points"))
    points = int(p) if p is not None and p > 0 else None
    n = num(v.get("inventory"))
    inventory = int(n) if n is not None and n >= 0 else None
    trigger = num(v.get("urgencyTrigger"))
    desc = plain(v.get("description"))
    out = {
        "id": vid, "title": text(v.get("voucherTitle")) or text(v.get("voucherEnTitle")),
        "image_url": text(v.get("imageThumbnail")), "image_alt": text(v.get("altThumbnail")),
        "scope_label": ", ".join(COUNTRY_NAMES.get(c, c) for c in countries) if level == "country" and countries else None,
        "scope_level": "property" if level == "property_specific" else ("country" if level == "country" else None),
        "property_codes": props_ or None, "country_codes": countries or None, "expiry_date": iso_date(v.get("expiryDate")),
        "details_url": details_url(v.get("voucherUrl")) or details_url(props.get("t05.detailsFallbackPath") or "/en/member/buy-experiences"),
        "category": text(v.get("category")),
        "price": None if price is None or (price <= 0 and points is not None) or price < 0 else money(price),
        "points": points, "remaining": inventory,
        "is_low_stock": inventory <= trigger if inventory is not None and trigger is not None else None,
        "description_text": None if desc is None or desc.lower() == (vid or "").lower() else desc,
        "hiddenPrivate": (text(v.get("private")) or "").lower() == "yes" or v.get("private") is True,
        "hiddenSequence": num(v.get("sequence")) if num(v.get("sequence")) is not None else 999999,
    }
    return out


def map_response(resp, req, props=PROPS):
    cats = [c.lower() for c in (req["voucherCategory"] or [])]

    def in_scope(x):
        country_ok = x["country_codes"] is None or req["countryCode"] in x["country_codes"]
        prop_ok = (req["propertyCode"] is None or x["scope_level"] == "country" or x["property_codes"] is None
                   or req["propertyCode"] in x["property_codes"])
        return country_ok and prop_ok

    items = [voucher(v, props) for v in (resp.get("voucher") or []) if isinstance(v, dict)]
    items = [x for x in items if x["id"] and x["title"] and not x["hiddenPrivate"] and in_scope(x)
             and (req["voucherName"] is None or req["voucherName"].lower() in x["title"].lower())
             and (not cats or (x["category"] or "").lower() in cats)]
    items = sorted(items, key=lambda x: x["hiddenSequence"])
    seen, vouchers = set(), []
    for x in items:
        if x["id"] in seen:
            continue
        seen.add(x["id"])
        vouchers.append({k: v for k, v in x.items() if v is not None and k not in ("hiddenPrivate", "hiddenSequence")})
    filters = None if req["voucherName"] is None and req["voucherCategory"] is None else \
        {k: v for k, v in {"voucher_name": req["voucherName"], "voucher_category": req["voucherCategory"]}.items() if v is not None}
    meta = {"country_code": req["countryCode"], "city": req["city"], "property_code": req["propertyCode"],
            "location_label": req["city"] or COUNTRY_NAMES.get(req["countryCode"], req["countryCode"]),
            "applied_filters": filters, "currency": req["currency"] if any("price" in v for v in vouchers) else None,
            "voucher_count": len(vouchers), "asset_base_url": props["asset.baseUrl"]}
    return {"meta": {k: v for k, v in meta.items() if v is not None}, "vouchers": vouchers}


def run(body, resp):
    v = validate_request(body)
    if v["errors"]:
        return {"status": 400, "errors": v["errors"]}
    return {"status": 200, "body": map_response(resp, v["request"]), "request": v["request"]}


def validate(label, doc, validator=OUT_VALIDATOR):
    errs = list(validator.iter_errors(doc))
    print(("ok   " if not errs else "FAIL ") + label)
    for e in errs[:6]:
        print("   /%s: %s" % ("/".join(str(x) for x in e.path), e.message))
    return not errs


def check(label, cond):
    print("%s %s" % ("ok  " if cond else "FAIL", label))
    return bool(cond)


def ids(res):
    return [v["id"] for v in res["body"]["vouchers"]]


upstream = json.loads((ROOT / "examples/upstream-searchvoucher.SYNTHETIC.json").read_text(encoding="utf-8"))
results = []

res = run({"countryCode": "SG"}, upstream)
results.append(validate("country only: validates against T05 0.2.0", res["body"]))
results.append(check("country only: SG vouchers in sequence order; private, untitled, JP and duplicate code dropped",
                     ids(res) == ["SGPKG", "TRIP50", "OTHERPROP"]))
m = res["body"]["meta"]
results.append(check("meta: country echoed, location label 'Singapore', count, currency SGD (some voucher has a price)",
                     m["country_code"] == "SG" and m["location_label"] == "Singapore" and m["voucher_count"] == 3
                     and m["currency"] == "SGD" and "applied_filters" not in m))
pkg, trip = res["body"]["vouchers"][0], res["body"]["vouchers"][1]
results.append(check("points-only voucher: no price, points 12000, no expiry (null upstream), description equal to code left out, country scope label",
                     "price" not in pkg and pkg["points"] == 12000 and "expiry_date" not in pkg and "description_text" not in pkg
                     and pkg["scope_label"] == "Singapore" and pkg["scope_level"] == "country"))
results.append(check("TRIP50: '//' after host collapsed, expiry date cut to YYYY-MM-DD, codes de-duplicated, price 45, low stock 3 <= 5",
                     trip["details_url"] == "https://www.discoverasr.com/en/member/buy-experiences/trip50"
                     and trip["expiry_date"] == "2027-03-31" and trip["property_codes"] == ["51052"] and trip["price"] == 45
                     and trip["remaining"] == 3 and trip["is_low_stock"] is True and "scope_label" not in trip))
results.append(check("TRIP50: description as plain text with a blank line between paragraphs, entity decoded",
                     trip["description_text"] == "Spend on any stay.\n\nValid & transferable."))
results.append(check("no voucherUrl: details_url falls back to the listing path",
                     pkg["details_url"] == "/en/member/buy-experiences"))
results.append(check("searchvoucher body: anonymous, country, currency default SGD, public only, mobile",
                     search_body(res["request"]) == {"messageId": "trace-1", "language": "en", "country": "SG", "currency": "SGD",
                                                     "sortBy": "latest", "private": False, "channel": "mobile"}))

res = run({"countryCode": "SG", "propertyCode": "51052"}, upstream)
results.append(check("propertyCode 51052: its vouchers plus country-wide ones, not another property's", ids(res) == ["SGPKG", "TRIP50"]))
results.append(check("propertyCode sent upstream as an array", search_body(res["request"])["propertyCode"] == ["51052"]))
results.append(validate("propertyCode: validates", res["body"]))

res = run({"countryCode": "sg", "voucherName": "TRIP", "voucherCategory": ["CASH", "cash"], "city": "Singapore", "currencyCode": "usd", "language": "th"}, upstream)
results.append(check("filters: name and category ignoring case, echoed; city is the location label; currency upper-cased; language passed",
                     ids(res) == ["TRIP50"] and res["body"]["meta"]["applied_filters"] == {"voucher_name": "TRIP", "voucher_category": ["CASH"]}
                     and res["body"]["meta"]["location_label"] == "Singapore" and res["body"]["meta"]["currency"] == "USD"
                     and res["request"]["language"] == "th"))
results.append(validate("filters: validates", res["body"]))

res = run({"countryCode": "SG", "voucherCategory": ["unknown"]}, upstream)
results.append(check("unknown category: zero vouchers, no currency, still 200", res["status"] == 200 and res["body"]["vouchers"] == []
                     and res["body"]["meta"]["voucher_count"] == 0 and "currency" not in res["body"]["meta"]))
results.append(validate("zero vouchers: validates", res["body"]))
res = run({"countryCode": "JP"}, {"voucher": []})
results.append(check("upstream 404 / empty list: zero vouchers, location label Japan", res["body"]["meta"]["location_label"] == "Japan" and res["body"]["vouchers"] == []))

results.append(validate("input schema accepts the full example", {"countryCode": "SG", "city": "Singapore", "propertyCode": "51052",
                        "voucherName": "flight", "voucherCategory": ["package"], "currencyCode": "SGD", "language": "en"}, IN_VALIDATOR))
for label, b in [("no countryCode", {}), ("3-letter country", {"countryCode": "SGP"}), ("propertyCode not digits", {"countryCode": "SG", "propertyCode": "A1"}),
                 ("voucherCategory not an array", {"countryCode": "SG", "voucherCategory": "package"}),
                 ("voucherCategory blank entry", {"countryCode": "SG", "voucherCategory": [" "]}),
                 ("blank voucherName", {"countryCode": "SG", "voucherName": " "}), ("bad currency", {"countryCode": "SG", "currencyCode": "DOLLAR"})]:
    results.append(check("400: " + label, run(b, upstream)["status"] == 400))

(ROOT / "examples/promotions-SG-response.sample.json").write_text(json.dumps(run({"countryCode": "SG"}, upstream)["body"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("\n%d/%d checks passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
