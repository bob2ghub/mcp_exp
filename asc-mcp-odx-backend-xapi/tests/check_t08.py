"""T-08 create_booking (t08-create-booking.xml): checks the pieces it chains, in Python.

1. dwl/create-booking-validate-request.dwl (mirrored here) on the input schema's shapes;
2. the inline booking search body in create-booking-get-rates (mirrored here);
3. dwl/room-rate-details.dwl (mirror: tests/check_t04.py) followed by dwl/create-booking-response.dwl (mirrored here)
   on the real 51052 response, validated against the owner's schema T08 0.1.0;
4. the flow's error rule (a picked room + rate gone -> 409 RATE_NOT_AVAILABLE, nothing bookable -> 404 NO_AVAILABILITY);
5. dwl/create-booking-add-ons.dwl (mirrored here) on a GUESSED addonlist response: no real sample has been shared.

T08 0.1.0 refers to the T-04 0.4.0 `ratePlan`, which is not in this repo yet; the T-04 0.3.0 schema is registered under
the 0.4.0 id until it arrives (0.4.0 only adds an optional `is_member_rate`).

Run: python -I tests/check_t08.py   (needs: pip install jsonschema)
"""
import copy, json, re, sys
from datetime import date, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]


def load(script, stop):
    """The function part of a mirror script, without running its own checks."""
    ns = {"__file__": str(ROOT / "tests" / script)}
    exec((ROOT / "tests" / script).read_text(encoding="utf-8").split(stop)[0], ns)
    return ns


map_mirror = load("check_t04.py", "def validate(")
map_rooms = map_mirror["map_rooms"]
money = map_mirror["money"]

T04 = json.loads((ROOT / "schemas/T04-get-room-rate-details.structured-content.schema.json").read_text(encoding="utf-8"))
REGISTRY = Registry().with_resource("urn:ascott:mcp:get_room_rate_details:structured-content:0.4.0", Resource.from_contents(T04))
OUT_SCHEMA = json.loads((ROOT / "schemas/T08-create-booking.structured-content.schema.json").read_text(encoding="utf-8"))
IN_SCHEMA = json.loads((ROOT / "schemas/T08-create-booking.input.schema.json").read_text(encoding="utf-8"))
OUT_VALIDATOR = Draft202012Validator(OUT_SCHEMA, registry=REGISTRY, format_checker=FormatChecker())
IN_VALIDATOR = Draft202012Validator(IN_SCHEMA, format_checker=FormatChecker())

PROPS = {"request.maxAdults": 8, "request.maxChildren": 6, "request.maxNights": 30, "rooms.maxRooms": 4,
         "default.language": "en", "default.userCountry": "SG", "property.currency": "SGD",
         "asset.baseUrl": "https://www.discoverasr.com"}
LANGUAGES = ["en", "zh-Hans", "zh-Hant", "fr", "de", "es", "ko", "ja", "id", "vi", "th"]
TODAY = date.today()


# ---------------------------------------------------------------- dwl/create-booking-validate-request.dwl

def text(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def is_int(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == int(v)


def in_range(v, lo, hi):
    return is_int(v) and lo <= v <= hi


def parse_date(v):
    if not isinstance(v, str):
        return False, None
    try:
        return True, date.fromisoformat(v.strip()) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()) else None
    except ValueError:
        return False, None


def validate_request(body, props=PROPS):
    body_ok = isinstance(body, dict)
    body = body if body_ok else {}
    p = props.get
    code = text(body.get("propertyCode"))
    if body.get("checkinDate") is None:
        ci_ok, checkin = True, TODAY + timedelta(days=int(p("t08.checkinOffsetDays") or 30))
    else:
        ci_ok, checkin = parse_date(body["checkinDate"])
        ci_ok = ci_ok and checkin is not None
    if body.get("checkoutDate") is not None:
        co_ok, checkout = parse_date(body["checkoutDate"])
        co_ok = co_ok and checkout is not None
    elif checkin is not None:
        co_ok, checkout = True, checkin + timedelta(days=int(p("t08.nights") or 1))
    else:
        co_ok, checkout = True, None
    nights = (checkout - checkin).days if checkin and checkout else None
    currency = text(body.get("currencyCode"))
    currency = currency.upper() if currency else None
    language = text(body.get("language")) if text(body.get("language")) in LANGUAGES else p("default.language")

    list_given = body.get("apartmentList") is not None
    rooms_in = [a for a in body["apartmentList"] if isinstance(a, dict)] if isinstance(body.get("apartmentList"), list) else []
    if not list_given:
        rooms_in = [{"noOfadults": 1, "noOfchildren": 0, "childAges": []}]
    rooms = [{"noOfadults": a.get("noOfadults"), "noOfchildren": a.get("noOfchildren"), "childAges": a.get("childAges"),
              "roomCode": text(a.get("roomCode")), "ratePlanCode": text(a.get("ratePlanCode")),
              "roomCodeSent": a.get("roomCode") is not None, "ratePlanCodeSent": a.get("ratePlanCode") is not None}
             for a in rooms_in]
    max_a, max_c, max_n, max_r = p("request.maxAdults"), p("request.maxChildren"), p("request.maxNights"), p("rooms.maxRooms")
    room_errors = []
    for i, a in enumerate(rooms):
        room_errors.append(None if in_range(a["noOfadults"], 1, max_a) else "apartmentList[%d].noOfadults must be a whole number from 1 to %d." % (i, max_a))
        room_errors.append(None if in_range(a["noOfchildren"], 0, max_c) else "apartmentList[%d].noOfchildren must be a whole number from 0 to %d." % (i, max_c))
        ages = a["childAges"]
        if not isinstance(ages, list):
            room_errors.append("apartmentList[%d].childAges must be an array of ages ([] when there are no children)." % i)
        elif any(not in_range(x, 0, 17) for x in ages):
            room_errors.append("apartmentList[%d].childAges must be whole numbers from 0 to 17." % i)
        elif in_range(a["noOfchildren"], 0, max_c) and len(ages) != a["noOfchildren"]:
            room_errors.append("apartmentList[%d].childAges must list one age per child." % i)
        room_errors.append("apartmentList[%d].roomCode must be a non-blank string." % i if a["roomCodeSent"] and a["roomCode"] is None else None)
        room_errors.append("apartmentList[%d].ratePlanCode must be a non-blank string." % i if a["ratePlanCodeSent"] and a["ratePlanCode"] is None else None)
        room_errors.append("apartmentList[%d] must have both roomCode and ratePlanCode, or neither." % i
                           if (a["roomCode"] is not None) != (a["ratePlanCode"] is not None) else None)
    errors = [
        None if body_ok else "Request body must be a JSON object.",
        "propertyCode is required." if code is None else (None if re.fullmatch(r"[0-9]{1,20}", code) else "propertyCode must be digits only."),
        None if ci_ok else "checkinDate must be a date in yyyy-MM-dd format.",
        None if co_ok else "checkoutDate must be a date in yyyy-MM-dd format.",
        "checkinDate cannot be in the past." if checkin and checkin < TODAY else None,
        None if nights is None else ("checkoutDate must be after checkinDate." if nights < 1 else
                                     ("The stay cannot be longer than %d nights." % max_n if nights > max_n else None)),
        "apartmentList must be an array of rooms." if list_given and not isinstance(body.get("apartmentList"), list) else None,
        "Each apartmentList entry must be an object." if isinstance(body.get("apartmentList"), list) and len(rooms_in) != len(body["apartmentList"]) else None,
        None if 1 <= len(rooms) <= max_r else "apartmentList must have 1 to %d rooms." % max_r,
        None if currency is None or re.fullmatch(r"[A-Z]{3}", currency) else "currencyCode must be an ISO 4217 code such as SGD.",
        "voucherCode must be a non-blank string." if body.get("voucherCode") is not None and text(body.get("voucherCode")) is None else None,
    ] + room_errors
    apartment_list = [{"noOfadults": a["noOfadults"], "noOfchildren": a["noOfchildren"],
                       "childAges": list(a["childAges"]) if isinstance(a["childAges"], list) else [],
                       "roomCode": a["roomCode"], "ratePlanCode": a["ratePlanCode"]} for a in rooms]
    num = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0
    return {"errors": [e for e in errors if e], "request": {
        "propertyCode": code, "checkin": checkin.isoformat() if checkin else None,
        "checkout": checkout.isoformat() if checkout else None, "nights": nights,
        "adults": sum(num(a["noOfadults"]) for a in apartment_list), "children": sum(num(a["noOfchildren"]) for a in apartment_list),
        "childAges": [x for a in apartment_list for x in a["childAges"]], "rooms": len(apartment_list),
        "apartmentList": apartment_list, "currency": currency, "language": language,
        "voucherCode": text(body.get("voucherCode")), "maxPois": 0}}


# ---------------------------------------------------------------- the inline booking search body

def booking_body(r, trace_id="trace-1", props=PROPS):
    rooms = r.get("apartmentList") or []
    return {
        "messageId": trace_id, "memberId": "", "language": r.get("language"),
        "currencyCode": r.get("currency") or props.get("property.currency"), "promoCorpCode": "",
        "propertyListing": False, "isModifyJourney": False, "propertyCode": [r["propertyCode"]],
        "checkinDate": r["checkin"], "checkoutDate": r["checkout"], "voucherCode": r.get("voucherCode") or "",
        "noOfRooms": len(rooms), "noOfadults": str(r.get("adults", 1)), "noOfchildren": str(r.get("children", 0)),
        "minPrice": "", "maxPrice": "", "perNightRate": True,
        "apartmentList": [{"childAges": a.get("childAges") or [], "noOfadults": str(a["noOfadults"]),
                           "noOfchildren": str(a["noOfchildren"])} for a in rooms],
        "userCountry": props.get("default.userCountry") or "SG", "isExcludePriceStartFrom": False, "channel": "mobile",
    }


# ---------------------------------------------------------------- dwl/create-booking-response.dwl

def upper_of(v):
    return v.strip().upper() if isinstance(v, str) and v.strip() else ""


def objects(v):
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def all_in(rate):
    return (rate.get("per_night_rate") or 0) + (rate.get("per_night_tax") or 0)


def resolve(t04, req, src):
    m = t04.get("meta") or {}
    specs = objects(req.get("apartmentList"))
    requested = objects(t04.get("requested_rooms"))
    picks = []
    for i, spec in enumerate(specs):
        rr = requested[i] if i < len(requested) else {}
        available = objects(rr.get("rooms"))
        label = "Room %d (%s adult(s), %s child(ren))" % (i + 1, rr.get("noOfadults", 1), rr.get("noOfchildren", 0))
        selected = spec.get("roomCode") is not None and spec.get("ratePlanCode") is not None
        c = spec.get("roomCode") or ""
        candidates = [r for r in available if upper_of(r.get("room_code")) == c.upper() or upper_of(r.get("room_category")) == c.upper()]
        if selected:
            hits = [{"room": r, "rate": rp} for r in candidates for rp in objects(r.get("rate_plans"))
                    if upper_of(rp.get("rate_plan_code")) == spec["ratePlanCode"].upper()]
            hit = hits[0] if hits else None
        else:
            hit = None
            for x in ({"room": r, "rate": rp} for r in available for rp in objects(r.get("rate_plans"))):
                if hit is None or all_in(x["rate"]) < all_in(hit["rate"]):
                    hit = x
        problem = None
        if hit is None and selected:
            msg = "%s: room %s with rate %s is not available for this stay." % (label, spec["roomCode"], spec["ratePlanCode"])
            if candidates:
                msg += " Rates available for %s: %s." % (spec["roomCode"], ", ".join(rp["rate_plan_code"] for r in candidates for rp in objects(r.get("rate_plans"))))
            elif available:
                msg += " Room types available: %s." % ", ".join(r["room_code"] for r in available)
            else:
                msg += " Nothing is available for this room."
            problem = {"room_index": i + 1, "reason": "not_available", "message": msg}
        elif hit is None:
            problem = {"room_index": i + 1, "reason": "no_availability", "message": "%s: nothing is available for this stay." % label}
        picks.append({"index": i, "selected": selected, "rr": rr, "hit": hit, "problem": problem})

    rooms = []
    for pk in picks:
        if pk["problem"]:
            continue
        r = {"room_index": pk["rr"].get("room_index", pk["index"] + 1), "noOfadults": pk["rr"].get("noOfadults"),
             "noOfchildren": pk["rr"].get("noOfchildren"), "childAges": pk["rr"].get("childAges") or [],
             "room_code": pk["hit"]["room"].get("room_code"), "room_name": pk["hit"]["room"].get("room_name"),
             "banner_image_url": pk["hit"]["room"].get("banner_image_url"), "rate": pk["hit"]["rate"]}
        rooms.append({k: v for k, v in r.items() if v is not None})
    selected_count = sum(1 for pk in picks if pk["selected"])
    points = sum(r["rate"].get("earn_asr_points", 0) for r in rooms)
    meta = {
        "property_code": text(req.get("propertyCode")) or m.get("property_code"), "property_name": m.get("property_name"),
        "brand_code": m.get("brand_code"), "country_code": m.get("country_code"), "asset_base_url": m.get("asset_base_url"),
        "address": text(src.get("address")), "banner_image_url": text(src.get("bannerImageMobile")),
        "checkin_date": m.get("checkin_date"), "checkout_date": m.get("checkout_date"), "noOfRooms": len(rooms),
        "noOfadults": sum(r.get("noOfadults", 0) for r in rooms), "noOfchildren": sum(r.get("noOfchildren", 0) for r in rooms),
        "currency": m.get("currency"),
        "resolution": "selected" if selected_count == len(picks) else ("cheapest" if selected_count == 0 else "mixed"),
        "total_stay_price": money(sum(r["rate"].get("total_stay_rate", 0) + (0 if r["rate"].get("is_tax_inclusive") else r["rate"].get("total_tax", 0)) for r in rooms)),
        "total_earn_asr_points": points if points > 0 else None, "voucher_code_valid": m.get("voucher_code_valid"),
    }
    return {"problems": [pk["problem"] for pk in picks if pk["problem"]],
            "response": {"meta": {k: v for k, v in meta.items() if v is not None}, "rooms": rooms}}


# ---------------------------------------------------------------- dwl/create-booking-add-ons.dwl

def num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip():
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


def first_text(o, keys):
    for k in keys:
        v = o.get(k)
        t = text(v) if isinstance(v, str) else (str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None)
        if t is not None:
            return t
    return None


def add_on_arrays(o):
    if not isinstance(o, dict):
        return []
    return [x for k, v in o.items() if "addon" in k.lower() and isinstance(v, list) for x in objects(v)]


def one_line(s):
    if s is None:
        return None
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", s)).strip()
    return plain or None


def map_add_ons(payload):
    top = objects(payload) if isinstance(payload, list) else add_on_arrays(payload)
    entries = [x for e in top for x in (add_on_arrays(e) or [e])]
    out, seen = [], set()
    for a in entries:
        title = first_text(a, ["addOnName", "addonName", "title", "name", "addOnTitle"])
        if title is None or title in seen:
            continue
        seen.add(title)
        p = next((n for n in (num(a.get(k)) for k in ["preferredCurrencyPrice", "priceInPrefCurrency", "prefCurrPrice", "price", "amount", "unitPrice"]) if n is not None), None)
        item = {"title": title, "description": one_line(first_text(a, ["shortDescription", "description", "addOnDescription"])),
                "image_url": first_text(a, ["imageUrl", "image", "imagePath", "thumbnailImage", "thumbnail"]),
                "price": money(p) if p is not None and p >= 0 else None}
        out.append({k: v for k, v in item.items() if v is not None})
    return out or None


# ---------------------------------------------------------------- the whole chain

def run(body, src, add_on_response=None):
    v = validate_request(body)
    if v["errors"]:
        return {"status": 400, "errors": v["errors"]}
    req = v["request"]
    t04 = map_rooms(src, req, PROPS)
    result = resolve(t04, req, src)
    if any(p["reason"] == "not_available" for p in result["problems"]):
        return {"status": 409, "code": "RATE_NOT_AVAILABLE", "message": " ".join(p["message"] for p in result["problems"])}
    if result["problems"]:
        return {"status": 404, "code": "NO_AVAILABILITY", "message": " ".join(p["message"] for p in result["problems"])}
    out = dict(result["response"])
    add_ons = map_add_ons(add_on_response) if add_on_response is not None else None
    if add_ons:
        out["add_ons"] = add_ons
    return {"status": 200, "body": out, "request": req, "t04": t04}


def validate(label, doc, validator=OUT_VALIDATOR):
    errs = list(validator.iter_errors(doc))
    print(("ok   " if not errs else "FAIL ") + label)
    for e in errs[:6]:
        print("   /%s: %s" % ("/".join(str(x) for x in e.path), e.message))
    return not errs


def check(label, cond):
    print("%s %s" % ("ok  " if cond else "FAIL", label))
    return bool(cond)


def picked(res):
    return [(r["room_code"], r["rate"]["rate_plan_code"]) for r in res["body"]["rooms"]]


src = json.loads((ROOT / "examples/upstream-property-details-51052.json").read_text(encoding="utf-8"))["propertyList"][0]
CI, CO = (TODAY + timedelta(days=40)).isoformat(), (TODAY + timedelta(days=42)).isoformat()
results = []

# 1. Minimal: propertyCode only -> one room, 1 adult, today + 30, one night, the cheapest rate.
res = run({"propertyCode": "51052"}, src)
results.append(validate("minimal {propertyCode}: response validates against T08 0.1.0", res["body"]))
meta = res["body"]["meta"]
results.append(check("minimal: defaults today+30 / 1 night / 1 room / 1 adult, resolution cheapest",
                     meta["checkin_date"] == (TODAY + timedelta(days=30)).isoformat()
                     and meta["checkout_date"] == (TODAY + timedelta(days=31)).isoformat()
                     and meta["noOfRooms"] == 1 and meta["noOfadults"] == 1 and meta["noOfchildren"] == 0
                     and meta["resolution"] == "cheapest" and meta["currency"] == "SGD"))
results.append(check("minimal: cheapest all-in rate is the studio's ASRAPPFX (211.50 + 42.09 tax)",
                     picked(res) == [("0BRCT", "ASRAPPFX")]))
results.append(check("minimal: total_stay_price = total_stay_rate + total_tax (tax-exclusive), points summed",
                     meta["total_stay_price"] == money(423 + 84.18)
                     and meta.get("total_earn_asr_points") == res["body"]["rooms"][0]["rate"].get("earn_asr_points")))
results.append(check("minimal: property address and banner from upstream",
                     meta.get("address") == "2 Finlayson Green, Singapore 049247" and "banner_image_url" in meta))
results.append(check("minimal: each room's rate is the T-04 rate object unchanged",
                     res["body"]["rooms"][0]["rate"] == res["t04"]["requested_rooms"][0]["rooms"][0]["rate_plans"][0]))

# 2. Selected: the user's pick, case ignored.
sel = {"propertyCode": "51052", "checkinDate": CI, "checkoutDate": CO, "currencyCode": "sgd", "language": "th",
       "apartmentList": [{"noOfadults": 2, "noOfchildren": 1, "childAges": [6], "roomCode": "0brct", "ratePlanCode": "zzflex"}]}
results.append(validate("input schema accepts the selected example (lower-case currency aside)",
                        dict(sel, currencyCode="SGD"), IN_VALIDATOR))
res = run(sel, src)
results.append(validate("selected: validates", res["body"]))
results.append(check("selected: 0BRCT + ZZFLEX, resolution selected, guests and childAges echoed, currency upper-cased",
                     picked(res) == [("0BRCT", "ZZFLEX")] and res["body"]["meta"]["resolution"] == "selected"
                     and res["body"]["rooms"][0]["childAges"] == [6] and res["body"]["meta"]["noOfchildren"] == 1
                     and res["body"]["meta"]["currency"] == "SGD" and res["body"]["meta"]["checkin_date"] == CI))
body = booking_body(res["request"])
results.append(check("booking search body: one apartmentList entry with childAges [6], language passed through",
                     body["apartmentList"] == [{"childAges": [6], "noOfadults": "2", "noOfchildren": "1"}]
                     and body["noOfRooms"] == 1 and body["language"] == "th" and body["voucherCode"] == ""))
(ROOT / "examples/create-booking-51052-request.sample.json").write_text(json.dumps(dict(sel, currencyCode="SGD"), indent=2) + "\n", encoding="utf-8")
(ROOT / "examples/create-booking-51052-response.sample.json").write_text(json.dumps(res["body"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# 3. Three rooms, mixed: room 1 picked, rooms 2 and 3 cheapest from their own room{i}.
s3 = copy.deepcopy(src)
room0 = s3["apartments"][0]["room0"]
s3["apartments"] = [{"room0": room0, "room1": room0[1:3], "room2": room0[3:]}]
three = {"propertyCode": "51052", "checkinDate": CI, "checkoutDate": CO, "apartmentList": [
    {"noOfadults": 2, "noOfchildren": 0, "childAges": [], "roomCode": "1DLXT", "ratePlanCode": "Flexi Monthly Rate"},
    {"noOfadults": 1, "noOfchildren": 1, "childAges": [4]},
    {"noOfadults": 3, "noOfchildren": 0, "childAges": []}]}
res = run(three, s3)
results.append(validate("three rooms, mixed: validates", res["body"]))
rooms = res["body"]["rooms"]
results.append(check("three rooms: in input order, room_index 1..3, room 2 and 3 from room1 / room2 only, resolution mixed",
                     [r["room_index"] for r in rooms] == [1, 2, 3] and rooms[0]["room_code"] == "1DLXT"
                     and rooms[1]["room_code"] in ("1DLXT", "1BRT") and rooms[2]["room_code"] == "1BRMT"
                     and res["body"]["meta"]["resolution"] == "mixed"))
results.append(check("three rooms: meta sums 6 adults, 1 child, noOfRooms 3; total = sum of all-in stays",
                     res["body"]["meta"]["noOfadults"] == 6 and res["body"]["meta"]["noOfchildren"] == 1
                     and res["body"]["meta"]["noOfRooms"] == 3
                     and res["body"]["meta"]["total_stay_price"] == money(sum(r["rate"]["total_stay_rate"] + (0 if r["rate"]["is_tax_inclusive"] else r["rate"]["total_tax"]) for r in rooms))))
body = booking_body(res["request"])
results.append(check("three rooms: booking search body has noOfRooms 3, three apartmentList entries, summed top-level guests",
                     body["noOfRooms"] == 3 and len(body["apartmentList"]) == 3 and body["noOfadults"] == "6" and body["noOfchildren"] == "1"))
res = run(dict(three, apartmentList=[dict(a, roomCode=None, ratePlanCode=None) if "roomCode" in a else a for a in three["apartmentList"]]), s3)
results.append(check("roomCode / ratePlanCode null = not sent: resolution cheapest", res["status"] == 200 and res["body"]["meta"]["resolution"] == "cheapest"))

# 4. A picked rate that is no longer bookable (a member rate, a missing room, a room with nothing left).
studio_codes = [rp["rate_plan_code"] for rp in map_rooms(src, validate_request({"propertyCode": "51052"})["request"], PROPS)["requested_rooms"][0]["rooms"][0]["rate_plans"]]
member = next(rp["ratePlanCode"] for rp in src["apartments"][0]["room0"][0]["ratePlan"]
              if (rp.get("ratePlanTemplate") or "").upper() == "AOA")
res = run({"propertyCode": "51052", "apartmentList": [{"noOfadults": 1, "noOfchildren": 0, "childAges": [], "roomCode": "0BRCT", "ratePlanCode": member}]}, src)
results.append(check("picked member rate: 409 RATE_NOT_AVAILABLE listing the studio's bookable rates",
                     res["status"] == 409 and res["code"] == "RATE_NOT_AVAILABLE"
                     and ("Rates available for 0BRCT: " + ", ".join(studio_codes) + ".") in res["message"]))
res = run({"propertyCode": "51052", "apartmentList": [{"noOfadults": 1, "noOfchildren": 0, "childAges": [], "roomCode": "9XXX", "ratePlanCode": "ZZFLEX"}]}, src)
results.append(check("picked unknown room: 409 listing the room types available",
                     res["status"] == 409 and "Room types available: 0BRCT, 1DLXT, 1BRT, 1BRMT." in res["message"]))
s4 = copy.deepcopy(src)
s4["apartments"] = [{"room0": s4["apartments"][0]["room0"], "room1": []}]
two = {"propertyCode": "51052", "apartmentList": [{"noOfadults": 1, "noOfchildren": 0, "childAges": []},
                                                  {"noOfadults": 4, "noOfchildren": 0, "childAges": []}]}
res = run(two, s4)
results.append(check("room 2 with nothing bookable: 404 NO_AVAILABILITY naming room 2",
                     res["status"] == 404 and res["code"] == "NO_AVAILABILITY" and res["message"].startswith("Room 2 (4 adult(s), 0 child(ren))")))
res = run(dict(two, apartmentList=[two["apartmentList"][0], dict(two["apartmentList"][1], roomCode="0BRCT", ratePlanCode="ZZFLEX")]), s4)
results.append(check("both kinds at once: 409 wins (a picked rate is gone)", res["status"] == 409 and "Nothing is available for this room." in res["message"]))

# 5. Cheapest is compared INCLUDING tax; ties go to the better-ranked room.
s5 = copy.deepcopy(src)
for a in s5["apartments"][0]["room0"]:
    if a["apartmentType"] == "1DLXT":
        rp = a["ratePlan"][0]
        rp.update(isTaxInclusive=True, perNightRatePrefCurr=240, totalStayRatePrefCurr=240, ratePlanTemplate="BAR",
                  ratePlanTemplateName="Best rate", ratePlanName="Inclusive Saver", ratePlanCode="INCL")
res = run({"propertyCode": "51052"}, s5)
results.append(check("tax-inclusive 240 beats tax-exclusive 211.50 + 42.09 = 253.59", picked(res) == [("1DLXT", "INCL")]))
results.append(check("tax-inclusive total_stay_price adds no tax", res["body"]["meta"]["total_stay_price"] == 240))
s6 = copy.deepcopy(s5)
for a in s6["apartments"][0]["room0"]:
    if a["apartmentType"] == "0BRCT":
        for rp in a["ratePlan"]:
            if rp.get("ratePlanCode") == "ASRAPPFX":
                rp.update(isTaxInclusive=True, perNightRatePrefCurr=240, totalStayRatePrefCurr=240, taxes=[])
res = run({"propertyCode": "51052"}, s6)
results.append(check("a tie at 240 goes to the better-ranked room (0BRCT, ranking 1)", picked(res) == [("0BRCT", "ASRAPPFX")]))

# 6. Voucher, language, currency.
res = run({"propertyCode": "51052", "voucherCode": " SUMMER24 ", "language": "pt"}, src)
results.append(check("voucherCode trimmed, sent upstream, voucher_code_valid answered; unknown language -> default",
                     res["request"]["voucherCode"] == "SUMMER24" and booking_body(res["request"])["voucherCode"] == "SUMMER24"
                     and "voucher_code_valid" in res["body"]["meta"] and res["request"]["language"] == "en"))
results.append(validate("voucher: validates", res["body"]))
res = run({"propertyCode": "51052"}, src)
results.append(check("no voucherCode: no voucher_code_valid", "voucher_code_valid" not in res["body"]["meta"]))

# 7. Points: absent when no booked rate earns any.
s7 = copy.deepcopy(src)
for a in s7["apartments"][0]["room0"]:
    for rp in a["ratePlan"]:
        rp["earnASRpoints"] = 0
res = run({"propertyCode": "51052"}, s7)
results.append(check("no points earned: total_earn_asr_points left out", "total_earn_asr_points" not in res["body"]["meta"]))

# 8. Bad input -> 400.
bad = [
    ("no propertyCode", {}),
    ("propertyCode not digits", {"propertyCode": "ABC"}),
    ("childAges shorter than noOfchildren", {"propertyCode": "51052", "apartmentList": [{"noOfadults": 2, "noOfchildren": 2, "childAges": [5]}]}),
    ("childAges missing", {"propertyCode": "51052", "apartmentList": [{"noOfadults": 2, "noOfchildren": 0}]}),
    ("child age 18", {"propertyCode": "51052", "apartmentList": [{"noOfadults": 2, "noOfchildren": 1, "childAges": [18]}]}),
    ("roomCode without ratePlanCode", {"propertyCode": "51052", "apartmentList": [{"noOfadults": 1, "noOfchildren": 0, "childAges": [], "roomCode": "0BRCT"}]}),
    ("blank ratePlanCode", {"propertyCode": "51052", "apartmentList": [{"noOfadults": 1, "noOfchildren": 0, "childAges": [], "roomCode": "0BRCT", "ratePlanCode": " "}]}),
    ("0 adults", {"propertyCode": "51052", "apartmentList": [{"noOfadults": 0, "noOfchildren": 0, "childAges": []}]}),
    ("empty apartmentList", {"propertyCode": "51052", "apartmentList": []}),
    ("five rooms", {"propertyCode": "51052", "apartmentList": [{"noOfadults": 1, "noOfchildren": 0, "childAges": []}] * 5}),
    ("past check-in", {"propertyCode": "51052", "checkinDate": "2020-01-01"}),
    ("checkout before check-in", {"propertyCode": "51052", "checkinDate": CO, "checkoutDate": CI}),
    ("bad date format", {"propertyCode": "51052", "checkinDate": "04/05/2027"}),
    ("currency not ISO", {"propertyCode": "51052", "currencyCode": "DOLLAR"}),
]
for label, b in bad:
    results.append(check("400: " + label, run(b, src)["status"] == 400))

# 9. Add-ons (GUESSED response shape: no real addonlist sample yet).
guess = {"messageId": "x", "addOnList": [
    {"addOnName": "Airport Transfer", "description": "<p>One way, up to 3 guests</p>", "imageUrl": "/content/addons/transfer.jpg", "preferredCurrencyPrice": "85.5"},
    {"addOnName": "Daily breakfast", "shortDescription": "Breakfast SGD 25 nett per meal per person", "price": 25},
    {"addOnName": "Airport Transfer", "price": 90},
    {"description": "no title, dropped"}]}
res = run({"propertyCode": "51052"}, src, add_on_response=guess)
results.append(validate("with add-ons: validates", res["body"]))
results.append(check("add-ons: titles de-duplicated, HTML stripped, prices as numbers, untitled dropped",
                     res["body"]["add_ons"] == [
                         {"title": "Airport Transfer", "description": "One way, up to 3 guests", "image_url": "/content/addons/transfer.jpg", "price": 85.5},
                         {"title": "Daily breakfast", "description": "Breakfast SGD 25 nett per meal per person", "price": 25}]))
per_room = {"rooms": [{"roomIndex": 1, "addons": [{"name": "Late checkout", "amount": "40"}]}, {"roomIndex": 2, "addons": [{"name": "Late checkout"}]}]}
results.append(check("add-ons: a per-room answer is flattened one level", map_add_ons({"perRoomAddOns": per_room["rooms"]}) == [{"title": "Late checkout", "price": 40}]))
results.append(check("add-ons: nothing usable -> add_ons left out", "add_ons" not in run({"propertyCode": "51052"}, src, add_on_response={"addOnList": []})["body"]))

print("\n%d/%d checks passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
