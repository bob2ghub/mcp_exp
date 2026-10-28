"""T-02 request validation: a Python copy of dwl/validate-request.dwl (input schema 0.2.0).

The DataWeave is the implementation; keep this copy in step with it. Every body the checks call valid must also pass
schemas/T02-get-property-details.input.schema.json (when it uses only schema names), and the schema-invalid bodies
must be rejected. Run: python -I tests/check_t02_request.py
"""
import json, math, os, re, sys
from datetime import date, timedelta

import jsonschema

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = json.load(open(os.path.join(HERE, "..", "schemas", "T02-get-property-details.input.schema.json")))
PROPS = {"request.maxAdults": 8, "request.maxChildren": 6, "request.maxNights": 30, "poi.maxPerProperty": 5,
         "default.language": "en"}
LANGUAGES = ["en", "zh-Hans", "zh-Hant", "fr", "de", "es", "ko", "ja", "id", "vi", "th"]
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


def first(body, *names):
    for n in names:
        if body.get(n) is not None:
            return body.get(n)
    return None


def validate(payload):
    p = lambda k, d=None: PROPS.get(k, d)
    body = payload if isinstance(payload, dict) else {}
    code_in = body.get("propertyCode")
    if isinstance(code_in, list) and len(code_in) == 1:
        code_in = code_in[0]
    code = text(code_in)

    ci_in = first(body, "checkinDate", "checkin")
    ci_ok, checkin = (True, TODAY + timedelta(days=p("t02.checkinOffsetDays", 30))) if ci_in is None else parse_date(ci_in)
    co_in = first(body, "checkoutDate", "checkout")
    if co_in is not None:
        co_ok, checkout = parse_date(co_in)
    elif isinstance(checkin, date):
        co_ok, checkout = True, checkin + timedelta(days=p("t02.nights", 1))
    else:
        co_ok, checkout = True, None
    nights = (checkout - checkin).days if isinstance(checkin, date) and isinstance(checkout, date) else None

    a_in, c_in = first(body, "noOfadults", "adults"), first(body, "noOfchildren", "children")
    adults = 1 if a_in is None else number(a_in)
    children = 0 if c_in is None else number(c_in)
    ages_in = body.get("childAges")
    child_ages = [number(x) for x in ages_in] if isinstance(ages_in, list) else []

    cur_in = first(body, "currencyCode", "currency")
    currency = None if cur_in is None else (text(cur_in) or "").upper()
    lang_in = text(body.get("language"))
    language = lang_in if lang_in in LANGUAGES else p("default.language")
    max_pois_limit = p("poi.maxPerProperty", 5)
    max_pois = max_pois_limit if body.get("maxPois") is None else number(body.get("maxPois"))
    max_a, max_c, max_n = p("request.maxAdults"), p("request.maxChildren"), p("request.maxNights")

    if not in_range(children, 1, max_c):
        ages_rule = None
    elif not child_ages:
        ages_rule = "childAges is required when noOfchildren is above 0: give one age per child."
    elif len(child_ages) != children:
        ages_rule = "childAges must list exactly one age per child (%d)." % children
    else:
        ages_rule = None

    errors = [e for e in [
        None if isinstance(payload, dict) else "Request body must be a JSON object.",
        'propertyCode must be one code, such as "51052".' if (isinstance(body.get("propertyCode"), list) and len(body.get("propertyCode")) != 1)
        else "propertyCode is required." if code is None else (None if re.fullmatch(r"[0-9]{1,20}", code) else 'propertyCode must be digits only, such as "51052".'),
        None if ci_ok else "checkinDate must be a date in YYYY-MM-DD format.",
        None if co_ok else "checkoutDate must be a date in YYYY-MM-DD format.",
        None if not isinstance(checkin, date) else (None if checkin >= TODAY else "checkinDate cannot be in the past."),
        None if nights is None else ("checkoutDate must be after checkinDate." if nights < 1
                                     else ("The stay cannot be longer than %s nights." % max_n if nights > max_n else None)),
        None if in_range(adults, 1, max_a) else "noOfadults must be a whole number from 1 to %s." % max_a,
        None if in_range(children, 0, max_c) else "noOfchildren must be a whole number from 0 to %s." % max_c,
        "childAges must be an array of ages." if (ages_in is not None and not isinstance(ages_in, list)) else None,
        "childAges must be whole numbers from 0 to 17." if [x for x in child_ages if not in_range(x, 0, 17)] else None,
        ages_rule,
        "childAges must be empty when noOfchildren is 0." if (in_range(children, 0, 0) and child_ages) else None,
        None if currency is None else (None if re.fullmatch(r"[A-Z]{3}", currency) else "currencyCode must be an ISO 4217 code such as SGD."),
        None if in_range(max_pois, 0, max_pois_limit) else "maxPois must be a whole number from 0 to %s." % max_pois_limit,
    ] if e is not None]

    return {
        "errors": errors,
        "request": {
            "propertyCode": code,
            "checkin": checkin.isoformat() if isinstance(checkin, date) else None,
            "checkout": checkout.isoformat() if isinstance(checkout, date) else None,
            "nights": nights,
            "adults": whole(adults), "children": whole(children),
            "childAges": [whole(x) for x in child_ages],
            "currency": currency, "language": language, "maxPois": whole(max_pois),
        },
    }


def schema_ok(body):
    return jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker()).is_valid(body)


def check(label, cond):
    print("%s %s" % ("ok  " if cond else "FAIL", label))
    return bool(cond)


ci, co = (TODAY + timedelta(days=21)).isoformat(), (TODAY + timedelta(days=24)).isoformat()
results = []

body = {"propertyCode": "51052"}
r = validate(body)
results.append(check("minimal body: schema-valid; defaults today+30, 1 night, 1 adult, 0 children, en, maxPois 5",
                     schema_ok(body) and r["errors"] == [] and r["request"]["checkin"] == (TODAY + timedelta(days=30)).isoformat()
                     and r["request"]["nights"] == 1 and r["request"]["adults"] == 1 and r["request"]["children"] == 0
                     and r["request"]["childAges"] == [] and r["request"]["language"] == "en"
                     and r["request"]["currency"] is None and r["request"]["maxPois"] == 5))

body = {"propertyCode": "51052", "checkinDate": ci, "checkoutDate": co, "noOfadults": 2, "noOfchildren": 2,
        "childAges": [4, 9], "currencyCode": "USD", "language": "zh-Hant"}
r = validate(body)
results.append(check("full schema body: valid; mapped to the downstream names",
                     schema_ok(body) and r["errors"] == []
                     and r["request"] == {"propertyCode": "51052", "checkin": ci, "checkout": co, "nights": 3,
                                          "adults": 2, "children": 2, "childAges": [4, 9], "currency": "USD",
                                          "language": "zh-Hant", "maxPois": 5}))

body = {"propertyCode": "51052", "noOfchildren": 1}
r = validate(body)
results.append(check("children without childAges: schema and server both reject",
                     not schema_ok(body) and r["errors"] == ["childAges is required when noOfchildren is above 0: give one age per child."]))

body = {"propertyCode": "51052", "noOfchildren": 2, "childAges": [5]}
r = validate(body)
results.append(check("one age for two children rejected", r["errors"] == ["childAges must list exactly one age per child (2)."]))

r = validate({"propertyCode": "51052", "childAges": [5]})
results.append(check("ages with no children rejected", r["errors"] == ["childAges must be empty when noOfchildren is 0."]))

body = {"propertyCode": "51052", "noOfchildren": 0, "childAges": []}
results.append(check("noOfchildren 0 with [] is fine", schema_ok(body) and validate(body)["errors"] == []))

r = validate({"checkinDate": ci})
results.append(check("no propertyCode: one error", r["errors"] == ["propertyCode is required."]))

r = validate({"propertyName": "Ascott Raffles Place Singapore"})
results.append(check("propertyName alone is no longer enough (not in 0.2.0)", r["errors"] == ["propertyCode is required."]))

body = {"propertyCode": "ABC-1"}
r = validate(body)
results.append(check("non-digit code rejected by schema and server",
                     not schema_ok(body) and r["errors"] == ['propertyCode must be digits only, such as "51052".']))

r = validate({"propertyCode": 51052})
results.append(check("numeric propertyCode accepted as \"51052\"", r["errors"] == [] and r["request"]["propertyCode"] == "51052"))

# The body from the UAT log of 2026-10-28 11:27 (the booking search shape sent to T-02).
mobile = {"messageId": "n:5", "memberId": "", "language": "en", "currencyCode": "USD", "promoCorpCode": "",
          "propertyListing": False, "isModifyJourney": False, "propertyCode": ["51052"], "checkinDate": ci,
          "checkoutDate": co, "voucherCode": "", "noOfRooms": 1, "noOfadults": "2", "noOfchildren": "0",
          "minPrice": "", "maxPrice": "", "perNightRate": True,
          "apartmentList": [{"childAges": [], "noOfadults": "2", "noOfchildren": "0"}], "userCountry": "SG",
          "isExcludePriceStartFrom": False, "channel": "mobile"}
r = validate(mobile)
results.append(check("booking search body (UAT 11:27): one-code array, string counts, extra fields ignored",
                     r["errors"] == [] and r["request"]["propertyCode"] == "51052" and r["request"]["checkin"] == ci
                     and r["request"]["adults"] == 2 and r["request"]["currency"] == "USD"))

r = validate({"propertyCode": ["51052", "8790"]})
results.append(check("two-code array rejected", r["errors"] == ['propertyCode must be one code, such as "51052".']))

r = validate({"propertyCode": "51052", "checkin": ci, "checkout": co, "adults": 3, "children": 1, "childAges": [6],
              "currency": "sgd", "maxPois": 2})
results.append(check("short names still accepted (MCP server mapping until redeployed), currency upper-cased",
                     r["errors"] == [] and r["request"]["adults"] == 3 and r["request"]["currency"] == "SGD"
                     and r["request"]["maxPois"] == 2 and r["request"]["childAges"] == [6]))

r = validate({"propertyCode": "51052", "checkinDate": ci, "checkin": "2099-01-01", "noOfadults": 2, "adults": 5})
results.append(check("schema name wins over the short name", r["request"]["checkin"] == ci and r["request"]["adults"] == 2))

body = {"propertyCode": "51052", "language": "pt"}
r = validate(body)
results.append(check("language outside the list: schema rejects, server falls back to default.language",
                     not schema_ok(body) and r["errors"] == [] and r["request"]["language"] == "en"))

r = validate({"propertyCode": "51052", "checkinDate": "10/12/2026"})
results.append(check("bad date format", r["errors"] == ["checkinDate must be a date in YYYY-MM-DD format."]))

r = validate({"propertyCode": "51052", "checkinDate": (TODAY - timedelta(days=1)).isoformat()})
results.append(check("past check-in", r["errors"] == ["checkinDate cannot be in the past."]))

r = validate({"propertyCode": "51052", "checkinDate": ci, "checkoutDate": ci})
results.append(check("same-day stay", r["errors"] == ["checkoutDate must be after checkinDate."]))

r = validate({"propertyCode": "51052", "checkinDate": ci, "checkoutDate": (TODAY + timedelta(days=60)).isoformat()})
results.append(check("stay over request.maxNights", r["errors"] == ["The stay cannot be longer than 30 nights."]))

r = validate({"propertyCode": "51052", "noOfadults": 0, "noOfchildren": 9, "currencyCode": "US$", "maxPois": 9})
results.append(check("bad counts, currency and maxPois each reported once", len(r["errors"]) == 4))

r = validate({"propertyCode": "51052", "noOfchildren": 2, "childAges": [3, 25]})
results.append(check("age above 17 rejected", r["errors"] == ["childAges must be whole numbers from 0 to 17."]))

r = validate({"propertyCode": "51052", "noOfchildren": 1, "childAges": 6})
results.append(check("childAges not an array", "childAges must be an array of ages." in r["errors"]))

r = validate("not an object")
results.append(check("non-object body", r["errors"][0] == "Request body must be a JSON object."))

print("\n%d/%d checks passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
