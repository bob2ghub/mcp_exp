"""T-04 request validation: a Python copy of dwl/rooms-validate-request.dwl.

The DataWeave is the implementation; keep this copy in step with it. Run: python -I tests/check_t04_request.py
"""
import math, re, sys
from datetime import date, timedelta

PROPS = {"request.maxAdults": 8, "request.maxChildren": 6, "request.maxNights": 30, "rooms.maxRooms": 4,
         "default.checkinOffsetDays": 7, "default.nights": 1, "default.adults": 2, "default.children": 0,
         "default.language": "en"}
TODAY = date.today()


def text(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, (int, float)):
        return str(v)
    return None


def number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str) and v.strip():
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


def is_whole(n):
    return isinstance(n, (int, float)) and not isinstance(n, bool) and float(n).is_integer()


def in_range(n, lo, hi):
    return is_whole(n) and lo <= n <= hi


def whole(n):
    return math.floor(n) if is_whole(n) else n


def parse_date(v):
    if not isinstance(v, str):
        return (False, None)
    try:
        return (True, date.fromisoformat(v.strip()))
    except ValueError:
        return (False, None)


def validate(body):
    p = PROPS.get
    body = body if isinstance(body, dict) else {}
    code, name = text(body.get("propertyCode")), text(body.get("propertyName"))

    ci_in = body.get("checkin") if body.get("checkin") is not None else body.get("checkinDate")
    ci_ok, checkin = (True, TODAY + timedelta(days=p("default.checkinOffsetDays"))) if ci_in is None else parse_date(ci_in)
    co_in = body.get("checkout") if body.get("checkout") is not None else body.get("checkoutDate")
    if co_in is not None:
        co_ok, checkout = parse_date(co_in)
    elif isinstance(checkin, date):
        co_ok, checkout = True, checkin + timedelta(days=p("default.nights"))
    else:
        co_ok, checkout = True, None
    nights = (checkout - checkin).days if isinstance(checkin, date) and isinstance(checkout, date) else None

    a_in = body.get("adults") if body.get("adults") is not None else body.get("noOfadults")
    c_in = body.get("children") if body.get("children") is not None else body.get("noOfchildren")
    adults = p("default.adults") if a_in is None else number(a_in)
    children = p("default.children") if c_in is None else number(c_in)
    cur_in = body.get("currency") if body.get("currency") is not None else body.get("currencyCode")
    currency = None if cur_in is None else (text(cur_in) or "").upper()
    language = p("default.language") if body.get("language") is None else text(body.get("language"))

    def ages(v):
        return [number(x) for x in v] if isinstance(v, list) else []

    top_ages = ages(body.get("childAges"))
    rows = [x for x in body.get("apartmentList")] if isinstance(body.get("apartmentList"), list) else []
    rows = [x for x in rows if isinstance(x, dict)]
    if not rows:
        apartment_list = [{"noOfadults": adults, "noOfchildren": children, "childAges": top_ages}]
    else:
        apartment_list = []
        for a in rows:
            a_i = a.get("noOfadults") if a.get("noOfadults") is not None else a.get("adults")
            c_i = a.get("noOfchildren") if a.get("noOfchildren") is not None else a.get("children")
            apartment_list.append({"noOfadults": adults if a_i is None else number(a_i),
                                   "noOfchildren": 0 if c_i is None else number(c_i),
                                   "childAges": ages(a.get("childAges"))})
    rooms = len(apartment_list)

    room_errors = []
    for i, a in enumerate(apartment_list if rows else []):
        if not in_range(a["noOfadults"], 1, p("request.maxAdults")):
            room_errors.append("apartmentList[%d].noOfadults must be a whole number from 1 to %s." % (i, p("request.maxAdults")))
        if not in_range(a["noOfchildren"], 0, p("request.maxChildren")):
            room_errors.append("apartmentList[%d].noOfchildren must be a whole number from 0 to %s." % (i, p("request.maxChildren")))
        if [x for x in a["childAges"] if not in_range(x, 0, 17)]:
            room_errors.append("apartmentList[%d].childAges must be whole numbers from 0 to 17." % i)
        if in_range(a["noOfchildren"], 0, p("request.maxChildren")) and len(a["childAges"]) > a["noOfchildren"]:
            room_errors.append("apartmentList[%d].childAges cannot list more ages than noOfchildren." % i)

    errors = [e for e in [
        None if code is not None or name is not None else "Provide propertyCode or propertyName.",
        None if code is None else (None if re.fullmatch(r"[A-Za-z0-9_-]{1,20}", code) else "propertyCode must be 1 to 20 letters, digits, hyphens or underscores."),
        None if name is None else (None if len(name) <= 200 else "propertyName must be at most 200 characters."),
        None if ci_ok else "checkin must be a date in yyyy-MM-dd format.",
        None if co_ok else "checkout must be a date in yyyy-MM-dd format.",
        None if not isinstance(checkin, date) else (None if checkin >= TODAY else "checkin cannot be in the past."),
        None if nights is None else ("checkout must be after checkin." if nights < 1
                                     else ("The stay cannot be longer than %s nights." % p("request.maxNights") if nights > p("request.maxNights") else None)),
        None if in_range(adults, 1, p("request.maxAdults")) else "adults must be a whole number from 1 to %s." % p("request.maxAdults"),
        None if in_range(children, 0, p("request.maxChildren")) else "children must be a whole number from 0 to %s." % p("request.maxChildren"),
        "childAges must be whole numbers from 0 to 17." if [x for x in top_ages if not in_range(x, 0, 17)] else None,
        None if in_range(rooms, 1, p("rooms.maxRooms")) else "apartmentList must have 1 to %s entries." % p("rooms.maxRooms"),
        "priceIncludesTax must be true or false." if (body.get("priceIncludesTax") is not None and not isinstance(body.get("priceIncludesTax"), bool)) else None,
        None if (isinstance(language, str) and re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2,4})?", language)) else "language must be a language code such as en or zh-CN.",
        None if currency is None else (None if re.fullmatch(r"[A-Z]{3}", currency) else "currency must be an ISO 4217 code such as SGD."),
    ] + room_errors if e is not None]

    return {
        "errors": errors,
        "request": {
            "propertyCode": code, "propertyName": name,
            "checkin": checkin.isoformat() if isinstance(checkin, date) else None,
            "checkout": checkout.isoformat() if isinstance(checkout, date) else None,
            "nights": nights,
            "adults": whole(sum(a["noOfadults"] for a in apartment_list if isinstance(a["noOfadults"], (int, float)))),
            "children": whole(sum(a["noOfchildren"] for a in apartment_list if isinstance(a["noOfchildren"], (int, float)))),
            "childAges": [whole(x) for a in apartment_list for x in a["childAges"]],
            "rooms": rooms,
            "apartmentList": [{"noOfadults": whole(a["noOfadults"]), "noOfchildren": whole(a["noOfchildren"]),
                               "childAges": [whole(x) for x in a["childAges"]]} for a in apartment_list],
            "currency": currency, "language": language,
            "priceIncludesTax": body.get("priceIncludesTax") if isinstance(body.get("priceIncludesTax"), bool) else None,
            "maxPois": 0,
            "noOfRoomsSent": body.get("noOfRooms") if body.get("noOfRooms") is not None else body.get("rooms"),
            "perNightRate": body.get("perNightRate") if isinstance(body.get("perNightRate"), bool) else None,
            "isExcludePriceStartFrom": body.get("isExcludePriceStartFrom") if isinstance(body.get("isExcludePriceStartFrom"), bool) else None,
            "promoCorpCode": text(body.get("promoCorpCode")),
        },
    }


def check(label, cond):
    print("%s %s" % ("ok  " if cond else "FAIL", label))
    return bool(cond)


results = []
r = validate({"propertyCode": "51052"})
results.append(check("defaults: today+7 for 1 night, 2 adults, one requested room",
                     r["errors"] == [] and r["request"]["checkin"] == (TODAY + timedelta(days=7)).isoformat()
                     and r["request"]["nights"] == 1 and r["request"]["adults"] == 2
                     and r["request"]["rooms"] == 1 and r["request"]["language"] == "en"
                     and r["request"]["apartmentList"] == [{"noOfadults": 2, "noOfchildren": 0, "childAges": []}]))

r = validate({"propertyCode": "51052", "checkin": "2026-11-10", "checkout": "2026-11-12", "adults": 3,
              "children": 2, "childAges": [4, 9], "currency": "sgd", "priceIncludesTax": True})
results.append(check("short names, 2 nights, currency upper-cased, flags kept",
                     r["errors"] == [] and r["request"]["nights"] == 2 and r["request"]["currency"] == "SGD"
                     and r["request"]["childAges"] == [4, 9] and r["request"]["priceIncludesTax"] is True))

r = validate({"propertyCode": "51052", "checkinDate": "2026-11-10", "checkoutDate": "2026-11-12",
              "noOfadults": 1, "noOfchildren": 1, "currencyCode": "USD"})
results.append(check("PRD names accepted", r["errors"] == [] and r["request"]["adults"] == 1
                     and r["request"]["children"] == 1 and r["request"]["currency"] == "USD"))

r = validate({"propertyCode": "51052", "checkin": "2026-11-10", "checkout": "2026-11-12",
              "apartmentList": [{"noOfadults": 2, "noOfchildren": 1, "childAges": [5]}, {"adults": 1}]})
results.append(check("apartmentList: guests summed, rooms counted, per-room children default 0",
                     r["errors"] == [] and r["request"]["rooms"] == 2 and r["request"]["adults"] == 3
                     and r["request"]["children"] == 1 and r["request"]["childAges"] == [5]
                     and r["request"]["apartmentList"][1] == {"noOfadults": 1, "noOfchildren": 0, "childAges": []}))

r = validate({})
results.append(check("no property: one error", r["errors"] == ["Provide propertyCode or propertyName."]))

r = validate({"propertyCode": "51052", "checkin": "10/11/2026"})
results.append(check("bad date format reported", "checkin must be a date in yyyy-MM-dd format." in r["errors"]))

r = validate({"propertyCode": "51052", "checkin": (TODAY - timedelta(days=1)).isoformat()})
results.append(check("past check-in reported", "checkin cannot be in the past." in r["errors"]))

r = validate({"propertyCode": "51052", "checkin": "2026-11-10", "checkout": "2026-11-10"})
results.append(check("same-day stay reported", "checkout must be after checkin." in r["errors"]))

r = validate({"propertyCode": "51052", "adults": 99, "children": -1, "childAges": [25], "currency": "SG$",
              "language": "English", "priceIncludesTax": "yes"})
results.append(check("every bad scalar reported once, and only once", len(r["errors"]) == 6))

r = validate({"propertyCode": "51052", "apartmentList": [{}, {}, {}, {}, {}]})
results.append(check("too many requested rooms reported",
                     "apartmentList must have 1 to 4 entries." in r["errors"]))

r = validate({"propertyCode": "51052", "apartmentList": [{"noOfadults": 0, "noOfchildren": 1, "childAges": [3, 4]}]})
results.append(check("per-room errors name the room",
                     r["errors"] == ["apartmentList[0].noOfadults must be a whole number from 1 to 8.",
                                     "apartmentList[0].childAges cannot list more ages than noOfchildren."]))

r = validate({"propertyName": "Ascott Raffles Place", "checkin": "2026-11-10", "checkout": "2026-12-20"})
results.append(check("stay longer than 30 nights reported",
                     "The stay cannot be longer than 30 nights." in r["errors"]))

sys.exit(0 if all(results) else 1)
