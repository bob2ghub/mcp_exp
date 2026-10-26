"""T-06 compare_properties: a Python copy of dwl/compare-properties-response.dwl, checked against schema 0.1.0.

The DataWeave is the implementation; this copy only exists so the mapping rules can be run here (no DataWeave runtime
in this session). Keep the two in step. It builds examples/compare-properties-response.sample.json from the real 51052
response plus two booking search samples, then runs not-found, on-request, listing-entry and POI cases and validates
every result against schemas/T06-compare-properties.structured-content.schema.json.

Run: python -I tests/check_t06.py   (needs: pip install jsonschema)
"""
import copy, json, math, re, sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/T06-compare-properties.structured-content.schema.json").read_text(encoding="utf-8"))
PROPS = {"t06.maxAmenityHighlights": 6, "property.currency": "SGD", "asset.baseUrl": "https://www.discoverasr.com"}

HIGHLIGHT_KEYWORDS = ["pool", "gym", "fitness", "spa", "business", "wifi", "internet", "breakfast",
                      "restaurant", "lounge", "parking", "laundry", "airport", "shuttle", "reception", "kitchen", "pet"]


def text(v):
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, (int, float)):
        return str(v)
    return None


def num(v):
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


def integer(v):
    n = num(v)
    return None if n is None else math.floor(n)


def boolean(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "y", "yes", "1")
    return None


def objects(v):
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def obj(v):
    return v if isinstance(v, dict) else {}


def money(n):
    if n is None:
        return None
    r = round(n * 100) / 100
    return int(r) if float(r).is_integer() else r


def at_least(n, lo):
    return n if (n is not None and n >= lo) else None


def first_text(o, keys):
    if not isinstance(o, dict):
        return None
    for k in keys:
        t = text(o.get(k))
        if t is not None:
            return t
    return None


def digits(v):
    s = text(v)
    return s if (s is not None and re.fullmatch(r"[0-9]+", s)) else None


def slug(v):
    s = re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", (text(v) or "").lower()))
    return s or None


def prune(o):
    if isinstance(o, dict):
        return {k: prune(v) for k, v in o.items() if v is not None}
    if isinstance(o, list):
        return [prune(x) for x in o]
    return o


def bookable(rp):
    template = (text(rp.get("ratePlanTemplate")) or "").upper()
    template_name = (text(rp.get("ratePlanTemplateName")) or "").lower()
    name = (text(rp.get("ratePlanName")) or "").lower()
    return (text(rp.get("ratePlanCode")) is not None and text(rp.get("ratePlanName")) is not None
            and not (template == "AOA" or "member" in template_name or "acrs compare" in name
                     or re.search(r"(^|[^a-z])test([^a-z]|$)", name)))


def highlight_rank(label):
    low = label.lower()
    for i, k in enumerate(HIGHLIGHT_KEYWORDS):
        if k in low:
            return i
    return len(HIGHLIGHT_KEYWORDS)


def amenity_highlights(src, max_amenities):
    groups = objects(obj(src.get("facilities")).get("facilityGroup"))
    preferred = [g for g in groups if (text(g.get("entityName")) or "").lower() == "facilities-amenities"]
    rest = [g for g in groups if (text(g.get("entityName")) or "").lower() != "facilities-amenities"]
    rows = []
    for g in preferred + rest:
        for f in objects(g.get("facilities")):
            en = boolean(f.get("enable"))
            if en is False:
                continue
            row = {"imagePath": text(f.get("imagePath")), "description": first_text(f, ["description", "name", "enName"])}
            if row["imagePath"] is not None and row["description"] is not None:
                rows.append(row)
    seen, uniq = set(), []
    for r in rows:
        key = r["description"].lower()
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    uniq.sort(key=lambda r: highlight_rank(r["description"]))
    return uniq[:max_amenities] or None


def nearby(lookup):
    pois = lookup.get("pois")
    if pois is None:
        pois = obj(lookup.get("property")).get("pois")
    rows = [{"title": first_text(poi, ["title", "name", "poiName"]),
             "icon_code": first_text(poi, ["icon_code", "iconCode", "icon", "emoji"]),
             "distance_minutes": at_least(integer(poi.get("distance_minutes") if poi.get("distance_minutes") is not None
                                                  else poi.get("distanceMinutes") if poi.get("distanceMinutes") is not None
                                                  else poi.get("walkMinutes")), 0)}
            for poi in objects(pois)]
    rows = [r for r in rows if r["title"] is not None and r["icon_code"] is not None]
    return rows or None


def card(lookup, max_amenities):
    src = obj(lookup.get("property"))
    rooms = [r for e in objects(src.get("apartments")) for v in e.values() for r in objects(v)]
    rates = [{"perNight": num(rp.get("perNightRatePrefCurr")) if num(rp.get("perNightRatePrefCurr")) is not None else num(rp.get("perNightRate")),
              "points": at_least(integer(rp.get("earnASRpoints")), 0)}
             for a in rooms for rp in objects(a.get("ratePlan")) if bookable(rp)]
    rates = sorted((r for r in rates if r["perNight"] is not None), key=lambda r: r["perNight"])
    lead = rates[0] if rates else {}
    per_night = lead.get("perNight")
    if per_night is None and not rooms:
        per_night = num(src.get("perNightRatePrefCurr"))
        if per_night is None:
            per_night = num(src.get("perNightRate"))
    city = first_text(src, ["cityName", "city"])
    country = first_text(src, ["countryName", "country"])
    if city is None:
        label = country
    elif country is None or country.lower() == city.lower():
        label = city
    else:
        label = city + ", " + country
    banner = first_text(src, ["bannerImageMobile", "newPropertyThumbnail"])
    if banner is None:
        gal = [t for t in (first_text(g, ["galleryImage", "path", "image"]) for g in objects(src.get("gallery"))) if t is not None]
        banner = gal[0] if gal else None
    asr = boolean(src.get("asrParticipating"))
    if asr is None:
        asr = boolean(src.get("isASR"))
    return {
        "property_code": digits(src.get("propertyCode")) or digits(lookup.get("code")),
        "property_name": first_text(src, ["propertyEnName", "propertyName"]),
        "brand_code": slug(src.get("brand")) or slug(src.get("brandName")) or "ascott",
        "banner_image_url": banner,
        "location_label": label,
        "amenity_highlights": amenity_highlights(src, max_amenities),
        "nearby": nearby(lookup),
        "availability_status": "available" if per_night is not None else "on_request",
        "per_night_rate": money(per_night),
        "is_asr_participating": asr if asr is not None else False,
        "earn_asr_points": None if per_night is None else lead.get("points"),
    }


def map_compare(lookups, req, props):
    def p(key):
        return props.get(key)

    m = p("t06.maxAmenityHighlights")
    max_amenities = m if (m is not None and m < 6) else 6
    cards = [c for c in (card(l, max_amenities) for l in lookups if l.get("status") == "ok")
             if c["property_code"] is not None and c["property_name"] is not None]

    ok_properties = [obj(l.get("property")) for l in lookups if l.get("status") == "ok"]
    currency = (text(req.get("currency"))
                or next((t for t in (text(x.get("currency")) for x in ok_properties) if t is not None), None)
                or p("property.currency") or "SGD").upper()
    labels = [c["location_label"] for c in cards if c["location_label"] is not None]
    child_ages = [x for x in (integer(v) for v in (req.get("childAges") if isinstance(req.get("childAges"), list) else [])) if x is not None]
    excluded = [e for e in ({"property_code": text(l.get("code")), "reason": "not_found"}
                            for l in lookups if l.get("status") == "not_found") if e["property_code"] is not None]
    out = {
        "meta": {
            "total_results": len(cards),
            "location_query": labels[0] if (len(labels) == len(cards) and len({x.lower() for x in labels}) == 1) else None,
            "currency": currency,
            "checkin_date": text(req.get("checkin")) or text(req.get("checkinDate")),
            "checkout_date": text(req.get("checkout")) or text(req.get("checkoutDate")),
            "noOfadults": at_least(integer(req.get("adults")) if integer(req.get("adults")) is not None else integer(req.get("noOfadults")), 1) or 1,
            "noOfchildren": (lambda n: 0 if n is None else n)(at_least(integer(req.get("children")) if integer(req.get("children")) is not None else integer(req.get("noOfchildren")), 0)),
            "childAges": child_ages if isinstance(req.get("childAges"), list) else None,
            "asset_base_url": p("asset.baseUrl") or "https://www.discoverasr.com",
        },
        "properties": cards,
        "excluded": excluded or None,
    }
    return prune(out)


VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def validate(label, doc):
    errs = sorted(VALIDATOR.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAIL %s" % label)
        for e in errs[:8]:
            print("   /%s: %s" % ("/".join(str(x) for x in e.path), e.message))
        return False
    print("ok   %s" % label)
    return True


def check(label, cond):
    print("%s %s" % ("ok  " if cond else "FAIL", label))
    return bool(cond)


real = json.loads((ROOT / "examples/upstream-property-details-51052.json").read_text(encoding="utf-8"))["propertyList"][0]
sample = json.loads((ROOT / "examples/compare-properties-upstream.sample.json").read_text(encoding="utf-8"))["propertyList"]
REQ = {"propertyCodes": ["51052", "8790", "8791"], "checkin": "2026-11-10", "checkout": "2026-11-12",
       "adults": 2, "children": 0, "currency": "SGD", "nights": 2}
lookups = ([{"code": "51052", "status": "ok", "source": "single", "property": real}]
           + [{"code": s["propertyCode"], "status": "ok", "source": "single", "property": s} for s in sample])
results = []

out = map_compare(lookups, REQ, PROPS)
(ROOT / "examples/compare-properties-response.sample.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
results.append(validate("three properties (51052 + two samples)", out))
results.append(check("cards in request order, total_results matches",
                     [c["property_code"] for c in out["properties"]] == ["51052", "8790", "8791"]
                     and out["meta"]["total_results"] == 3 and "excluded" not in out))
c0 = out["properties"][0]
results.append(check("51052 card: name, brand slug, banner, location line, ASR flag",
                     c0["property_name"] == "Ascott Raffles Place Singapore" and c0["brand_code"] == "ascott-the-residence"
                     and c0["banner_image_url"].endswith(".jpg") and c0["location_label"] == "Singapore"
                     and c0["is_asr_participating"] is True))
results.append(check("51052 price: cheapest bookable rate as upstream gives it, with its points",
                     c0["availability_status"] == "available" and c0["per_night_rate"] == 211.5
                     and c0["earn_asr_points"] == 4230))
results.append(check("highlights: at most 6, de-duplicated, the real highlights first",
                     [a["description"] for a in c0["amenity_highlights"]]
                     == ["Swimming pool", "Gymnasium", "Wireless internet connectivity (WiFi)",
                         "Daily continental breakfast", "Residents' lounge", "Laundry & dry cleaning services"]))
results.append(check("no reviews, no next_available_date, no nearby (T-06 does not call the POI system)",
                     all(k not in c0 for k in ("average_ratings", "total_number_of_reviews", "next_available_date", "nearby"))))
results.append(check("meta: one currency, the stay echoed, asset base url",
                     out["meta"]["currency"] == "SGD" and out["meta"]["checkin_date"] == "2026-11-10"
                     and out["meta"]["checkout_date"] == "2026-11-12" and out["meta"]["noOfadults"] == 2
                     and out["meta"]["asset_base_url"] == "https://www.discoverasr.com"
                     and "childAges" not in out["meta"]))

# A not-found code: still 2 cards, and the code is named in excluded.
lk = [lookups[0], {"code": "99999", "status": "not_found", "source": "single"}, lookups[1]]
r = map_compare(lk, REQ, PROPS)
results.append(validate("one code not found", r))
results.append(check("excluded names the code, the others are still compared",
                     r["excluded"] == [{"property_code": "99999", "reason": "not_found"}]
                     and r["meta"]["total_results"] == 2))

# A failed lookup has no slot in the schema's excluded: it is left out and logged instead.
lk = [lookups[0], lookups[1], {"code": "8791", "status": "unavailable", "source": "single"}]
r = map_compare(lk, REQ, PROPS)
results.append(validate("one lookup unavailable", r))
results.append(check("unavailable code is not in excluded", "excluded" not in r and r["meta"]["total_results"] == 2))

# No bookable rate: on_request, no price and no points banner.
no_rate = copy.deepcopy(real)
for rm in no_rate["apartments"][0]["room0"]:
    rm["ratePlan"] = [x for x in rm["ratePlan"] if x.get("ratePlanTemplate") == "AOA"]
r = map_compare([{"code": "51052", "status": "ok", "property": no_rate}, lookups[1]], REQ, PROPS)
results.append(validate("a property with no bookable rate", r))
results.append(check("on_request: no per_night_rate, no earn_asr_points",
                     r["properties"][0]["availability_status"] == "on_request"
                     and "per_night_rate" not in r["properties"][0] and "earn_asr_points" not in r["properties"][0]))

# A slim listing entry (the batch lookup's shape): no apartments, but a property-level lead-in rate.
listing = {"propertyCode": "8792", "propertyName": "Citadines Rochor Singapore", "brandName": "Citadines",
           "cityName": "Singapore", "countryName": "Singapore", "perNightRatePrefCurr": "175.00", "currency": "SGD"}
r = map_compare([lookups[0], {"code": "8792", "status": "ok", "source": "batch", "property": listing}], REQ, PROPS)
results.append(validate("a listing-style entry", r))
results.append(check("listing entry priced from the property-level rate, brand slug from brandName",
                     r["properties"][1]["per_night_rate"] == 175 and r["properties"][1]["brand_code"] == "citadines"
                     and "amenity_highlights" not in r["properties"][1]
                     and r["meta"]["location_query"] == "Singapore"))

# POIs, when a lookup carries them, and childAges echoed.
pois = [{"title": "Merlion Park", "iconCode": "\U0001f5fd", "walkMinutes": "5"},
        {"name": "Lau Pa Sat", "emoji": "\U0001f35c"},
        {"title": "No icon"}]
r = map_compare([dict(lookups[0], pois=pois), lookups[1]], dict(REQ, childAges=[4, "9"]), PROPS)
results.append(validate("POIs and childAges", r))
results.append(check("nearby built from the POIs, rows without an icon dropped; childAges echoed",
                     [n["title"] for n in r["properties"][0]["nearby"]] == ["Merlion Park", "Lau Pa Sat"]
                     and r["properties"][0]["nearby"][0]["distance_minutes"] == 5
                     and r["meta"]["childAges"] == [4, 9]))

# Properties in different cities: no shared location_query.
other = dict(sample[0], cityName="Kuala Lumpur", countryName="Malaysia")
r = map_compare([lookups[0], {"code": other["propertyCode"], "status": "ok", "property": other}], REQ, PROPS)
results.append(validate("different cities", r))
results.append(check("location_query only when every card shares a place",
                     "location_query" not in r["meta"] and r["properties"][1]["location_label"] == "Kuala Lumpur, Malaysia"))

sys.exit(0 if all(results) else 1)
