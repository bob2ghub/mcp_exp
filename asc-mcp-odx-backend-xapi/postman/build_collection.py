"""Builds postman/ascott-mcp-xapi.postman_collection.json: every tool call of the ODX backend xAPI, with tests.

Run: python -I postman/build_collection.py
Edit the request lists below, not the JSON. Each request names the status it expects and, for a 200, the tool whose
schema it answers with: the test script then checks the schema's required top-level and meta keys
(read from schemas/*.json when the collection is built) plus any request-specific checks.
"""
import json, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "postman/ascott-mcp-xapi.postman_collection.json"

SCHEMAS = {
    "T02": "T02-get-property-details", "T03": "T03-get-service-offerings", "T04": "T04-get-room-rate-details",
    "T05": "T05-get-promotions", "T06": "T06-compare-properties", "T07": "T07-compare-rooms-rates", "T08": "T08-create-booking",
}


def required_keys(tool):
    s = json.loads((ROOT / "schemas" / (SCHEMAS[tool] + ".structured-content.schema.json")).read_text(encoding="utf-8"))
    meta = (s["properties"].get("meta") or {}).get("required") or []
    return s.get("required") or [], meta


def stable_id(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "ascott-mcp-xapi/" + "/".join(parts)))


def request(name, path, body, status, tool=None, checks=(), desc="", raw=None, query=None):
    return {"name": name, "path": path, "body": body, "status": status, "tool": tool, "checks": list(checks),
            "desc": desc, "raw": raw, "query": query}


STAY = {"checkinDate": "{{checkin}}", "checkoutDate": "{{checkout}}"}

# ---------------------------------------------------------------------------------------------------- T-02
T02 = ("T-02 get_property_details", "POST /api/v1/property-details: one property's details (output schema 0.6.0, input schema 0.2.0).", [
    request("200 by property code, full stay", "/api/v1/property-details",
            dict(propertyCode="{{propertyCode}}", **STAY, noOfadults=2, noOfchildren=0, currencyCode="{{currency}}", language="en"),
            200, "T02",
            ["pm.expect(b.property_code).to.eql(pm.collectionVariables.get('propertyCode'));",
             "pm.expect(b.pricing).to.be.an('object');"]),
    request("200 with children (childAges, one per child)", "/api/v1/property-details",
            dict(propertyCode="{{propertyCode}}", **STAY, noOfadults=2, noOfchildren=2, childAges=[4, 9], currencyCode="{{currency}}"),
            200, "T02"),
    request("200 property code only (server defaults)", "/api/v1/property-details", {"propertyCode": "{{propertyCode}}"}, 200, "T02"),
    request("200 with nearby POIs (maxPois 5)", "/api/v1/property-details", {"propertyCode": "{{propertyCode}}", "maxPois": 5}, 200, "T02",
            desc="nearby[] is [] while the POI mock answers 400 for real codes. maxPois is server-side, not in the input schema."),
    request("400 no propertyCode", "/api/v1/property-details", {"noOfadults": 2}, 400),
    request("400 propertyName only (not in input schema 0.2.0)", "/api/v1/property-details", {"propertyName": "{{propertyName}}"}, 400),
    request("400 children without childAges", "/api/v1/property-details",
            {"propertyCode": "{{propertyCode}}", "noOfchildren": 1}, 400),
    request("400 checkout before checkin", "/api/v1/property-details",
            {"propertyCode": "{{propertyCode}}", "checkinDate": "2030-01-10", "checkoutDate": "2030-01-09"}, 400),
    request("400 invalid JSON", "/api/v1/property-details", None, 400, raw='{"propertyCode": "51052",'),
    request("404 unknown property", "/api/v1/property-details", {"propertyCode": "99999999"}, 404),
])

# ---------------------------------------------------------------------------------------------------- T-03
T03 = ("T-03 get_service_offerings", "POST /api/v1/service-offerings: the property's facilities as services (schema 0.1.0).", [
    request("200 by property code", "/api/v1/service-offerings", {"propertyCode": "{{propertyCode}}", "language": "en"}, 200, "T03",
            ["pm.expect(b.services).to.be.an('array');",
             "pm.expect(b.meta.total_results).to.eql(b.services.length);"]),
    request("200 default language", "/api/v1/service-offerings", {"propertyCode": "{{propertyCode}}"}, 200, "T03"),
    request("400 missing propertyCode", "/api/v1/service-offerings", {"propertyName": "{{propertyName}}"}, 400),
    request("400 non-numeric propertyCode", "/api/v1/service-offerings", {"propertyCode": "SG-001"}, 400),
    request("400 bad language", "/api/v1/service-offerings", {"propertyCode": "{{propertyCode}}", "language": "english"}, 400),
    request("400 invalid JSON", "/api/v1/service-offerings", None, 400, raw='{"propertyCode": "51052",'),
    request("404 unknown property", "/api/v1/service-offerings", {"propertyCode": "00000"}, 404),
])

# ---------------------------------------------------------------------------------------------------- T-04
MOBILE3 = {"isExcludePriceStartFrom": False, "perNightRate": False, "promoCorpCode": "", "version": "10.9", "memberId": "",
           "checkinDate": "{{checkin}}", "language": "en", "platform": "iOS", "messageId": "Q7Gc8ffBQPzUHXYd", "currencyCode": "SGD",
           "checkoutDate": "{{checkout}}", "propertyCode": "{{propertyCode}}", "noOfRooms": 3,
           "apartmentList": [{"noOfadults": "2", "noOfchildren": "1", "childAges": [3]},
                             {"noOfadults": "1", "noOfchildren": "2", "childAges": [2, 10]},
                             {"noOfadults": "2", "noOfchildren": "0", "childAges": []}]}
SAVE_PICK = [
    "// Chain: keep the first room + rate and the first two room codes for T-07 and T-08.",
    "const rooms = (b.requested_rooms[0] || {}).rooms || [];",
    "if (rooms.length) {",
    "  pm.collectionVariables.set('pickedRoomCode', rooms[0].room_code);",
    "  pm.collectionVariables.set('pickedRatePlanCode', rooms[0].rate_plans[0].rate_plan_code);",
    "  pm.collectionVariables.set('pickedRoomCode2', (rooms[1] || rooms[0]).room_code);",
    "}",
]
T04 = ("T-04 get_room_rate_details (one or several rooms)",
       "POST /api/v1/multi-room-details: every room type and bookable rate, one list per requested room (schema 0.3.0).", [
    request("200 single room, PRD names (saves picks for T-07 / T-08)", "/api/v1/multi-room-details",
            dict(propertyCode="{{propertyCode}}", **STAY, noOfadults=2, noOfchildren=1, childAges=[6], currencyCode="SGD",
                 priceIncludesTax=True, language="en"), 200, "T04",
            ["pm.expect(b.requested_rooms).to.have.lengthOf(1);",
             "pm.expect(b.requested_rooms[0].childAges).to.eql([6]);"] + SAVE_PICK),
    request("200 single room, short T-04 names", "/api/v1/multi-room-details",
            {"propertyCode": "{{propertyCode}}", "checkin": "{{checkin}}", "checkout": "{{checkout}}", "adults": 2, "children": 1,
             "childAges": [4], "currency": "SGD"}, 200, "T04"),
    request("200 property code only (server defaults)", "/api/v1/multi-room-details", {"propertyCode": "{{propertyCode}}"}, 200, "T04"),
    request("200 single room, mobile body (one apartmentList entry)", "/api/v1/multi-room-details",
            dict(propertyCode="{{propertyCode}}", **STAY, currencyCode="SGD", language="en", noOfRooms=1,
                 apartmentList=[{"noOfadults": "2", "noOfchildren": "0", "childAges": []}]), 200, "T04"),
    request("200 three rooms (mobile app body)", "/api/v1/multi-room-details", MOBILE3, 200, "T04",
            ["pm.expect(b.requested_rooms).to.have.lengthOf(3);",
             "pm.expect(b.requested_rooms.map(r => r.room_index)).to.eql([1, 2, 3]);",
             "pm.expect(b.meta.noOfRooms).to.eql(3);"]),
    request("200 three rooms, raw upstream property (room0..room2)", "/api/v1/multi-room-details", MOBILE3, 200,
            checks=["pm.expect(b).to.have.property('apartments');"], query="format=raw",
            desc="Unmapped propertyList[0], to see what upstream sent for each room{i}."),
    request("400 noOfRooms does not match apartmentList", "/api/v1/multi-room-details", dict(MOBILE3, noOfRooms=2), 400),
    request("400 more child ages than children", "/api/v1/multi-room-details",
            dict(MOBILE3, apartmentList=[{"noOfadults": "2", "noOfchildren": "1", "childAges": [3, 5]}], noOfRooms=1), 400),
    request("400 rooms 2 without apartmentList", "/api/v1/multi-room-details",
            {"propertyCode": "{{propertyCode}}", "checkin": "{{checkin}}", "checkout": "{{checkout}}", "adults": 2, "rooms": 2}, 400),
    request("400 check-in in the past", "/api/v1/multi-room-details", {"propertyCode": "{{propertyCode}}", "checkinDate": "2020-01-01"}, 400),
    request("404 unknown property", "/api/v1/multi-room-details", {"propertyCode": "99999999"}, 404, checks=["errorCode('ROOMS_NOT_FOUND');"]),
])

# ---------------------------------------------------------------------------------------------------- T-05
T05 = ("T-05 get_promotions (vouchers)", "POST /api/v1/promotions: vouchers from /v1/searchvoucher (schema 0.2.0). Zero vouchers is a 200.", [
    request("200 country only", "/api/v1/promotions", {"countryCode": "{{countryCode}}"}, 200, "T05",
            ["pm.expect(b.meta.voucher_count).to.eql(b.vouchers.length);",
             "b.vouchers.forEach(v => pm.expect(v).to.include.keys('id', 'title', 'details_url'));",
             "if (b.vouchers.some(v => 'price' in v)) pm.expect(b.meta).to.have.property('currency');"]),
    request("200 property in context", "/api/v1/promotions", {"countryCode": "{{countryCode}}", "propertyCode": "{{propertyCode}}"}, 200, "T05",
            ["pm.expect(b.meta.property_code).to.eql(pm.collectionVariables.get('propertyCode'));"]),
    request("200 city", "/api/v1/promotions", {"countryCode": "{{countryCode}}", "city": "Singapore"}, 200, "T05",
            ["pm.expect(b.meta.location_label).to.eql('Singapore');"]),
    request("200 name and category filters", "/api/v1/promotions",
            {"countryCode": "{{countryCode}}", "voucherName": "stay", "voucherCategory": ["package", "cash"], "currencyCode": "SGD", "language": "en"},
            200, "T05", ["pm.expect(b.meta.applied_filters.voucher_name).to.eql('stay');"]),
    request("200 unknown category (zero vouchers, not an error)", "/api/v1/promotions",
            {"countryCode": "{{countryCode}}", "voucherCategory": ["no-such-category"]}, 200, "T05",
            ["pm.expect(b.vouchers).to.eql([]);", "pm.expect(b.meta.voucher_count).to.eql(0);"]),
    request("200 lower-case country code", "/api/v1/promotions", {"countryCode": "sg"}, 200, "T05",
            ["pm.expect(b.meta.country_code).to.eql('SG');"]),
    request("400 no countryCode", "/api/v1/promotions", {"city": "Singapore"}, 400),
    request("400 voucherCategory not an array", "/api/v1/promotions", {"countryCode": "{{countryCode}}", "voucherCategory": "package"}, 400),
    request("400 propertyCode not digits", "/api/v1/promotions", {"countryCode": "{{countryCode}}", "propertyCode": "SG-001"}, 400),
    request("400 bad currency", "/api/v1/promotions", {"countryCode": "{{countryCode}}", "currencyCode": "DOLLAR"}, 400),
])

# ---------------------------------------------------------------------------------------------------- T-06
T06 = ("T-06 compare_properties", "POST /api/v1/compare-properties: 2 to 4 properties side by side (schema 0.1.0).", [
    request("200 two codes", "/api/v1/compare-properties",
            dict(propertyCodes=["{{propertyCode}}", "{{propertyCode2}}"], **STAY, noOfadults=2, noOfchildren=0, currencyCode="SGD"), 200, "T06",
            ["pm.expect(b.properties.length).to.be.within(2, 4);",
             "pm.expect(b.meta.total_results).to.eql(b.properties.length);"]),
    request("200 three codes with a child", "/api/v1/compare-properties",
            dict(propertyCodes=["{{propertyCode}}", "{{propertyCode2}}", "{{propertyCode3}}"], **STAY, noOfadults=2, noOfchildren=1,
                 childAges=[7]), 200, "T06", ["pm.expect(b.meta.childAges).to.eql([7]);"]),
    request("200 defaults only (today+30, 1 night, 1 adult)", "/api/v1/compare-properties",
            {"propertyCodes": ["{{propertyCode}}", "{{propertyCode2}}"]}, 200, "T06"),
    request("200 five codes with a duplicate (first four kept)", "/api/v1/compare-properties",
            {"propertyCodes": ["{{propertyCode}}", "{{propertyCode}}", "{{propertyCode2}}", "{{propertyCode3}}", "{{propertyCode4}}", "99999997"]},
            200, "T06", ["pm.expect(b.properties.length).to.be.at.most(4);"]),
    request("404 one known, one unknown code (fewer than two found)", "/api/v1/compare-properties",
            dict(propertyCodes=["{{propertyCode}}", "99999999"], **STAY), 404, checks=["errorCode('PROPERTIES_NOT_FOUND');"]),
    request("400 only one code", "/api/v1/compare-properties", {"propertyCodes": ["{{propertyCode}}"]}, 400),
    request("400 checkout before checkin", "/api/v1/compare-properties",
            {"propertyCodes": ["{{propertyCode}}", "{{propertyCode2}}"], "checkinDate": "2030-01-10", "checkoutDate": "2030-01-09"}, 400),
    request("400 invalid JSON", "/api/v1/compare-properties", None, 400, raw='{"propertyCodes": ["51052",'),
    request("404 no code found", "/api/v1/compare-properties", {"propertyCodes": ["99999998", "99999999"]}, 404,
            checks=["errorCode('PROPERTIES_NOT_FOUND');"]),
])

# ---------------------------------------------------------------------------------------------------- T-07
T07_STAY = dict(**STAY, noOfadults=2, noOfchildren=1, childAges=[6], currencyCode="SGD", priceIncludesTax=True, language="en")
T07 = ("T-07 compare_rooms_rates", "POST /api/v1/compare-rooms: 2 to 4 room types of one property (schema 0.4.0).", [
    request("200 three room codes", "/api/v1/compare-rooms",
            dict(propertyCode="{{propertyCode}}", roomCodes=["{{roomCode1}}", "{{roomCode2}}", "{{roomCode4}}"], **T07_STAY), 200, "T07",
            ["pm.expect(b.rooms.length).to.be.within(2, 4);", "pm.expect(b.meta.total_results).to.eql(b.rooms.length);",
             "const want = [pm.collectionVariables.get('roomCode1'), pm.collectionVariables.get('roomCode2'), pm.collectionVariables.get('roomCode4')];",
             "pm.expect(b.rooms.map(r => r.room_code)).to.eql(want.filter(c => !(b.excluded || []).some(x => x.room_code === c)));"]),
    request("200 two codes carried from T-04", "/api/v1/compare-rooms",
            dict(propertyCode="{{propertyCode}}", roomCodes=["{{pickedRoomCode}}", "{{pickedRoomCode2}}"], **T07_STAY), 200, "T07",
            desc="Run the first T-04 request first: it saves pickedRoomCode / pickedRoomCode2. If both are the same room this is a 400."),
    request("200 no roomCodes (first four)", "/api/v1/compare-rooms", dict(propertyCode="{{propertyCode}}", **T07_STAY), 200, "T07",
            ["(b.excluded || []).forEach(x => pm.expect(x.reason).to.eql('over_limit'));"]),
    request("200 minimal (property + codes only)", "/api/v1/compare-rooms",
            {"propertyCode": "{{propertyCode}}", "roomCodes": ["{{roomCode1}}", "{{roomCode2}}"]}, 200, "T07"),
    request("200 one unknown code (excluded as not_available)", "/api/v1/compare-rooms",
            dict(propertyCode="{{propertyCode}}", roomCodes=["{{roomCode2}}", "XXXX", "{{roomCode1}}"], **T07_STAY), 200, "T07",
            ["pm.expect(b.excluded).to.deep.include({room_code: 'XXXX', reason: 'not_available'});"]),
    request("404 fewer than two available", "/api/v1/compare-rooms",
            dict(propertyCode="{{propertyCode}}", roomCodes=["0BRXA", "1BRXB", "2BRXC"], **T07_STAY), 404,
            checks=["errorCode('NOT_ENOUGH_ROOMS');", "pm.expect(b.error.message).to.include('Room types with rates');"]),
    request("400 one code", "/api/v1/compare-rooms", dict(propertyCode="{{propertyCode}}", roomCodes=["{{roomCode1}}"], **T07_STAY), 400),
    request("400 five codes", "/api/v1/compare-rooms",
            dict(propertyCode="{{propertyCode}}", roomCodes=["A1", "A2", "A3", "A4", "A5"], **T07_STAY), 400),
    request("400 two apartmentList rooms (one room's guests only)", "/api/v1/compare-rooms",
            dict(propertyCode="{{propertyCode}}", roomCodes=["{{roomCode1}}", "{{roomCode2}}"], **STAY, noOfRooms=2,
                 apartmentList=[{"noOfadults": 2, "noOfchildren": 0, "childAges": []}, {"noOfadults": 1, "noOfchildren": 0, "childAges": []}]), 400),
    request("404 unknown property", "/api/v1/compare-rooms", {"propertyCode": "99999999", "roomCodes": ["{{roomCode1}}", "{{roomCode2}}"]}, 404,
            checks=["errorCode('ROOMS_NOT_FOUND');"]),
])

# ---------------------------------------------------------------------------------------------------- T-08
ROOM = lambda a, c, ages, **k: dict(noOfadults=a, noOfchildren=c, childAges=ages, **k)
T08_TOTAL = ["const t = b.rooms.reduce((s, r) => s + r.rate.total_stay_rate + (r.rate.is_tax_inclusive ? 0 : r.rate.total_tax), 0);",
             "pm.expect(b.meta.total_stay_price).to.be.closeTo(t, 0.011);",
             "pm.expect(b.meta.noOfRooms).to.eql(b.rooms.length);"]
T08 = ("T-08 create_booking (checkout hand-off, read-only)",
       "POST /api/v1/create-booking: re-checks availability and returns the booking summary (schema 0.1.0). Nothing is reserved.", [
    request("200 minimal (cheapest, 1 adult, today+30)", "/api/v1/create-booking", {"propertyCode": "{{propertyCode}}"}, 200, "T08",
            ["pm.expect(b.meta.resolution).to.eql('cheapest');", "pm.expect(b.rooms).to.have.lengthOf(1);"] + T08_TOTAL),
    request("200 selected room + rate carried from T-04", "/api/v1/create-booking",
            dict(propertyCode="{{propertyCode}}", **STAY, currencyCode="SGD", language="en",
                 apartmentList=[ROOM(2, 1, [6], roomCode="{{pickedRoomCode}}", ratePlanCode="{{pickedRatePlanCode}}")]), 200, "T08",
            ["pm.expect(b.meta.resolution).to.eql('selected');",
             "pm.expect(b.rooms[0].room_code).to.eql(pm.collectionVariables.get('pickedRoomCode'));",
             "pm.expect(b.rooms[0].rate.rate_plan_code).to.eql(pm.collectionVariables.get('pickedRatePlanCode'));"] + T08_TOTAL,
            desc="Run the first T-04 request first (same stay and guests): it saves pickedRoomCode / pickedRatePlanCode."),
    request("200 three rooms, mixed (room 1 picked)", "/api/v1/create-booking",
            dict(propertyCode="{{propertyCode}}", **STAY, apartmentList=[
                ROOM(2, 0, [], roomCode="{{pickedRoomCode}}", ratePlanCode="{{pickedRatePlanCode}}"), ROOM(1, 1, [4]), ROOM(2, 0, [])]), 200, "T08",
            ["pm.expect(b.meta.resolution).to.eql('mixed');", "pm.expect(b.rooms.map(r => r.room_index)).to.eql([1, 2, 3]);"] + T08_TOTAL,
            desc="Room 1 uses the T-04 pick, which was priced for 2 adults + 1 child; for 2 adults it may come back 409."),
    request("200 two rooms, all cheapest", "/api/v1/create-booking",
            dict(propertyCode="{{propertyCode}}", **STAY, apartmentList=[ROOM(2, 0, []), ROOM(1, 0, [])]), 200, "T08",
            ["pm.expect(b.meta.resolution).to.eql('cheapest');", "pm.expect(b.meta.noOfadults).to.eql(3);"] + T08_TOTAL),
    request("200 with voucher code", "/api/v1/create-booking", dict(propertyCode="{{propertyCode}}", **STAY, voucherCode="{{voucherCode}}"),
            200, "T08", ["pm.expect(b.meta).to.have.property('voucher_code_valid');"]),
    request("409 picked rate not available", "/api/v1/create-booking",
            dict(propertyCode="{{propertyCode}}", **STAY, apartmentList=[ROOM(1, 0, [], roomCode="{{roomCode1}}", ratePlanCode="NOSUCHRATE")]), 409,
            checks=["errorCode('RATE_NOT_AVAILABLE');", "pm.expect(b.error.message).to.include('Rates available for');"]),
    request("409 picked room not at the property", "/api/v1/create-booking",
            dict(propertyCode="{{propertyCode}}", **STAY, apartmentList=[ROOM(1, 0, [], roomCode="9XXX", ratePlanCode="ZZFLEX")]), 409,
            checks=["errorCode('RATE_NOT_AVAILABLE');", "pm.expect(b.error.message).to.include('Room types available');"]),
    request("400 childAges length differs from noOfchildren", "/api/v1/create-booking",
            {"propertyCode": "{{propertyCode}}", "apartmentList": [ROOM(2, 2, [5])]}, 400),
    request("400 roomCode without ratePlanCode", "/api/v1/create-booking",
            {"propertyCode": "{{propertyCode}}", "apartmentList": [ROOM(1, 0, [], roomCode="{{roomCode1}}")]}, 400),
    request("400 five rooms", "/api/v1/create-booking", {"propertyCode": "{{propertyCode}}", "apartmentList": [ROOM(1, 0, [])] * 5}, 400),
    request("400 check-in in the past", "/api/v1/create-booking", {"propertyCode": "{{propertyCode}}", "checkinDate": "2020-01-01"}, 400),
    request("400 propertyCode not digits", "/api/v1/create-booking", {"propertyCode": "ABC"}, 400),
    request("404 unknown property", "/api/v1/create-booking", {"propertyCode": "99999999"}, 404, checks=["errorCode('PROPERTY_NOT_FOUND');"]),
])

# ---------------------------------------------------------------------------------------------------- journey
JOURNEY = ("00 Journey: details -> rooms -> compare -> book -> vouchers",
           "Run this folder alone (Collection Runner) for the ChatGPT journey in order; each step uses what the previous one returned.", [
    request("1 get_property_details", "/api/v1/property-details",
            dict(propertyCode="{{propertyCode}}", **STAY, noOfadults=2, noOfchildren=1, childAges=[6], currencyCode="{{currency}}"), 200, "T02"),
    request("2 get_room_rate_details", "/api/v1/multi-room-details",
            dict(propertyCode="{{propertyCode}}", **STAY, noOfadults=2, noOfchildren=1, childAges=[6], currencyCode="SGD"), 200, "T04", SAVE_PICK),
    request("3 compare_rooms_rates (first four)", "/api/v1/compare-rooms",
            dict(propertyCode="{{propertyCode}}", **STAY, noOfadults=2, noOfchildren=1, childAges=[6], currencyCode="SGD"), 200, "T07"),
    request("4 create_booking (the picked room + rate)", "/api/v1/create-booking",
            dict(propertyCode="{{propertyCode}}", **STAY, currencyCode="SGD",
                 apartmentList=[ROOM(2, 1, [6], roomCode="{{pickedRoomCode}}", ratePlanCode="{{pickedRatePlanCode}}")]), 200, "T08",
            ["pm.expect(b.meta.resolution).to.eql('selected');"] + T08_TOTAL),
    request("5 get_promotions for the property", "/api/v1/promotions", {"countryCode": "{{countryCode}}", "propertyCode": "{{propertyCode}}"}, 200, "T05"),
])

FOLDERS = [JOURNEY, T02, T03, T04, T05, T06, T07, T08]

# ---------------------------------------------------------------------------------------------------- scripts
COLLECTION_PREREQUEST = [
    "// Fresh future dates and a correlation ID for every request.",
    "const d = n => { const x = new Date(); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10); };",
    "pm.variables.set('checkin', d(21));",
    "pm.variables.set('checkout', d(24));",
    "pm.variables.set('correlationId', 'postman-' + Date.now());",
]
COLLECTION_TEST = [
    "// Every response: JSON body, correlation ID echoed; every error: the shared error envelope.",
    "pm.test('Content-Type is JSON', () => pm.expect(pm.response.headers.get('Content-Type') || '').to.include('application/json'));",
    "pm.test('X-Correlation-ID echoed', () => pm.expect(pm.response.headers.get('X-Correlation-ID')).to.eql(pm.variables.get('correlationId')));",
    "if (pm.response.code >= 400) {",
    "  pm.test('Error envelope {success:false, correlationId, error{category, code, message, retryable}}', () => {",
    "    const e = pm.response.json();",
    "    pm.expect(e.success).to.eql(false);",
    "    pm.expect(e.correlationId).to.be.a('string');",
    "    pm.expect(e.error).to.include.keys('category', 'code', 'message', 'retryable');",
    "  });",
    "}",
]


def test_script(r):
    lines = ["pm.test('Status %d', () => pm.response.to.have.status(%d));" % (r["status"], r["status"])]
    body_checks = []
    if r["tool"] and r["status"] == 200:
        top, meta = required_keys(r["tool"])
        body_checks.append("pm.expect(b).to.include.keys(%s);" % ", ".join(json.dumps(k) for k in top))
        if meta:
            body_checks.append("pm.expect(b.meta).to.include.keys(%s);" % ", ".join(json.dumps(k) for k in meta))
        if "meta" in top:
            body_checks.append("pm.expect(b).to.not.have.property('success');  // the bare structuredContent, not an envelope")
    body_checks += r["checks"]
    if body_checks:
        label = "Response matches %s" % (r["tool"] + " schema (required keys) and request checks" if r["tool"] and r["status"] == 200 else "the expected error")
        lines += ["const errorCode = c => pm.expect(pm.response.json().error.code).to.eql(c);",
                  "pm.test(%s, () => {" % json.dumps(label), "  const b = pm.response.json();"]
        lines += ["  " + l for l in body_checks] + ["});"]
    return lines


def item(folder, r):
    path = r["path"].strip("/").split("/")
    raw_url = "{{baseUrl}}/" + "/".join(path) + ("?" + r["query"] if r["query"] else "")
    url = {"raw": raw_url, "host": ["{{baseUrl}}"], "path": path}
    if r["query"]:
        k, v = r["query"].split("=")
        url["query"] = [{"key": k, "value": v}]
    return {
        "id": stable_id(folder, r["name"]),
        "name": r["name"],
        "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": test_script(r)}}],
        "request": {
            "method": "POST",
            "header": [{"key": "Content-Type", "value": "application/json"}, {"key": "X-Correlation-ID", "value": "{{correlationId}}"}],
            "description": r["desc"],
            "body": {"mode": "raw", "raw": r["raw"] if r["raw"] is not None else json.dumps(r["body"], indent=2, ensure_ascii=False),
                     "options": {"raw": {"language": "json"}}},
            "url": url,
        },
    }


def build():
    variables = [
        ("baseUrl", "http://localhost:8081", "The xAPI: http://localhost:8081 in Studio, or the CloudHub app URL."),
        ("propertyCode", "51052", "Ascott Raffles Place Singapore: the property every sample in this repo is built from."),
        ("propertyName", "Ascott Raffles Place Singapore", ""),
        ("propertyCode2", "8790", "Second property for T-06."),
        ("propertyCode3", "8791", "Third property for T-06."),
        ("propertyCode4", "SET_A_4TH_CODE", "A 4th valid property code for T-06; until set it is reported as not found."),
        ("countryCode", "SG", "T-05 country."),
        ("currency", "SGD", ""),
        ("roomCode1", "0BRCT", "51052 room codes (apartmentType): 0BRCT, 1DLXT, 1BRT, 1BRMT."),
        ("roomCode2", "1DLXT", ""),
        ("roomCode3", "1BRT", ""),
        ("roomCode4", "1BRMT", ""),
        ("voucherCode", "SUMMER24", "Any voucher code; meta.voucher_code_valid says whether upstream accepted it."),
        ("pickedRoomCode", "0BRCT", "Set by the first T-04 request (and Journey step 2)."),
        ("pickedRoomCode2", "1DLXT", "Set by the first T-04 request."),
        ("pickedRatePlanCode", "ZZFLEX", "Set by the first T-04 request (and Journey step 2)."),
    ]
    return {
        "info": {
            "_postman_id": stable_id("collection"),
            "name": "Ascott MCP xAPI - all tool calls (T-02 to T-08)",
            "description": (
                "Every tool call of the ODX backend xAPI (asc-mcp-odx-backend-xapi), with tests.\n\n"
                "| Tool | Endpoint |\n|---|---|\n"
                "| T-02 get_property_details | POST /api/v1/property-details |\n"
                "| T-03 get_service_offerings | POST /api/v1/service-offerings |\n"
                "| T-04 get_room_rate_details | POST /api/v1/multi-room-details |\n"
                "| T-05 get_promotions | POST /api/v1/promotions |\n"
                "| T-06 compare_properties | POST /api/v1/compare-properties |\n"
                "| T-07 compare_rooms_rates | POST /api/v1/compare-rooms |\n"
                "| T-08 create_booking | POST /api/v1/create-booking |\n\n"
                "Every request sends a fresh X-Correlation-ID and future dates (check-in today + 21, three nights). "
                "Tests check the status, the JSON body, the echoed correlation ID, the error envelope on errors, and on a 200 the "
                "required keys of the tool's schema. The first T-04 request saves a room code and rate code that T-07 and T-08 reuse; "
                "the '00 Journey' folder runs the calls in conversation order.\n\n"
                "Generated by postman/build_collection.py: edit that script, not this file."),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "event": [{"listen": "prerequest", "script": {"type": "text/javascript", "exec": COLLECTION_PREREQUEST}},
                  {"listen": "test", "script": {"type": "text/javascript", "exec": COLLECTION_TEST}}],
        "variable": [{"key": k, "value": v, **({"description": d} if d else {})} for k, v, d in variables],
        "item": [{"name": name, "description": desc, "item": [item(name, r) for r in reqs]} for name, desc, reqs in FOLDERS],
    }


if __name__ == "__main__":
    c = build()
    OUT.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("%s: %d folders, %d requests" % (OUT.relative_to(ROOT), len(c["item"]), sum(len(f["item"]) for f in c["item"])))
