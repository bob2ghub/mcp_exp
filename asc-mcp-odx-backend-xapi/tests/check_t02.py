"""T-02 get_property_details: a Python copy of dwl/map-structured-content.dwl, checked against schema 0.6.0.

The DataWeave is the implementation; this copy exists so the mapping can be run here (no DataWeave runtime in this repo).
Keep the two in step, function for function. It maps the real booking search response for 51052
(examples/upstream-property-details-51052.json), writes examples/property-details-51052-response.sample.json and
validates it, then runs edge cases (no request, no rate, POIs, missing optional blocks) and validates each.

Run: python -I tests/check_t02.py   (needs: pip install jsonschema)
"""
import copy, datetime, json, re, sys
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/T02-get-property-details.structured-content.schema.json").read_text(encoding="utf-8"))
PROPS = {"asset.baseUrl": "https://www.discoverasr.com", "default.currency": "SGD"}  # t02.bestrateguaranteedtext unset by default


def p(key, props):
    return props.get(key)


# ---------- helpers (same names and rules as the DataWeave)
def text(v):
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, bool):
        return "true" if v else "false"
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
            f = float(v.strip())
            return int(f) if f.is_integer() and "." not in v else f
        except ValueError:
            return None
    return None


def intv(v):
    n = num(v)
    return None if n is None else int(n // 1)


def positive(v):
    n = num(v)
    return n if (n is not None and n > 0) else None


def boolv(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "y", "yes", "1")
    if isinstance(v, (int, float)):
        return v != 0
    return None


def objects(v):
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def obj(v):
    return v if isinstance(v, dict) else {}


def non_empty(a):
    return a if a else None


def first(o, keys):
    if not isinstance(o, dict):
        return None
    for k in keys:
        t = text(o.get(k))
        if t is not None:
            return t
    return None


def dflt(*vals):
    """DataWeave `a default b default c`: the first non-null."""
    for v in vals:
        if v is not None:
            return v
    return None


def slug(v):
    s = re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", (text(v) or "").lower()))
    return s or None


def plain(v):
    s = text(v)
    if s is None:
        return None
    out = re.sub(r"\s+", " ", re.sub(r"&nbsp;|&#160;", " ", re.sub(r"<[^>]*>", " ", s))).strip()
    return out or None


def time24(v):
    s = re.sub(r"\s+", "", (text(v) or "").upper())
    m = re.match(r"^([0-9]{1,2}):([0-5][0-9])(:([0-5][0-9]))?(AM|PM)?$", s)
    if not m:
        return None
    h, mer = int(m.group(1)), m.group(5) or ""
    h24 = (0 if h == 12 else h) if mer == "AM" else (12 if h == 12 else h + 12) if mer == "PM" else h
    if h24 < 0 or h24 > 23:
        return None
    return f"{h24:02d}:{m.group(2)}"


def iso_date(v):
    s = text(v)
    if s is None:
        return None
    try:
        return datetime.date.fromisoformat(s[0:10]).isoformat()
    except ValueError:
        return None


def us_date(v):
    s = text(v)
    if s is None:
        return None
    try:
        return datetime.datetime.strptime(s, "%m/%d/%Y").date()
    except ValueError:
        return None


def clamp05(n):
    return 0 if n < 0 else 5 if n > 5 else n


def coords(la, lo):
    la, lo = num(la), num(lo)
    if la is None or lo is None or la < -90 or la > 90 or lo < -180 or lo > 180:
        return None
    return {"latitude": la, "longitude": lo}


def skip_nulls(v):
    """skipNullOn="everywhere"."""
    if isinstance(v, dict):
        return {k: skip_nulls(x) for k, x in v.items() if x is not None}
    if isinstance(v, list):
        return [skip_nulls(x) for x in v if x is not None]
    return v


def poi_groups_of(v):
    if isinstance(v, list):
        return [g for x in v for g in poi_groups_of(x)]
    if isinstance(v, dict):
        return [v] if isinstance(v.get("pois"), list) else [g for x in v.values() for g in poi_groups_of(x)]
    return []


def titled(g, property_name):
    t, d = first(g, ["title"]), first(g, ["description"])
    return None if (t is None or d is None) else {"title": t.replace("{0}", property_name), "description": d}


def map_property(src, req, pois, props=PROPS, property_code_var=None):
    src, req = obj(src), obj(req)
    loc = obj(src.get("location"))
    rate_plans = [rp for a in objects(src.get("apartments")) for r in objects(a.get("room0")) for rp in objects(r.get("ratePlan"))]

    property_code = dflt(first(src, ["propertyCode"]), text(property_code_var), text(req.get("propertyCode")))
    property_name = dflt(first(src, ["propertyEnName", "propertyName"]), text(req.get("propertyName")), property_code)
    gallery_src = objects(src.get("gallery"))
    banner = first(src, ["bannerImageMobile"])
    rooms = [r for a in objects(src.get("apartments")) for r in objects(a.get("room0"))]
    thumbnail = dflt(first(src, ["newPropertyThumbnail"]), banner, first(gallery_src[0] if gallery_src else None, ["path", "galleryImage"]),
                     first(rooms[0] if rooms else None, ["thumbnailImage", "bannerImageMobile"]), first(obj(src.get("location")), ["mapImage"]))

    per_night = dflt(positive(src.get("perNightRatePrefCurr")), positive(src.get("perNightRate")))
    total_stay = dflt(positive(src.get("totalStayRatePrefCurr")), positive(src.get("totalStayRate")))
    strikes = [dflt(positive(rp.get("strikethroughRatePrefCurr")), positive(rp.get("strikethroughRate")))
               for rp in rate_plans if dflt(positive(rp.get("perNightRatePrefCurr")), positive(rp.get("perNightRate"))) == per_night]
    strikes = [s for s in strikes if s is not None]
    strike = dflt(positive(src.get("strikethroughRatePrefCurr")), positive(src.get("strikethroughRate")), strikes[0] if strikes else None)
    currency_in = (first(src, ["currency", "currencyCode"]) or "").upper()
    currency = currency_in if re.fullmatch(r"[A-Z]{3}", currency_in) else (dflt(text(req.get("currency")), p("default.currency", props), "SGD")).upper()
    nightly = sorted(d for d in (us_date(n.get("date")) for rp in rate_plans for n in objects(rp.get("nightlyRate"))) if d is not None)
    checkin = dflt(iso_date(req.get("checkin")), nightly[0].isoformat() if nightly else None)
    checkout = dflt(iso_date(req.get("checkout")), (nightly[-1] + datetime.timedelta(days=1)).isoformat() if nightly else None)
    a = intv(req.get("adults"))
    adults = a if (a is not None and a >= 1) else 1
    c = intv(req.get("children"))
    children = c if (c is not None and c >= 0) else 0
    child_ages = [x for x in (intv(v) for v in (req.get("childAges") if isinstance(req.get("childAges"), list) else [])) if x is not None and x >= 0]

    fac = obj(src.get("facilities"))
    groups_raw = dflt(fac.get("facilityGroup"), src.get("facilityGroup"), obj(src.get("amenities")).get("facilityGroup"))
    groups_in = []
    for g in objects(groups_raw):
        facs, seen_local = [], set()
        for f in objects(g.get("facilities")):
            row = {"description": first(f, ["description", "name", "enName"]),
                   "imagePath": first(f, ["imagePath", "image_path", "facilityIcon", "icon"]),
                   "charge": first(f, ["charge"]),
                   "enabled": dflt(boolv(f.get("enable")), boolv(f.get("enabled")))}
            if row["description"] is None or row["imagePath"] is None or row["description"].lower() in seen_local:
                continue
            seen_local.add(row["description"].lower())
            facs.append(row)
        groups_in.append({"entity_name": first(g, ["entityName", "entity_name"]), "entity_title": first(g, ["entityTitle", "entity_title"]), "facilities": facs})
    groups_in = [g for g in groups_in if g["entity_name"] is not None]
    seen, facility_groups = set(), []
    for g in groups_in:
        fresh = [f for f in g["facilities"] if f["description"].lower() not in seen]
        seen.update(f["description"].lower() for f in fresh)
        if fresh:
            facility_groups.append({"entity_name": g["entity_name"], "entity_title": g["entity_title"], "facilities": fresh})

    staff = obj(src.get("staffLanguages"))
    languages = []
    for l in (staff.get("languages") if isinstance(staff.get("languages"), list) else []):
        t = text(l)
        if t is not None and t not in languages:
            languages.append(t)

    items = [i for t in objects(src.get("tag")) for i in objects(obj(t.get("susstainable")).get("allItems")) + objects(obj(t.get("susstainable")).get("sustainableItems"))]
    acc = [i for i in items if (first(i, ["identityName", "label"]) or "").lower() == "accessibility"]
    accessibility = acc[0] if acc else None

    groups = poi_groups_of(pois)
    matching = [g for g in groups if first(g, ["propertyCode", "property_code"]) == property_code]
    poi_group = matching[0] if matching else (groups[0] if len(groups) == 1 else None)
    nearby = []
    for poi in objects(obj(poi_group).get("pois")):
        m = num(dflt(poi.get("distanceMinutes"), poi.get("distance_minutes")))
        n = {"poi_id": first(poi, ["poiId", "poi_id"]), "title": first(poi, ["poiName", "title", "name"]),
             "category": first(poi, ["poiCategory", "category"]), "type": first(poi, ["poiType", "type"]),
             "icon_code": first(poi, ["iconCode", "icon_code"]),
             "coordinates": coords(dflt(poi.get("latitude"), obj(poi.get("coordinates")).get("latitude")), dflt(poi.get("longitude"), obj(poi.get("coordinates")).get("longitude"))),
             "address": first(poi, ["poiAddress", "address"]),
             "distance_minutes": round(m) if (m is not None and m >= 0) else None}
        if all(n[k] is not None for k in ("poi_id", "title", "category", "type", "icon_code", "coordinates")):
            nearby.append(n)
    nearby = nearby[:5]

    reviews_src = obj(src.get("reviews"))
    r_avg = num(dflt(reviews_src.get("averageRatings"), src.get("averageRatings")))
    r_tot = intv(dflt(reviews_src.get("totalNumberOfReviews"), src.get("totalNumberOfReviews")))
    cc = (dflt(first(src, ["countryCode"]), first(loc, ["countryCode"])) or "").upper()
    acc_title = first(accessibility, ["sustainableLabel", "label", "identityName"])
    acc_body = plain(obj(accessibility).get("tooltip"))
    individual = []
    for r in objects(reviews_src.get("individualReviews")):
        rn = num(dflt(r.get("rating"), r.get("score")))
        row = {"reviewer_name": first(r, ["reviewerName", "name"]), "rating": None if rn is None else clamp05(rn),
               "posted_date": iso_date(dflt(r.get("postedDate"), r.get("date"))), "source": first(r, ["source"]),
               "text": first(r, ["text", "reviewText", "comment"])}
        if row["reviewer_name"] is not None and row["rating"] is not None and row["text"] is not None:
            individual.append(row)

    out = {
        "property_code": property_code,
        "property_name": property_name,
        "brand_code": dflt(slug(src.get("brand")), slug(src.get("brandName")), "ascott"),
        "brand_name": dflt(first(src, ["brandName"]), "Ascott"),
        "brand_logo_url": dflt(first(src, ["brandlogo", "brandLogo"]), ""),
        "banner_image_url": banner,
        "thumbnail_url": thumbnail,
        "property_type": dflt(first(src, ["propertyType"]), ""),
        "asr_participating": dflt(boolv(src.get("asrParticipating")), False),
        "email": first(src, ["email"]),
        "phone": first(src, ["phone", "phoneNumber"]),
        "tags": non_empty([t for t in ({"propertyTagTitle": first(t, ["propertyTagTitle", "title"]),
                                        "propertyTagPresent": dflt(boolv(t.get("propertyTagPresent")), False)} for t in objects(src.get("tag")))
                           if t["propertyTagTitle"] is not None]),
        "description_title": first(src, ["descriptionTitle"]),
        "description": first(src, ["description"]),
        "gallery": non_empty([g for g in ({"path": first(g, ["path", "galleryImage"]), "gallery_image": first(g, ["galleryImage"]),
                                           "gallery_type": dflt(first(g, ["galleryType"]), "image"), "title": dflt(first(g, ["title"]), property_name)}
                                          for g in gallery_src) if g["path"] is not None]),
        "pricing": {
            "availability_status": "on_request" if per_night is None else "available",
            "per_night_rate_pref_curr": per_night,
            "total_stay_rate_pref_curr": total_stay,
            "strikethrough_rate": strike if (strike is not None and per_night is not None and strike > per_night) else None,
            "currency": currency,
            "next_available_date": None,
            "based_on": {"checkin": checkin, "checkout": checkout, "adults": adults, "children": children, "child_ages": non_empty(child_ages)},
        },
        "location": {
            "city": dflt(first(src, ["cityName", "city"]), first(loc, ["city", "cityName"])),
            "country": dflt(first(src, ["countryName"]), first(loc, ["country", "countryName"])),
            "country_code": cc if re.fullmatch(r"[A-Z]{2}", cc) else None,
            "address": dflt(first(src, ["address"]), first(loc, ["address"])),
            "local_address": dflt(first(src, ["localAddress"]), first(loc, ["localAddress"])),
            "coordinates": coords(dflt(loc.get("latitude"), src.get("latitude"), obj(loc.get("coordinates")).get("latitude")),
                                  dflt(loc.get("longitude"), src.get("longitude"), obj(loc.get("coordinates")).get("longitude"))),
            "map_image_url": dflt(first(loc, ["mapImage"]), first(src, ["mapImage"])),
            "getting_to_property": titled(obj(dflt(loc.get("gettingToProperty"), src.get("gettingToProperty"))), property_name),
            "public_transport": titled(obj(dflt(loc.get("publicTransport"), src.get("publicTransport"))), property_name),
        },
        "amenities": {"facility_groups": facility_groups},
        "reviews": {
            "average_ratings": 0 if r_avg is None else clamp05(r_avg),
            "total_number_of_reviews": r_tot if (r_tot is not None and r_tot >= 0) else 0,
            "score_label": first(reviews_src, ["scoreLabel"]),
            "individual_reviews": non_empty(individual),
        },
        "hotel_information": {
            "check_in_time": time24(src.get("checkInTime")),
            "check_out_time": time24(src.get("checkOutTime")),
            "staff_languages": None if not languages else {"title": first(staff, ["title"]), "languages": languages},
            "cancellation_policy": first(src, ["cancellationPolicy"]),
            "best_rate_guaranteed": text(p("t02.bestrateguaranteedtext", props)) if dflt(boolv(src.get("isBestRateGuaranteeEnabled")), False) else None,
        },
        "nearby": nearby,
        "asset_base_url": dflt(p("asset.baseUrl", props), "https://www.discoverasr.com"),
        "accessibility_note": None if (acc_title is None or acc_body is None) else {"title": acc_title, "body": acc_body},
        "awards": non_empty([a for a in ({"image": first(a, ["image", "imagePath", "path"]), "label": first(a, ["title", "label", "name"])}
                                         for a in objects(src.get("listOfAwards"))) if a["image"] is not None]),
    }
    return skip_nulls(out)


def validate(name, data):
    errors = sorted(Draft202012Validator(SCHEMA, format_checker=FormatChecker()).iter_errors(data), key=lambda e: list(e.path))
    for e in errors:
        print(f"FAIL {name}: /{'/'.join(map(str, e.path))}: {e.message[:150]}")
    if not errors:
        print(f"ok   {name} validates against T-02 {SCHEMA['$id'].rsplit(':', 1)[-1]}")
    return not errors


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    return cond


upstream = json.loads((ROOT / "examples/upstream-property-details-51052.json").read_text(encoding="utf-8"))
src = upstream["propertyList"][0]
REQ = {"propertyCode": "51052", "checkin": "2026-11-10", "checkout": "2026-11-12", "adults": 2, "children": 0, "currency": "SGD", "language": "en", "maxPois": 5}

results = []
out = map_property(src, REQ, None)
(ROOT / "examples/property-details-51052-response.sample.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
results.append(validate("51052 real payload", out))
results.append(check("lead-in 211.50 / stay 423.00, strikethrough 940 from the ASRAPPFX plan",
                     out["pricing"]["per_night_rate_pref_curr"] == 211.5 and out["pricing"]["total_stay_rate_pref_curr"] == 423 and out["pricing"]["strikethrough_rate"] == 940))
results.append(check("brand_code slugged from brandName", out["brand_code"] == "ascott-the-residence"))
results.append(check("03:00 PM -> 15:00, 12:00 PM -> 12:00", out["hotel_information"]["check_in_time"] == "15:00" and out["hotel_information"]["check_out_time"] == "12:00"))
results.append(check("coordinates are numbers", out["location"]["coordinates"] == {"latitude": 1.28222, "longitude": 103.851721}))
results.append(check("{0} placeholder replaced", "{0}" not in json.dumps(out["location"])))
results.append(check("gallery titles fall back to the property name", all(g["title"] == "Ascott Raffles Place Singapore" for g in out["gallery"])))
results.append(check("banner_multifield group and null facilities dropped", all(g["entity_name"] != "banner_multifield_facilities" for g in out["amenities"]["facility_groups"])))
results.append(check("Residents' lounge kept via name (description is null)",
                     any(f["description"] == "Residents' lounge" for g in out["amenities"]["facility_groups"] for f in g["facilities"])))
all_desc = [f["description"].lower() for g in out["amenities"]["facility_groups"] for f in g["facilities"]]
results.append(check("facilities de-duplicated across groups", len(all_desc) == len(set(all_desc))))
results.append(check("empty sections kept: reviews zeroes, nearby []", out["reviews"] == {"average_ratings": 0, "total_number_of_reviews": 0} and out["nearby"] == []))
results.append(check("accessibility note is plain text", "<" not in out["accessibility_note"]["body"]))

r = map_property(src, {"propertyCode": "51052"}, None)
results.append(validate("no stay in request (dates from nightlyRate)", r))
results.append(check("fallback stay 2026-11-10 to 2026-11-12", r["pricing"]["based_on"]["checkin"] == "2026-11-10" and r["pricing"]["based_on"]["checkout"] == "2026-11-12"))

r = map_property(src, {**REQ, "children": 2, "childAges": [4, "7"]}, None)
results.append(validate("childAges", r))
results.append(check("child_ages passed through as integers", r["pricing"]["based_on"]["child_ages"] == [4, 7]))

no_rate = copy.deepcopy(src)
for k in ("perNightRate", "totalStayRate", "perNightRatePrefCurr", "totalStayRatePrefCurr"):
    no_rate[k] = ""
r = map_property(no_rate, REQ, None)
results.append(validate("no rate (on_request)", r))
results.append(check("on_request has no price fields", r["pricing"]["availability_status"] == "on_request" and "per_night_rate_pref_curr" not in r["pricing"]))

pois = {"propertyList": [{"propertyCode": "51052", "pois": [
    {"poiId": f"poi-51052-0{i}", "poiName": f"Place {i}", "poiCategory": "Landmarks & Outdoors", "poiType": "Park", "iconCode": "🌳",
     "latitude": "1.2876", "longitude": "103.8545", "poiAddress": "Singapore", "distanceMinutes": 5 + i} for i in range(1, 8)]
    + [{"poiId": "bad", "poiName": "No coords", "poiCategory": "x", "poiType": "y", "iconCode": "z"}]}]}
r = map_property(src, REQ, pois)
results.append(validate("with POIs", r))
results.append(check("nearby capped at 5, invalid POI dropped", len(r["nearby"]) == 5 and all(n["poi_id"] != "bad" for n in r["nearby"])))

r = map_property(src, REQ, None, props={**PROPS, "t02.bestrateguaranteedtext": "Applicable under property's Terms and conditions"})
results.append(validate("best_rate_guaranteed text set", r))
results.append(check("best_rate_guaranteed emitted when the property key is set", r["hotel_information"].get("best_rate_guaranteed", "").startswith("Applicable")))

bare = {k: src[k] for k in ("propertyCode", "propertyName", "address", "location")}
r = map_property(bare, REQ, None)
results.append(validate("bare property (only code, name, address, location)", r))

sys.exit(0 if all(results) else 1)
