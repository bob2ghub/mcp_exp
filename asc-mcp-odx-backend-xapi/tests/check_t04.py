"""T-04 get_room_rate_details: a Python copy of dwl/room-rate-details.dwl, checked against schema 0.3.0.

The DataWeave is the implementation; keep this copy in step with it. It maps the real 51052 response
(examples/upstream-property-details-51052.json), writes examples/room-rate-details-51052-response.sample.json and
validates it, then runs edge cases. Run: python -I tests/check_t04.py   (needs: pip install jsonschema)
"""
import copy, json, math, re, sys
from datetime import datetime, timedelta
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/T04-get-room-rate-details.structured-content.schema.json").read_text(encoding="utf-8"))


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
        return v.strip().lower() == "true"
    return None


def objects(v):
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def money(n):
    if n is None:
        return None
    r = round(n * 100) / 100
    return int(r) if float(r).is_integer() else r


def at_least(n, lo):
    return n if (n is not None and n >= lo) else None


def slug(v):
    s = re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", (text(v) or "").lower()))
    return s or None


def prune(o):
    """skipNullOn=\"everywhere\": drop null keys."""
    if isinstance(o, dict):
        return {k: prune(v) for k, v in o.items() if v is not None}
    if isinstance(o, list):
        return [prune(x) for x in o]
    return o


def bookable(rp):
    template = (text(rp.get("ratePlanTemplate")) or "").upper()
    template_name = (text(rp.get("ratePlanTemplateName")) or "").lower()
    name = (text(rp.get("ratePlanName")) or "").lower()
    return not (template == "AOA"
                or "member" in template_name
                or "acrs compare" in name
                or re.search(r"(^|[^a-z])test([^a-z]|$)", name))


def rate_plan(rp):
    inclusive = boolean(rp.get("isTaxInclusive"))
    inclusive = False if inclusive is None else inclusive
    per_night = num(rp.get("perNightRatePrefCurr"))
    if per_night is None:
        per_night = num(rp.get("perNightRate"))
    stay = num(rp.get("totalStayRatePrefCurr"))
    if stay is None:
        stay = num(rp.get("totalStayRate"))
    if inclusive:
        per_night_tax, total_tax = 0, 0
    else:
        per_night_tax = sum((num(t.get("taxAmountPrefCurrPerNight")) if num(t.get("taxAmountPrefCurrPerNight")) is not None
                             else num(t.get("taxAmountPerNight")) if num(t.get("taxAmountPerNight")) is not None else 0)
                            for t in objects(rp.get("taxes")))
        total_tax = num(rp.get("totalTaxPrefCurrency"))
        if total_tax is None:
            total_tax = num(rp.get("totalTax"))
        if total_tax is None:
            total_tax = 0
    channel = (text(rp.get("ratePlanChannel")) or "").upper()
    return {
        "rate_plan_code": text(rp.get("ratePlanCode")),
        "rate_plan_name": text(rp.get("ratePlanName")),
        "description": text(rp.get("ratePlanDescription")),
        "is_tax_inclusive": inclusive,
        "per_night_rate": money(per_night),
        "total_stay_rate": money(stay),
        "per_night_tax": money(per_night_tax),
        "total_tax": money(total_tax),
        "earn_asr_points": at_least(integer(rp.get("earnASRpoints")), 0),
        "non_refundable": boolean(rp.get("nonRefundable")),
        "cancellation_description": text(rp.get("cancellationDescription")),
        "is_app_exclusive": None if channel == "" else channel == "MOBILE",
    }


def room(a):
    gallery = [g for g in ({"path": text(i.get("galleryImage")) or text(i.get("path")), "title": text(i.get("title"))}
                           for i in objects(a.get("imageGalleryItems"))
                           if (text(i.get("galleryType")) or "image").lower() == "image")
               if g["path"] is not None]
    groups = [g for g in ({"group": text(x.get("refAmenityGroup")),
                           "amenities": [d for d in ((text(y.get("description")) or text(y.get("name")))
                                                     for y in objects(x.get("amenities"))) if d is not None]}
                          for x in objects(a.get("amenityGroups")))
              if g["group"] is not None and g["amenities"]]
    dim = num(a.get("dimension"))
    plans = [rp for rp in (rate_plan(x) for x in objects(a.get("ratePlan")) if bookable(x))
             if rp["rate_plan_code"] is not None and rp["rate_plan_name"] is not None
             and rp["per_night_rate"] is not None and rp["total_stay_rate"] is not None]
    plans.sort(key=lambda rp: rp["per_night_rate"])
    return {
        "room_code": text(a.get("apartmentType")),
        "room_name": text(a.get("apartmentName")),
        "room_category": text(a.get("apartmentCategoryCode")),
        "ranking": at_least(integer(a.get("ranking")), 1),
        "description": text(a.get("roomInformation")),
        "bed_type": text(a.get("bedType")),
        "max_person_in_room": text(a.get("maxPersonInRoom")),
        "max_occupancy": at_least(integer(a.get("maxOccupancy")), 1),
        "size_sqm": dim if (dim is not None and dim > 0) else None,
        "units_remaining": at_least(integer(a.get("noOfUnitRemaining")), 0),
        "thumbnail_url": text(a.get("thumbnailImage")),
        "banner_image_url": text(a.get("bannerImageMobile")),
        "floor_plan_url": text(a.get("floorPlanPath")),
        "gallery": gallery or None,
        "amenity_groups": groups or None,
        "rate_plans": plans,
    }


def map_rooms(src, req, props):
    def p(key):
        return props.get(key)

    rows = objects(req.get("apartmentList"))
    if not rows:
        rows = [{"noOfadults": req.get("adults"), "noOfchildren": req.get("children"), "childAges": req.get("childAges")}]

    def upstream_rooms(index):
        key = "room%d" % index
        return [r for e in objects(src.get("apartments")) for r in objects(e.get(key))]

    requested = []
    for i, spec in enumerate(rows):
        rooms = [r for r in (room(a) for a in upstream_rooms(i))
                 if r["room_code"] is not None and r["room_name"] is not None and r["rate_plans"]]
        rooms.sort(key=lambda r: r["ranking"] if r["ranking"] is not None else 999999)
        adults = at_least(integer(spec.get("noOfadults")) if integer(spec.get("noOfadults")) is not None else integer(spec.get("adults")), 1) or 1
        ch = integer(spec.get("noOfchildren")) if integer(spec.get("noOfchildren")) is not None else integer(spec.get("children"))
        children = at_least(ch, 0)
        children = 0 if children is None else children
        ages = [x for x in (integer(v) for v in (spec.get("childAges") if isinstance(spec.get("childAges"), list) else [])) if x is not None]
        requested.append({
            "room_index": i + 1,
            "noOfadults": adults,
            "noOfchildren": children,
            "childAges": ages,
            "total_results": len(rooms),
            "rooms": rooms,
        })

    all_rooms = [r for e in objects(src.get("apartments")) for v in e.values() for r in objects(v)]

    def us_date(v):
        s = text(v)
        if s is None:
            return None
        try:
            return datetime.strptime(s, "%m/%d/%Y").date()
        except ValueError:
            return None

    night_dates = sorted(d for d in (us_date(n.get("date"))
                                     for a in all_rooms for rp in objects(a.get("ratePlan"))
                                     for n in objects(rp.get("nightlyRate"))) if d is not None)
    stay_from = night_dates[0].isoformat() if night_dates else None
    stay_to = (night_dates[-1] + timedelta(days=1)).isoformat() if night_dates else None

    country = (text(src.get("countryCode")) or "").upper()
    lead_rate = (objects(all_rooms[0].get("ratePlan")) if all_rooms else [{}]) or [{}]
    currency = (text(req.get("currency")) or text(req.get("currencyCode")) or text(src.get("currency"))
                or text(lead_rate[0].get("currency")) or p("property.currency") or "SGD").upper()
    out = {
        "meta": {
            "property_code": text(src.get("propertyCode")) or text(req.get("propertyCode")),
            "property_name": text(src.get("propertyEnName")) or text(src.get("propertyName")) or text(req.get("propertyCode")),
            "brand_code": slug(src.get("brand")) or slug(src.get("brandName")) or "ascott",
            "country_code": country if re.fullmatch(r"[A-Z]{2}", country) else None,
            "asset_base_url": p("asset.baseUrl") or "https://www.discoverasr.com",
            "checkin_date": text(req.get("checkin")) or text(req.get("checkinDate")) or stay_from,
            "checkout_date": text(req.get("checkout")) or text(req.get("checkoutDate")) or stay_to,
            "noOfadults": sum(r["noOfadults"] for r in requested),
            "noOfchildren": sum(r["noOfchildren"] for r in requested),
            "noOfRooms": len(requested),
            "is_all_avail": boolean(src.get("isAllAvail")),
            "currency": currency,
            "price_includes_tax": boolean(req.get("priceIncludesTax")),
            "voucher_code_valid": None if text(req.get("voucherCode")) is None else (boolean(src.get("isCodeValid")) or False),
        },
        "requested_rooms": requested,
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


src = json.loads((ROOT / "examples/upstream-property-details-51052.json").read_text(encoding="utf-8"))["propertyList"][0]
PROPS = {"asset.baseUrl": "https://www.discoverasr.com", "property.currency": "SGD"}
REQ = {"propertyCode": "51052", "checkin": "2026-11-10", "checkout": "2026-11-12", "adults": 2, "children": 0, "currency": "SGD"}
results = []

out = map_rooms(src, REQ, PROPS)
(ROOT / "examples/room-rate-details-51052-response.sample.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
results.append(validate("51052 real payload", out))
rr = out["requested_rooms"]
results.append(check("one requested room, 4 room types in ranking order",
                     len(rr) == 1 and rr[0]["room_index"] == 1 and rr[0]["total_results"] == 4
                     and [r["room_code"] for r in rr[0]["rooms"]] == ["0BRCT", "1DLXT", "1BRT", "1BRMT"]))
studio = rr[0]["rooms"][0]
results.append(check("member (AOA), ACRS and TEST rates dropped: 14 -> 6",
                     [rp["rate_plan_code"] for rp in studio["rate_plans"]]
                     == ["ASRAPPFX", "SSPM", "Flexi Monthly Rate", "ASRAP-15", "BASB", "ZZFLEX"]))
lead = studio["rate_plans"][0]
results.append(check("lead rate: upstream prices passed through, taxes beside them",
                     lead["per_night_rate"] == 211.5 and lead["total_stay_rate"] == 423
                     and lead["per_night_tax"] == 42.09 and lead["total_tax"] == 84.18
                     and lead["is_tax_inclusive"] is False and lead["is_app_exclusive"] is True))
results.append(check("per_night_rate + per_night_tax matches upstream nightlyRate.priceWithTaxAndFee",
                     abs((lead["per_night_rate"] + lead["per_night_tax"]) - 253.59) < 0.01))
results.append(check("no strikethrough or save_percentage anywhere",
                     all("strikethrough_rate" not in rp and "save_percentage" not in rp
                         for r in rr[0]["rooms"] for rp in r["rate_plans"])))
results.append(check("room detail: category, size, occupancy, gallery, amenity groups",
                     studio["room_category"] == "Studio" and studio["size_sqm"] == 48
                     and studio["max_occupancy"] == 3 and studio["units_remaining"] == 91
                     and len(studio["gallery"]) > 0 and all("title" not in g for g in studio["gallery"])
                     and [g["group"] for g in studio["amenity_groups"]] == ["bathroom", "bedroom", "kitchen", "livingroom", "others"]))
results.append(check("meta: stay echoed, guests summed, no voucher / price flag keys",
                     out["meta"]["noOfRooms"] == 1 and out["meta"]["noOfadults"] == 2
                     and out["meta"]["checkin_date"] == "2026-11-10" and out["meta"]["currency"] == "SGD"
                     and out["meta"]["brand_code"] == "ascott-the-residence" and out["meta"]["is_all_avail"] is True
                     and "voucher_code_valid" not in out["meta"] and "price_includes_tax" not in out["meta"]))

# Three requested rooms: apartments[i].room{i}, whether in one entry or one entry each.
s2 = copy.deepcopy(src)
room0 = s2["apartments"][0]["room0"]
s2["apartments"] = [{"room0": room0, "room1": room0[:2]}, {"room2": []}]
req2 = dict(REQ, apartmentList=[{"noOfadults": 2, "noOfchildren": 1, "childAges": [4]},
                                {"noOfadults": 1, "noOfchildren": 0},
                                {"noOfadults": 3, "noOfchildren": 2, "childAges": ["7", 9]}],
            voucherCode="SAVE10", priceIncludesTax=True)
r2 = map_rooms(s2, req2, PROPS)
results.append(validate("three requested rooms", r2))
results.append(check("one entry per requested room, room{i} matched, empty list allowed",
                     [e["room_index"] for e in r2["requested_rooms"]] == [1, 2, 3]
                     and [e["total_results"] for e in r2["requested_rooms"]] == [4, 2, 0]
                     and r2["requested_rooms"][2]["rooms"] == []))
results.append(check("per-room guests and childAges, meta sums them",
                     r2["requested_rooms"][0]["childAges"] == [4] and r2["requested_rooms"][1]["childAges"] == []
                     and r2["requested_rooms"][2]["childAges"] == [7, 9]
                     and r2["meta"]["noOfadults"] == 6 and r2["meta"]["noOfchildren"] == 3
                     and r2["meta"]["noOfRooms"] == 3))
results.append(check("voucher and price flags echoed",
                     r2["meta"]["voucher_code_valid"] is True and r2["meta"]["price_includes_tax"] is True))

# A tax-inclusive rate carries no tax on top.
s3 = copy.deepcopy(src)
rp = s3["apartments"][0]["room0"][0]["ratePlan"]
s3["apartments"][0]["room0"][0]["ratePlan"] = [dict(rp[1], isTaxInclusive=True, totalTaxPrefCurrency="0")]
r3 = map_rooms(s3, REQ, PROPS)
results.append(validate("tax-inclusive rate", r3))
inc = r3["requested_rooms"][0]["rooms"][0]["rate_plans"][0]
results.append(check("tax-inclusive: both tax amounts 0",
                     inc["is_tax_inclusive"] is True and inc["per_night_tax"] == 0 and inc["total_tax"] == 0))

# Nothing available: every rate is a member rate.
s4 = copy.deepcopy(src)
for rm in s4["apartments"][0]["room0"]:
    rm["ratePlan"] = [x for x in rm["ratePlan"] if x.get("ratePlanTemplate") == "AOA"]
r4 = map_rooms(s4, REQ, PROPS)
results.append(validate("no bookable rate anywhere", r4))
results.append(check("rooms with no bookable rate dropped, total_results 0",
                     r4["requested_rooms"][0]["rooms"] == [] and r4["requested_rooms"][0]["total_results"] == 0))

# An empty request: the stay and the currency come from upstream's own nightlyRate dates and currency.
r5 = map_rooms(src, {}, {})
results.append(validate("empty request (stay derived from nightlyRate)", r5))
results.append(check("dates from nightlyRate, currency from the property, 1 adult / 0 children / 1 room",
                     r5["meta"]["checkin_date"] == "2026-11-10" and r5["meta"]["checkout_date"] == "2026-11-12"
                     and r5["meta"]["currency"] == "SGD" and r5["meta"]["noOfadults"] == 1
                     and r5["meta"]["noOfchildren"] == 0 and r5["meta"]["noOfRooms"] == 1))

# A bare property: no rooms at all, with the stay from the request.
r6 = map_rooms({"propertyCode": "51052", "propertyName": "X", "apartments": []}, REQ, {})
results.append(validate("bare property", r6))
results.append(check("brand_code falls back, no rooms",
                     r6["meta"]["brand_code"] == "ascott" and r6["requested_rooms"][0]["rooms"] == []))

sys.exit(0 if all(results) else 1)
