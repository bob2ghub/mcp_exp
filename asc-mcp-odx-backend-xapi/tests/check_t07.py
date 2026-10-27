"""T-07 compare_rooms_rates (get-room-rates.xml): checks the pieces it chains, in Python.

1. dwl/compare-rooms-validate-request.dwl (room codes; mirrored here) and dwl/rooms-validate-request.dwl
   (stay and guests; mirror: tests/check_t04_request.py) plus multi-rooms-validate-request's noOfRooms check
   (mirror: tests/check_t04_multi.py);
2. the booking search body from multi-rooms-get-rates (mirror: tests/check_t04_multi.py), to show childAges reach upstream;
3. dwl/room-rate-details.dwl (mirror: tests/check_t04.py) followed by dwl/compare-rooms-response.dwl (mirrored here)
   on the real 51052 response, validated against the draft schema T07 0.1.0;
4. the flow's 404 rule (every requested code not_found -> ROOM_CODES_NOT_FOUND, listing the property's codes).

Run: python -I tests/check_t07.py   (needs: pip install jsonschema)
"""
import copy, json, re, sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

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
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


# ---------------------------------------------------------------- dwl/compare-rooms-validate-request.dwl

def validate_codes(body, max_codes=4):
    body = body if isinstance(body, dict) else {}
    codes_in = body.get("roomCodes") if body.get("roomCodes") is not None else body.get("roomCategoryCodes")

    def code(v):
        return v.strip().upper() if isinstance(v, str) and v.strip() else None

    listed = [code(v) for v in codes_in] if isinstance(codes_in, list) else []
    distinct = []
    for c in listed:
        if c is not None and c not in distinct:
            distinct.append(c)
    errors = [
        'roomCodes must be an array of room codes, for example ["0BRCT", "1DLXT"].' if codes_in is not None and not isinstance(codes_in, list) else None,
        "roomCodes must contain only non-blank strings." if isinstance(codes_in, list) and None in listed else None,
        "Each room code must be 1 to 40 letters, digits, hyphens or underscores." if any(not re.fullmatch(r"[A-Z0-9_-]{1,40}", c) for c in distinct) else None,
    ]
    return {"errors": [e for e in errors if e], "roomCodes": distinct[:max_codes], "droppedRoomCodes": distinct[max_codes:]}


# ---------------------------------------------------------------- dwl/compare-rooms-response.dwl

def upper_of(v):
    return v.strip().upper() if isinstance(v, str) and v.strip() else ""


def objects(v):
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def compare_rooms(t04, codes_req, src):
    codes = codes_req.get("roomCodes") or []
    dropped = codes_req.get("droppedRoomCodes") or []

    def matches(r, c):
        return upper_of(r.get("room_code")) == c or upper_of(r.get("room_category")) == c

    def code_index(r):
        return next((i for i, c in enumerate(codes) if matches(r, c)), 999999)

    requested = []
    for rr in objects(t04.get("requested_rooms")):
        rooms = objects(rr.get("rooms"))
        kept = rooms if not codes else sorted([r for r in rooms if code_index(r) != 999999], key=code_index)
        e = {k: v for k, v in rr.items() if k not in ("total_results", "rooms")}
        e.update(total_results=len(kept), rooms=kept)
        requested.append(e)

    upstream = [a for e in objects(src.get("apartments")) for v in e.values() for a in objects(v)]

    def at_property(c):
        return any(upper_of(a.get("apartmentType")) == c or upper_of(a.get("apartmentCategoryCode")) == c for a in upstream)

    def returned(c):
        return any(matches(r, c) for rr in requested for r in rr["rooms"])

    meta = dict(t04.get("meta") or {})
    if codes:
        meta["room_codes"] = codes
    if dropped:
        meta["dropped_room_codes"] = dropped
    return {
        "meta": meta,
        "requested_rooms": requested,
        "excluded": [{"room_code": c, "reason": "no_available_rate" if at_property(c) else "not_found"}
                     for c in codes if not returned(c)],
    }


def not_found_error(out, codes_req, src, property_code):
    """The flow's 404 rule; None when the call succeeds."""
    codes = codes_req["roomCodes"]
    if not codes or len([x for x in out["excluded"] if x["reason"] == "not_found"]) != len(codes):
        return None
    known = []
    for e in objects(src.get("apartments")):
        for v in e.values():
            for a in objects(v):
                t = a.get("apartmentType") or ""
                if t and t not in known:
                    known.append(t)
    msg = "None of the room codes %s exists at property %s." % (", ".join(codes), property_code)
    if known:
        msg += " Its room codes are %s." % ", ".join(known)
    return {"code": "ROOM_CODES_NOT_FOUND", "status": 404, "message": msg}


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
    out = compare_rooms(map_rooms(src, v["request"], PROPS), codes_req, src)
    err = not_found_error(out, codes_req, src, v["request"]["propertyCode"])
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


def codes_of(res, i=0):
    return [r["room_code"] for r in res["body"]["requested_rooms"][i]["rooms"]]


src = json.loads((ROOT / "examples/upstream-property-details-51052.json").read_text(encoding="utf-8"))["propertyList"][0]
OWNER = {"propertyCode": "51052", "roomCodes": ["0BRXA", "1BRXB", "2BRXC"], "checkinDate": "2027-05-04",
         "checkoutDate": "2027-05-13", "noOfadults": 2, "noOfchildren": 1, "childAges": [6], "currencyCode": "SGD",
         "priceIncludesTax": True, "language": "en"}
results = []

# The owner's request as sent: none of its codes is a 51052 room code.
res = run(OWNER, src)
results.append(check("owner's request: 404 ROOM_CODES_NOT_FOUND naming 51052's real codes",
                     res["status"] == 404 and res["error"]["message"] ==
                     "None of the room codes 0BRXA, 1BRXB, 2BRXC exists at property 51052. Its room codes are 0BRCT, 1DLXT, 1BRT, 1BRMT."))

# The same request with real codes: the sample response.
real = dict(OWNER, roomCodes=["1BRMT", "0brct", "1DLXT"])
res = run(real, src)
(ROOT / "examples/compare-rooms-51052-request.sample.json").write_text(json.dumps(real, indent=2) + "\n", encoding="utf-8")
(ROOT / "examples/compare-rooms-51052-response.sample.json").write_text(
    json.dumps(res["body"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
results.append(validate("real codes: response validates against T07 0.1.0", res["body"]))
results.append(check("real codes: only those rooms, in request order, case ignored",
                     codes_of(res) == ["1BRMT", "0BRCT", "1DLXT"] and res["body"]["requested_rooms"][0]["total_results"] == 3))
results.append(check("real codes: meta echoes codes upper case, stay, guests; excluded is []",
                     res["body"]["meta"]["room_codes"] == ["1BRMT", "0BRCT", "1DLXT"]
                     and res["body"]["meta"]["checkin_date"] == "2027-05-04" and res["body"]["meta"]["noOfchildren"] == 1
                     and res["body"]["meta"]["price_includes_tax"] is True and res["body"]["excluded"] == []))
results.append(check("real codes: the room's childAges echoed",
                     res["body"]["requested_rooms"][0]["childAges"] == [6]))
body = booking_body(res["request"])
results.append(check("booking search body carries childAges [6] and the 2 + 1 guests",
                     body["apartmentList"] == [{"childAges": [6], "noOfadults": "2", "noOfchildren": "1"}]
                     and body["noOfRooms"] == 1 and body["propertyCode"] == ["51052"]))

# No codes: every room, identical to T-04.
for label, b in [("no roomCodes", {k: v for k, v in OWNER.items() if k != "roomCodes"}),
                 ("roomCodes []", dict(OWNER, roomCodes=[])), ("roomCodes null", dict(OWNER, roomCodes=None))]:
    res = run(b, src)
    results.append(check(label + ": every room in ranking order, no room_codes, excluded []",
                         res["status"] == 200 and codes_of(res) == ["0BRCT", "1DLXT", "1BRT", "1BRMT"]
                         and "room_codes" not in res["body"]["meta"] and res["body"]["excluded"] == []))
    results.append(validate(label + ": validates", res["body"]))

# Mixed: one found, one unknown.
res = run(dict(OWNER, roomCodes=["1DLXT", "XXXX"]), src)
results.append(check("mixed: 200 with the known room, unknown code excluded as not_found",
                     res["status"] == 200 and codes_of(res) == ["1DLXT"]
                     and res["body"]["excluded"] == [{"room_code": "XXXX", "reason": "not_found"}]))
results.append(validate("mixed: validates", res["body"]))

# A room that exists but has no bookable rate (only member / test rates left).
s2 = copy.deepcopy(src)
for a in s2["apartments"][0]["room0"]:
    if a["apartmentType"] == "1BRT":
        for rp in a["ratePlan"]:
            rp["ratePlanTemplate"] = "AOA"
res = run(dict(OWNER, roomCodes=["1BRT", "0BRCT"]), s2)
results.append(check("no bookable rate: 200, code excluded as no_available_rate",
                     res["status"] == 200 and codes_of(res) == ["0BRCT"]
                     and res["body"]["excluded"] == [{"room_code": "1BRT", "reason": "no_available_rate"}]))
res = run(dict(OWNER, roomCodes=["1BRT"]), s2)
results.append(check("only code has no bookable rate: still 200 (not 404), rooms []",
                     res["status"] == 200 and res["body"]["requested_rooms"][0]["rooms"] == []
                     and res["body"]["excluded"][0]["reason"] == "no_available_rate"))
results.append(validate("no bookable rate: validates", res["body"]))

# Category code (apartmentCategoryCode) as a fallback match.
res = run(dict(OWNER, roomCodes=["1 Bedroom"]), src)
results.append(check("a space is not a valid code: 400", res["status"] == 400))
s3 = copy.deepcopy(src)
for a in s3["apartments"][0]["room0"]:
    a["apartmentCategoryCode"] = {"0BRCT": "CUTLER-STUDIO"}.get(a["apartmentType"], a["apartmentCategoryCode"])
no_codes = {k: v for k, v in OWNER.items() if k != "roomCodes"}
res = run(dict(no_codes, roomCategoryCodes=["cutler-studio", "1BRT"]), s3)
results.append(check("roomCategoryCodes alias, matched by apartmentCategoryCode too",
                     res["status"] == 200 and codes_of(res) == ["0BRCT", "1BRT"]))

# Duplicates and a 5th code.
res = run(dict(OWNER, roomCodes=["0BRCT", "0brct", "1DLXT", "1BRT", "1BRMT", "ZZZ"]), src)
results.append(check("duplicates removed, 5th code dropped and echoed",
                     res["status"] == 200 and res["body"]["meta"]["room_codes"] == ["0BRCT", "1DLXT", "1BRT", "1BRMT"]
                     and res["body"]["meta"]["dropped_room_codes"] == ["ZZZ"]))
results.append(validate("dropped codes: validates", res["body"]))

# Bad input.
results.append(check("roomCodes not an array: 400", run(dict(OWNER, roomCodes="0BRCT"), src)["status"] == 400))
results.append(check("roomCodes with a blank entry: 400", run(dict(OWNER, roomCodes=["0BRCT", " "]), src)["status"] == 400))
res = run(dict(OWNER, roomCodes=["0BRCT"], checkinDate="2020-01-01"), src)
results.append(check("past check-in: 400 from the T-04 validator", res["status"] == 400 and "past" in " ".join(res["errors"])))
# The T-04 validator compares childAges with noOfchildren per apartmentList entry only, not for the top-level shape.
res = run(dict(OWNER, roomCodes=["0BRCT"], apartmentList=[{"noOfadults": 2, "noOfchildren": 0, "childAges": [6]}]), src)
results.append(check("apartmentList entry with more childAges than children: 400", res["status"] == 400))

# Two requested rooms (mobile app body): each keeps only the requested codes.
s4 = copy.deepcopy(src)
room0 = s4["apartments"][0]["room0"]
s4["apartments"] = [{"room0": room0, "room1": room0[1:3]}]
two = dict(OWNER, roomCodes=["1BRT", "0BRCT"], noOfRooms=2,
           apartmentList=[{"noOfadults": 2, "noOfchildren": 1, "childAges": [6]}, {"noOfadults": 1, "noOfchildren": 0}])
res = run(two, s4)
results.append(check("two rooms: room 1 has both codes, room 2 only 1BRT; nothing excluded",
                     res["status"] == 200 and codes_of(res, 0) == ["1BRT", "0BRCT"] and codes_of(res, 1) == ["1BRT"]
                     and res["body"]["excluded"] == []))
results.append(validate("two rooms: validates", res["body"]))

print("\n%d/%d checks passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
