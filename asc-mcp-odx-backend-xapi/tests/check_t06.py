"""T-06 compare_properties: a Python copy of dwl/compare-properties-response.dwl, checked against the schema.

The DataWeave is the implementation; this copy only exists so the mapping rules can be run here (no DataWeave runtime in
this repo). Keep the two in step. It builds examples/compare-properties-response.sample.json from two booking search
samples, then runs not-found / on-request / T-02-shaped scenarios and validates every result against
schemas/T06-compare-properties.structured-content.schema.json.

Run: python -I tests/check_t06.py   (needs: pip install jsonschema)
"""
import copy, json, sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT.parent / "ascott.mcp.get-property-details.xapi/examples"
SCHEMA = json.loads((ROOT / "schemas/T06-compare-properties.structured-content.schema.json").read_text(encoding="utf-8"))
PROPS = {"t06.maxAmenityHighlights": 6, "t06.maxRoomTypes": 6, "property.currency": "SGD", "asset.baseUrl": "https://www.discoverasr.com"}


def text(v):
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, bool):
        return str(v).lower()
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


def intv(v):
    n = num(v)
    return None if n is None else int(n // 1)


def boolv(v):
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
    return None if n is None else round(n * 100) / 100


def first_text(o, keys):
    if not isinstance(o, dict):
        return None
    for k in keys:
        t = text(o.get(k))
        if t is not None:
            return t
    return None


def distinct_ci(items, key=lambda x: x):
    seen, out = set(), []
    for i in items:
        k = key(i).lower()
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


def bookable(rp):
    template = (text(rp.get("ratePlanTemplate")) or "").upper()
    template_name = (text(rp.get("ratePlanTemplateName")) or "").lower()
    name = (text(rp.get("ratePlanName")) or "").lower()
    return (text(rp.get("ratePlanCode")) is not None and text(rp.get("ratePlanName")) is not None
            and not (template == "AOA" or "member" in template_name or "acrs compare" in name))


def rate_of(rp, nights):
    stay = num(rp.get("totalStayRatePrefCurr"))
    total = None if stay is None else stay + (num(rp.get("totalTaxPrefCurrency")) or 0)
    per_night = None if total is None else total / nights
    tax_factor = total / stay if (stay is not None and stay > 0) else 1
    s = num(rp.get("strikethroughRatePrefCurr"))
    strike = None if s is None else s * tax_factor / nights
    return {"perNight": per_night, "total": total,
            "strike": strike if (strike is not None and per_night is not None and strike > per_night) else None}


def entry(lookup, req, currency):
    nights = req["nights"]
    src = obj(lookup.get("property"))
    rooms = [r for a in objects(src.get("apartments")) for r in objects(a.get("room0"))]
    rooms.sort(key=lambda r: intv(r.get("ranking")) if intv(r.get("ranking")) is not None else 999999)
    rated = []
    for a in rooms:
        rates = [x for x in (rate_of(rp, nights) for rp in objects(a.get("ratePlan")) if bookable(rp)) if x["perNight"] is not None and x["total"] is not None]
        if rates:
            rated.append({"room": a, "rates": rates})
    all_rates = sorted([x for r in rated for x in r["rates"]], key=lambda x: x["perNight"])
    cheapest = all_rates[0] if all_rates else None
    type_rooms = rooms if not rated else [r["room"] for r in rated]
    room_types = distinct_ci([t for t in ((text(r.get("apartmentName")) or text(r.get("apartmentType"))) for r in type_rooms) if t is not None])
    occ = [o for o in ((intv(r.get("maxOccupancy")) if intv(r.get("maxOccupancy")) is not None else intv(r.get("maxPersonInRoom"))) for r in rooms) if o is not None and o > 0]
    fac = obj(src.get("facilities"))
    groups = objects(fac.get("facilityGroup") or src.get("facilityGroup") or obj(src.get("amenities")).get("facilityGroup"))
    ordered = [g for g in groups if text(g.get("entityName")) == "facilities-amenities"] + [g for g in groups if text(g.get("entityName")) != "facilities-amenities"]
    amenities = distinct_ci([a for a in ({"label": first_text(f, ["description", "name"]), "icon_url": first_text(f, ["imagePath", "icon"])}
                                         for g in ordered for f in objects(g.get("facilities")) if boolv(f.get("enabled")) is not False) if a["label"] is not None],
                            key=lambda a: a["label"])
    loc = obj(src.get("location"))
    city = first_text(src, ["cityName", "city"]) or first_text(loc, ["city"])
    country = first_text(src, ["countryName"]) or first_text(loc, ["country"])
    reviews = obj(src.get("reviews"))
    avg = num(reviews.get("averageRatings", src.get("averageRatings")))
    cc = (first_text(src, ["countryCode"]) or first_text(loc, ["countryCode"]) or "").upper()
    parts = distinct_ci([p for p in (city, country) if p is not None])
    gallery0 = (objects(src.get("gallery")) or [None])[0]
    total_reviews = intv(reviews.get("totalNumberOfReviews", src.get("totalNumberOfReviews")))
    card = {
        "property_code": first_text(src, ["propertyCode"]) or lookup["code"],
        "property_name": first_text(src, ["propertyEnName", "propertyName"]) or lookup["code"],
        "is_asr": boolv(src.get("asrParticipating")),
        "property_type": first_text(src, ["propertyType"]),
        "brand_name": first_text(src, ["brandName"]),
        "brand_logo_url": first_text(src, ["brandlogo", "brandLogo"]),
        "banner_image_url": first_text(src, ["bannerImageMobile", "newPropertyThumbnail"]) or first_text(gallery0, ["path", "galleryImage"]),
        "card_location_line": ", ".join(parts) if parts else None,
        "rating": None if avg is None else {"average_ratings": min(max(avg, 0), 5),
                                             "total_number_of_reviews": total_reviews if (total_reviews is not None and total_reviews >= 0) else 0},
        "location": {"area_label": first_text(loc, ["areaLabel", "area", "neighbourhood"]) or city,
                     "district_label": first_text(loc, ["districtLabel", "district"]) or country,
                     "country_code": cc if len(cc) == 2 and cc.isalpha() else None},
        "max_person_in_room": max(occ) if occ else None,
        "room_types": room_types[:PROPS["t06.maxRoomTypes"]] or None,
        "amenity_highlights": amenities[:PROPS["t06.maxAmenityHighlights"]] or None,
        "pricing": {"availability_status": "on_request" if cheapest is None else "available",
                    "per_night_rate_pref_curr": money(cheapest and cheapest["perNight"]),
                    "strikethrough_rate": money(cheapest and cheapest["strike"]),
                    "total_stay_rate_pref_curr": money(cheapest and cheapest["total"]),
                    "currency": currency,
                    "next_available_date": None},
    }
    return {"code": lookup["code"], "status": lookup["status"], "city": city, "card": card}


def map_response(lookups, req):
    currency = (req.get("currency") or PROPS["property.currency"]).upper()
    entries = [entry(l, req, currency) for l in lookups]
    found = [e for e in entries if e["status"] == "ok"]
    cities = distinct_ci([e["city"] for e in found if e["city"] is not None])
    return {
        "meta": {"total_results": len(found), "location_query": ", ".join(cities) if cities else None, "currency": currency,
                 "checkin_date": req["checkin"], "checkout_date": req["checkout"], "nights": req["nights"],
                 "noOfadults": req["adults"], "noOfchildren": req["children"], "attribution": "discoverasr.com",
                 "asset_base_url": PROPS["asset.baseUrl"], "requested_property_codes": req["propertyCodes"],
                 "dropped_property_codes": req["droppedPropertyCodes"]},
        "properties": [e["card"] for e in found],
        "missing_properties": [
            {"property_code": e["code"], "reason_code": "not_found", "message": "No property data was returned for this code and these dates."}
            if e["status"] == "not_found" else
            {"property_code": e["code"], "reason_code": "lookup_failed", "message": "The property details service did not answer for this property."}
            for e in entries if e["status"] != "ok"],
    }


def validate(name, data):
    errors = sorted(Draft202012Validator(SCHEMA, format_checker=FormatChecker()).iter_errors(data), key=lambda e: list(e.path))
    for e in errors:
        print(f"FAIL {name}: /{'/'.join(map(str, e.path))}: {e.message}")
    return not errors


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    return cond


# ---------- inputs: the T-04 samples (8790 Citadines Balestier, 8791 lyf Funan) as one batch propertyList, 3 nights
p8790 = json.loads((REF / "upstream-room-rates.sample.json").read_text(encoding="utf-8"))["propertyList"][0]
p8791 = json.loads((REF / "upstream-room-rates-lyf-funan.sample.json").read_text(encoding="utf-8"))["propertyList"][0]
REQ = {"propertyCodes": ["8790", "8791"], "droppedPropertyCodes": [], "checkin": "2026-11-15", "checkout": "2026-11-18", "nights": 3,
       "adults": 2, "children": 0, "currency": "SGD", "language": "en"}
ok = lambda p: {"code": p["propertyCode"], "status": "ok", "source": "batch", "property": p}

results = []
base = map_response([ok(p8790), ok(p8791)], REQ)
(ROOT / "examples").mkdir(exist_ok=True)
(ROOT / "examples/compare-properties-upstream.sample.json").write_text(json.dumps({"messageId": "sample", "propertyList": [p8790, p8791]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
(ROOT / "examples/compare-properties-request.json").write_text(json.dumps({"propertyCodes": ["8790", "8791"], "checkinDate": "2026-11-15", "checkoutDate": "2026-11-18", "noOfadults": "2", "noOfchildren": "0", "currencyCode": "SGD"}, indent=2) + "\n", encoding="utf-8")
(ROOT / "examples/compare-properties-response.sample.json").write_text(json.dumps(base, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
results.append(check("sample validates", validate("sample", base)))
results.append(check("cards in request order", [c["property_code"] for c in base["properties"]] == ["8790", "8791"]))
results.append(check("no comparison fields", "recommendation" not in base and all("is_recommended" not in c for c in base["properties"])))
results.append(check("one currency (AC-07)", {c["pricing"]["currency"] for c in base["properties"]} == {base["meta"]["currency"]}))
results.append(check("same keys on every card (EC-10)", len({tuple(c.keys()) for c in base["properties"]}) == 1))
results.append(check("8791 price = T-04 cheapest (900 + 179.10) / 3", base["properties"][1]["pricing"]["per_night_rate_pref_curr"] == 359.7))

r = map_response([ok(p8790), {"code": "99999", "status": "not_found", "source": "single"}, {"code": "12345", "status": "unavailable", "source": "single"}], {**REQ, "propertyCodes": ["8790", "99999", "12345"]})
results.append(check("not found / unavailable validate", validate("partial", r)))
results.append(check("missing codes listed with reasons", len(r["properties"]) == 1 and [x["reason_code"] for x in r["missing_properties"]] == ["not_found", "lookup_failed"]))

no_rates = copy.deepcopy(p8791)
for a in no_rates["apartments"]:
    for room in a["room0"]:
        room["ratePlan"] = []
r = map_response([ok(p8790), ok(no_rates)], REQ)
results.append(check("on request validates", validate("on_request", r)))
results.append(check("on request card keeps price keys as null (ER-08)", r["properties"][1]["pricing"]["availability_status"] == "on_request" and r["properties"][1]["pricing"]["per_night_rate_pref_curr"] is None))

p50926 = json.loads((REF / "upstream-property-details.sample.json").read_text(encoding="utf-8"))
r = map_response([ok(p50926), ok(p8790)], {**REQ, "propertyCodes": ["50926", "8790"]})
results.append(check("T-02 shaped property validates", validate("t02_shape", r)))
c = r["properties"][0]
results.append(check("T-02 shaped property: brand, image, location, rating, amenities filled",
                     all(c[k] is not None for k in ("brand_logo_url", "banner_image_url", "card_location_line", "rating", "amenity_highlights", "is_asr"))))
print(json.dumps(c, indent=2, ensure_ascii=False))

sys.exit(0 if all(results) else 1)
