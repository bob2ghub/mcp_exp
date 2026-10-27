"""T-07 compare_rooms_rates (t07-compare-rooms.xml): checks the pieces it chains, in Python.

1. dwl/compare-rooms-validate-request.dwl (room codes; mirrored here) and dwl/rooms-validate-request.dwl
   (stay and guests; mirror: tests/check_t04_request.py) plus multi-rooms-validate-request's noOfRooms check
   (mirror: tests/check_t04_multi.py) and the flow's one-room check;
2. the booking search body from multi-rooms-get-rates (mirror: tests/check_t04_multi.py), to show childAges reach upstream;
3. dwl/room-rate-details.dwl (mirror: tests/check_t04.py) followed by dwl/compare-rooms-response.dwl (mirrored here)
   on the real 51052 response, validated against the owner's schema T07 0.4.0;
4. the flow's two-room rule (fewer than two rooms -> 404 NOT_ENOUGH_ROOMS).

T07 0.4.0 refers to the T-04 0.4.0 `room`, which is not in this repo yet; the T-04 0.3.0 schema is registered under the
0.4.0 id until it arrives (0.4.0 only adds an optional `is_member_rate` on rates).

Run: python -I tests/check_t07.py   (needs: pip install jsonschema)
"""
import copy, json, re, sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]


def load(script, stop):
    """The function part of a mirror script, without running its own checks."""
    ns = {"__file__": str(ROOT / "tests" / script)}
    exec((ROOT / "tests" / script).read_text(encoding="utf-8").split(stop)[0], ns)
    return ns


req_mirror = load("check_t04_request.py", "def check(")
map_mirror = load("check_t04.py", "def validate(")
multi_mirror = load("check_t04_multi.py", "\ndef validate(label")
validate_request = req_mirror["validate"]
map_rooms = map_mirror["map_rooms"]
no_of_rooms_errors = multi_mirror["no_of_rooms_errors"]
booking_body = multi_mirror["booking_body"]

SCHEMA = json.loads((ROOT / "schemas/T07-compare-rooms-rates.structured-content.schema.json").read_text(encoding="utf-8"))
T04 = json.loads((ROOT / "schemas/T04-get-room-rate-details.structured-content.schema.json").read_text(encoding="utf-8"))
REGISTRY = Registry().with_resource("urn:ascott:mcp:get_room_rate_details:structured-content:0.4.0", Resource.from_contents(T04))
VALIDATOR = Draft202012Validator(SCHEMA, registry=REGISTRY, format_checker=FormatChecker())


# ---------------------------------------------------------------- dwl/compare-rooms-validate-request.dwl

def validate_codes(body):
    body = body if isinstance(body, dict) else {}
    codes_in = body.get("roomCodes") if body.get("roomCodes") is not None else body.get("roomCategoryCodes")

    def code(v):
        return v.strip() if isinstance(v, str) and v.strip() else None

    listed = [code(v) for v in codes_in] if isinstance(codes_in, list) else []
    distinct, seen = [], set()
    for c in listed:
        if c is not None and c.upper() not in seen:
            seen.add(c.upper())
            distinct.append(c)
    errors = [
        'roomCodes must be an array of room codes, for example ["0BRCT", "1DLXT"].' if codes_in is not None and not isinstance(codes_in, list) else None,
        "roomCodes must contain only non-blank strings." if isinstance(codes_in, list) and None in listed else None,
        "Each room code must be 1 to 40 letters, digits, hyphens or underscores." if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", c) for c in distinct) else None,
        None if (not distinct or 2 <= len(distinct) <= 4) else
        "roomCodes must name 2 to 4 different room types (it names %d); omit it to compare the property's first four." % len(distinct),
    ]
    return {"errors": [e for e in errors if e], "roomCodes": distinct}


# ---------------------------------------------------------------- dwl/compare-rooms-response.dwl

def upper_of(v):
    return v.strip().upper() if isinstance(v, str) and v.strip() else ""


def objects(v):
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def compare_rooms(t04, codes_req):
    codes = codes_req.get("roomCodes") or []
    m = t04.get("meta") or {}
    requested = (objects(t04.get("requested_rooms")) or [{}])[0]
    available = objects(requested.get("rooms"))

    def matches(r, c):
        return upper_of(r.get("room_code")) == c.upper() or upper_of(r.get("room_category")) == c.upper()

    picks = []
    for c in codes:
        taken = [x["room"]["room_code"] for x in picks if x["room"] is not None]
        hit = next((r for r in available if matches(r, c) and r.get("room_code") not in taken), None)
        picks.append({"code": c, "room": hit})
    if not codes:
        rooms = available[:4]
        excluded = [{"room_code": r["room_code"], "reason": "over_limit"} for r in available[4:]]
    else:
        rooms = [x["room"] for x in picks if x["room"] is not None]
        excluded = [{"room_code": x["code"], "reason": "not_available"} for x in picks if x["room"] is None]
    meta = {
        "property_code": m.get("property_code"), "property_name": m.get("property_name"), "brand_code": m.get("brand_code"),
        "country_code": m.get("country_code"), "asset_base_url": m.get("asset_base_url"), "total_results": len(rooms),
        "currency": m.get("currency"), "checkin_date": m.get("checkin_date"), "checkout_date": m.get("checkout_date"),
        "noOfadults": requested.get("noOfadults", m.get("noOfadults")),
        "noOfchildren": requested.get("noOfchildren", m.get("noOfchildren")),
        "childAges": requested.get("childAges") or [], "price_includes_tax": m.get("price_includes_tax"),
    }
    out = {"meta": {k: v for k, v in meta.items() if v is not None}, "rooms": rooms}
    if excluded:
        out["excluded"] = excluded
    return out


def not_enough_error(out, t04, property_code):
    """The flow's two-room rule; None when the call succeeds."""
    if len(out["rooms"]) >= 2:
        return None
    with_rates = [r["room_code"] for r in (objects(t04.get("requested_rooms")) or [{}])[0].get("rooms", []) if r.get("room_code")]
    missing = [x["room_code"] for x in out.get("excluded", []) if x["reason"] == "not_available"]
    msg = "Fewer than two room types can be compared at property %s for this stay." % property_code
    if missing:
        msg += " Not available: %s." % ", ".join(missing)
    msg += (" Room types with rates: %s." % ", ".join(with_rates)) if with_rates else " No room type has a bookable rate."
    return {"code": "NOT_ENOUGH_ROOMS", "status": 404, "message": msg}


# ---------------------------------------------------------------- the whole chain

PROPS = {"asset.baseUrl": "https://www.discoverasr.com", "property.currency": "SGD"}


def run(body, src):
    codes_req = validate_codes(body)
    if codes_req["errors"]:
        return {"status": 400, "errors": codes_req["errors"]}
    v = validate_request(body)
    errors = v["errors"] + no_of_rooms_errors(v["request"])
    if errors:
        return {"status": 400, "errors": errors}
    if len(v["request"]["apartmentList"]) > 1:
        return {"status": 400, "errors": ["compare_rooms_rates compares room types for one room."]}
    t04 = map_rooms(src, v["request"], PROPS)
    out = compare_rooms(t04, codes_req)
    err = not_enough_error(out, t04, v["request"]["propertyCode"])
    if err:
        return {"status": 404, "error": err}
    return {"status": 200, "body": out, "request": v["request"]}


def validate(label, doc):
    errs = list(VALIDATOR.iter_errors(doc))
    print(("ok   " if not errs else "FAIL ") + label)
    for e in errs[:6]:
        print("   /%s: %s" % ("/".join(str(x) for x in e.path), e.message))
    return not errs


def check(label, cond):
    print("%s %s" % ("ok  " if cond else "FAIL", label))
    return bool(cond)


def codes_of(res):
    return [r["room_code"] for r in res["body"]["rooms"]]


src = json.loads((ROOT / "examples/upstream-property-details-51052.json").read_text(encoding="utf-8"))["propertyList"][0]
OWNER = {"propertyCode": "51052", "roomCodes": ["0BRXA", "1BRXB", "2BRXC"], "checkinDate": "2027-05-04",
         "checkoutDate": "2027-05-13", "noOfadults": 2, "noOfchildren": 1, "childAges": [6], "currencyCode": "SGD",
         "priceIncludesTax": True, "language": "en"}
NO_CODES = {k: v for k, v in OWNER.items() if k != "roomCodes"}
results = []

# The owner's request as sent: none of its codes is a 51052 room code.
res = run(OWNER, src)
results.append(check("owner's request: 404 NOT_ENOUGH_ROOMS naming the missing codes and 51052's real ones",
                     res["status"] == 404 and res["error"]["message"] ==
                     "Fewer than two room types can be compared at property 51052 for this stay. Not available: 0BRXA, 1BRXB, 2BRXC."
                     " Room types with rates: 0BRCT, 1DLXT, 1BRT, 1BRMT."))

# The same request with real codes: the sample response.
real = dict(OWNER, roomCodes=["1BRMT", "0brct", "1DLXT"])
res = run(real, src)
(ROOT / "examples/compare-rooms-51052-request.sample.json").write_text(json.dumps(real, indent=2) + "\n", encoding="utf-8")
(ROOT / "examples/compare-rooms-51052-response.sample.json").write_text(
    json.dumps(res["body"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
results.append(validate("real codes: response validates against T07 0.4.0", res["body"]))
results.append(check("real codes: those rooms, in request order, case ignored, no excluded",
                     codes_of(res) == ["1BRMT", "0BRCT", "1DLXT"] and "excluded" not in res["body"]))
meta = res["body"]["meta"]
results.append(check("meta: total_results 3, stay, one room's guests, childAges and the tax flag echoed",
                     meta["total_results"] == 3 and meta["checkin_date"] == "2027-05-04" and meta["checkout_date"] == "2027-05-13"
                     and meta["noOfadults"] == 2 and meta["noOfchildren"] == 1 and meta["childAges"] == [6]
                     and meta["price_includes_tax"] is True and meta["property_code"] == "51052" and meta["currency"] == "SGD"))
results.append(check("each room is the T-04 room unchanged",
                     res["body"]["rooms"][1] == map_rooms(src, res["request"], PROPS)["requested_rooms"][0]["rooms"][0]))
body = booking_body(res["request"])
results.append(check("booking search body carries childAges [6] and the 2 + 1 guests",
                     body["apartmentList"] == [{"childAges": [6], "noOfadults": "2", "noOfchildren": "1"}]
                     and body["noOfRooms"] == 1 and body["propertyCode"] == ["51052"]))

# No codes: the first four, in ranking order.
for label, b in [("no roomCodes", NO_CODES), ("roomCodes []", dict(OWNER, roomCodes=[])), ("roomCodes null", dict(OWNER, roomCodes=None))]:
    res = run(b, src)
    results.append(check(label + ": 51052's four room types, ranking order, no excluded",
                         res["status"] == 200 and codes_of(res) == ["0BRCT", "1DLXT", "1BRT", "1BRMT"] and "excluded" not in res["body"]))
results.append(validate("no roomCodes: validates", res["body"]))

# Six room types, no codes: four compared, two over_limit.
s5 = copy.deepcopy(src)
room0 = s5["apartments"][0]["room0"]
for n, code in ((5, "2BRXT"), (6, "3BRXT")):
    extra = copy.deepcopy(room0[0])
    extra.update(apartmentType=code, apartmentName="Extra %s" % code, ranking=n)
    room0.append(extra)
res = run(NO_CODES, s5)
results.append(check("six room types, no codes: first four, the rest over_limit with their own codes",
                     res["status"] == 200 and codes_of(res) == ["0BRCT", "1DLXT", "1BRT", "1BRMT"]
                     and res["body"]["excluded"] == [{"room_code": "2BRXT", "reason": "over_limit"}, {"room_code": "3BRXT", "reason": "over_limit"}]))
results.append(validate("over_limit: validates", res["body"]))

# Mixed: two found, one unknown, echoed as requested.
res = run(dict(OWNER, roomCodes=["1DLXT", "xxxx", "0BRCT"]), src)
results.append(check("mixed: two rooms compared, unknown code excluded as not_available, as written",
                     res["status"] == 200 and codes_of(res) == ["1DLXT", "0BRCT"]
                     and res["body"]["excluded"] == [{"room_code": "xxxx", "reason": "not_available"}]))
results.append(validate("mixed: validates", res["body"]))
res = run(dict(OWNER, roomCodes=["1DLXT", "XXXX"]), src)
results.append(check("only one code available: 404 NOT_ENOUGH_ROOMS", res["status"] == 404 and "Not available: XXXX." in res["error"]["message"]))

# A room that exists but has no bookable rate (only member rates left): also not_available.
s2 = copy.deepcopy(src)
for a in s2["apartments"][0]["room0"]:
    if a["apartmentType"] == "1BRT":
        for rp in a["ratePlan"]:
            rp["ratePlanTemplate"] = "AOA"
res = run(dict(OWNER, roomCodes=["1BRT", "0BRCT", "1DLXT"]), s2)
results.append(check("no bookable rate: excluded as not_available",
                     res["status"] == 200 and codes_of(res) == ["0BRCT", "1DLXT"]
                     and res["body"]["excluded"] == [{"room_code": "1BRT", "reason": "not_available"}]))
s6 = copy.deepcopy(src)
s6["apartments"][0]["room0"] = s6["apartments"][0]["room0"][:1]
res = run(NO_CODES, s6)
results.append(check("one bookable room type at the property, no codes: 404", res["status"] == 404))

# Category code (apartmentCategoryCode) as a fallback match, via the PRD name.
s3 = copy.deepcopy(src)
for a in s3["apartments"][0]["room0"]:
    a["apartmentCategoryCode"] = {"0BRCT": "CUTLER-STUDIO"}.get(a["apartmentType"], a["apartmentCategoryCode"])
res = run(dict(NO_CODES, roomCategoryCodes=["cutler-studio", "1BRT"]), s3)
results.append(check("roomCategoryCodes alias, matched by apartmentCategoryCode too",
                     res["status"] == 200 and codes_of(res) == ["0BRCT", "1BRT"]))

# Code counts and bad input.
res = run(dict(OWNER, roomCodes=["0BRCT", "0brct", "1DLXT"]), src)
results.append(check("duplicates removed ignoring case: two rooms", res["status"] == 200 and codes_of(res) == ["0BRCT", "1DLXT"]))
results.append(check("one code: 400", run(dict(OWNER, roomCodes=["0BRCT"]), src)["status"] == 400))
results.append(check("five codes: 400", run(dict(OWNER, roomCodes=["A1", "A2", "A3", "A4", "A5"]), src)["status"] == 400))
results.append(check("roomCodes not an array: 400", run(dict(OWNER, roomCodes="0BRCT"), src)["status"] == 400))
results.append(check("roomCodes with a blank entry: 400", run(dict(OWNER, roomCodes=["0BRCT", " "]), src)["status"] == 400))
results.append(check("a space in a code: 400", run(dict(OWNER, roomCodes=["1 Bedroom", "0BRCT"]), src)["status"] == 400))
res = run(dict(OWNER, roomCodes=["0BRCT", "1DLXT"], checkinDate="2020-01-01"), src)
results.append(check("past check-in: 400 from the T-04 validator", res["status"] == 400 and "past" in " ".join(res["errors"])))
two = dict(OWNER, roomCodes=["1BRT", "0BRCT"], noOfRooms=2,
           apartmentList=[{"noOfadults": 2, "noOfchildren": 1, "childAges": [6]}, {"noOfadults": 1, "noOfchildren": 0}])
results.append(check("two apartmentList rooms: 400 (one room's guests only)", run(two, src)["status"] == 400))
one = dict(NO_CODES, apartmentList=[{"noOfadults": "2", "noOfchildren": "1", "childAges": [6]}], noOfRooms=1)
res = run(one, src)
results.append(check("mobile body with one apartmentList entry: 200, guests from it",
                     res["status"] == 200 and res["body"]["meta"]["noOfadults"] == 2 and res["body"]["meta"]["childAges"] == [6]))

# The minimal request (owner, 2026-10-28): propertyCode and roomCodes only, every other field defaulted.
res = run({"propertyCode": "51052", "roomCodes": ["0BRXA", "1BRXB"]}, src)
results.append(check("minimal request, owner's codes: 404 NOT_ENOUGH_ROOMS listing 51052's codes",
                     res["status"] == 404 and res["error"]["message"] ==
                     "Fewer than two room types can be compared at property 51052 for this stay. Not available: 0BRXA, 1BRXB."
                     " Room types with rates: 0BRCT, 1DLXT, 1BRT, 1BRMT."))
res = run({"propertyCode": "51052", "roomCodes": ["0BRCT", "1DLXT"]}, src)
results.append(check("minimal request, real codes: 200 with the default stay and guests, no childAges or tax flag",
                     res["status"] == 200 and codes_of(res) == ["0BRCT", "1DLXT"] and res["body"]["meta"]["noOfadults"] == 2
                     and res["body"]["meta"]["noOfchildren"] == 0 and res["body"]["meta"]["childAges"] == []
                     and "price_includes_tax" not in res["body"]["meta"] and res["body"]["meta"]["currency"] == "SGD"))
results.append(validate("minimal request, real codes: validates", res["body"]))

print("\n%d/%d checks passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
