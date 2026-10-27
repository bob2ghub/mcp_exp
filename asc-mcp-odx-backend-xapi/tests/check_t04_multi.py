"""T-04 multi-room (get-multi-room-rates.xml): checks the three pieces it chains, in Python.

1. dwl/rooms-validate-request.dwl on the mobile app's multi-room body (mirror: tests/check_t04_request.py),
   plus the flow's noOfRooms check;
2. dwl/multi-room-booking-search-request.dwl, the booking search body (mirrored here);
3. dwl/room-rate-details.dwl on a three-room upstream answer (mirror: tests/check_t04.py), validated against
   schema 0.3.0. The upstream answer is built from the real 51052 response: room0 as sent, room1 and room2 cut
   down from it, the way upstream returns fewer room types for rooms with more guests.

Run: python -I tests/check_t04_multi.py   (needs: pip install jsonschema)
"""
import copy, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(script, stop):
    """The function part of a mirror script, without running its own checks."""
    ns = {"__file__": str(ROOT / "tests" / script)}
    exec((ROOT / "tests" / script).read_text(encoding="utf-8").split(stop)[0], ns)
    return ns


req_mirror = load("check_t04_request.py", "def check(")
map_mirror = load("check_t04.py", "def validate(")
validate_request = req_mirror["validate"]
map_rooms = map_mirror["map_rooms"]
VALIDATOR = map_mirror["VALIDATOR"]


def no_of_rooms_errors(body, request):
    sent = body.get("noOfRooms")
    if sent is None:
        return []
    n = sent if isinstance(sent, int) and not isinstance(sent, bool) else (int(sent) if isinstance(sent, str) and sent.isdigit() else None)
    listed = len(request["apartmentList"])
    if n is None:
        return ["noOfRooms must be a whole number."]
    if n != listed:
        return ["noOfRooms is %d but apartmentList describes %d room(s): send one apartmentList entry per room." % (n, listed)]
    return []


def booking_body(r, body, trace_id="trace-1", props=None):
    props = props or {"default.userCountry": "SG", "property.currency": "SGD"}
    rooms = r.get("apartmentList") or []
    out = {
        "messageId": trace_id, "memberId": "", "language": r.get("language"),
        "currencyCode": r.get("currency") or props.get("property.currency"),
        "promoCorpCode": body.get("promoCorpCode").strip() if isinstance(body.get("promoCorpCode"), str) else "",
        "propertyListing": False, "isModifyJourney": False,
        "propertyCode": None if r.get("propertyCode") is None else [r["propertyCode"]],
        "checkinDate": r.get("checkin"), "checkoutDate": r.get("checkout"), "voucherCode": "",
        "noOfRooms": len(rooms),
        "noOfadults": str(r.get("adults") if r.get("adults") is not None else 1),
        "noOfchildren": str(r.get("children") if r.get("children") is not None else 0),
        "minPrice": "", "maxPrice": "",
        "perNightRate": body["perNightRate"] if isinstance(body.get("perNightRate"), bool) else True,
        "apartmentList": [{"childAges": a.get("childAges") or [], "noOfadults": str(a["noOfadults"]),
                           "noOfchildren": str(a["noOfchildren"])} for a in rooms],
        "userCountry": props.get("default.userCountry") or "SG",
        "isExcludePriceStartFrom": body["isExcludePriceStartFrom"] if isinstance(body.get("isExcludePriceStartFrom"), bool) else False,
        "channel": "mobile",
    }
    return {k: v for k, v in out.items() if v is not None}


def validate(label, doc):
    errs = list(VALIDATOR.iter_errors(doc))
    print(("ok   " if not errs else "FAIL ") + label)
    for e in errs[:6]:
        print("   /%s: %s" % ("/".join(str(x) for x in e.path), e.message))
    return not errs


def check(label, cond):
    print("%s %s" % ("ok  " if cond else "FAIL", label))
    return bool(cond)


# The mobile app's own body, as the owner sent it (dates moved forward so the past-date check cannot trip).
BODY = {
    "isExcludePriceStartFrom": False, "perNightRate": False, "promoCorpCode": "", "version": "10.9", "memberId": "",
    "checkinDate": "2026-12-03", "language": "en", "platform": "iOS", "messageId": "Q7Gc8ffBQPzUHXYd",
    "currencyCode": "SGD", "checkoutDate": "2026-12-06", "propertyCode": "51052", "noOfRooms": 3,
    "apartmentList": [
        {"noOfadults": "2", "noOfchildren": "1", "childAges": [3]},
        {"noOfadults": "1", "noOfchildren": "2", "childAges": [2, 10]},
        {"noOfadults": "2", "noOfchildren": "0", "childAges": []},
    ],
}
results = []

v = validate_request(BODY)
r = v["request"]
results.append(check("validator accepts the mobile body: string guest counts, PRD names",
                     v["errors"] == [] and no_of_rooms_errors(BODY, r) == []))
results.append(check("three requested rooms, guests summed, 3 nights",
                     r["rooms"] == 3 and r["adults"] == 5 and r["children"] == 3 and r["nights"] == 3
                     and r["apartmentList"][1] == {"noOfadults": 1, "noOfchildren": 2, "childAges": [2, 10]}))

body = booking_body(r, BODY)
(ROOT / "examples/multi-room-booking-search-request.sample.json").write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
results.append(check("booking search body: noOfRooms 3, one apartmentList entry per room, strings as upstream wants",
                     body["noOfRooms"] == 3 and body["propertyCode"] == ["51052"]
                     and body["apartmentList"] == [{"childAges": [3], "noOfadults": "2", "noOfchildren": "1"},
                                                   {"childAges": [2, 10], "noOfadults": "1", "noOfchildren": "2"},
                                                   {"childAges": [], "noOfadults": "2", "noOfchildren": "0"}]
                     and body["noOfadults"] == "5" and body["noOfchildren"] == "3"))
results.append(check("pass-through flags kept, memberId / messageId / version / platform not",
                     body["perNightRate"] is False and body["isExcludePriceStartFrom"] is False
                     and body["memberId"] == "" and body["messageId"] == "trace-1"
                     and "version" not in body and "platform" not in body
                     and body["userCountry"] == "SG" and body["channel"] == "mobile"))

bad = dict(BODY, noOfRooms=2)
results.append(check("noOfRooms that disagrees with apartmentList is refused",
                     no_of_rooms_errors(bad, validate_request(bad)["request"])
                     == ["noOfRooms is 2 but apartmentList describes 3 room(s): send one apartmentList entry per room."]))
bad = {k: v for k, v in BODY.items() if k != "apartmentList"}
results.append(check("noOfRooms 3 without an apartmentList is refused, not searched as one room",
                     no_of_rooms_errors(bad, validate_request(bad)["request"]) != []))
bad = dict(BODY, apartmentList=[{"noOfadults": "1", "noOfchildren": "1", "childAges": [3, 5]}], noOfRooms=1)
results.append(check("per-room child ages are checked against that room's children",
                     "apartmentList[0].childAges cannot list more ages than noOfchildren." in validate_request(bad)["errors"]))

# Upstream's answer for three rooms: apartments[].room0 / room1 / room2.
real = json.loads((ROOT / "examples/upstream-property-details-51052.json").read_text(encoding="utf-8"))["propertyList"][0]
three = copy.deepcopy(real)
room0 = three["apartments"][0]["room0"]
three["apartments"] = [{"room0": room0, "room1": room0[1:], "room2": room0[:2]}]
out = map_rooms(three, r, {"asset.baseUrl": "https://www.discoverasr.com"})
(ROOT / "examples/multi-room-rate-details-51052-response.sample.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
results.append(validate("three-room response against schema 0.3.0", out))
rr = out["requested_rooms"]
results.append(check("requested_rooms[i] = room{i}, with that room's own guests",
                     [e["room_index"] for e in rr] == [1, 2, 3]
                     and [e["total_results"] for e in rr] == [4, 3, 2]
                     and [(e["noOfadults"], e["noOfchildren"], e["childAges"]) for e in rr]
                     == [(2, 1, [3]), (1, 2, [2, 10]), (2, 0, [])]))
results.append(check("meta: 3 rooms, guests summed, stay echoed",
                     out["meta"]["noOfRooms"] == 3 and out["meta"]["noOfadults"] == 5 and out["meta"]["noOfchildren"] == 3
                     and out["meta"]["checkin_date"] == "2026-12-03" and out["meta"]["checkout_date"] == "2026-12-06"))

# Upstream one entry per room instead of one entry holding every key.
split = copy.deepcopy(three)
split["apartments"] = [{"room0": room0}, {"room1": room0[1:]}, {"room2": room0[:2]}]
results.append(check("same result when upstream sends one apartments entry per room",
                     map_rooms(split, r, {"asset.baseUrl": "https://www.discoverasr.com"}) == out))

# Upstream answered fewer rooms than asked: the missing room is an empty tab, not an error.
short = copy.deepcopy(three)
del short["apartments"][0]["room2"]
o = map_rooms(short, r, {"asset.baseUrl": "https://www.discoverasr.com"})
results.append(validate("upstream returned no room2", o))
results.append(check("room 3 present with rooms [] and total_results 0",
                     o["requested_rooms"][2]["rooms"] == [] and o["requested_rooms"][2]["total_results"] == 0))

sys.exit(0 if all(results) else 1)
