%dw 2.0
// Booking search properties (vars.lookups, one entry per requested code, in request order) + the request
// (vars.compareRequest) -> compare_properties structuredContent,
// schemas/T06-compare-properties.structured-content.schema.json 0.1.0 (the owner's file, 2026-10-27).
//
// T-06 only puts the requested properties side by side in one payload. It does not compare, rank, filter or
// recommend: the model writes its recommendation in the reply, from this data.
//
// 0.1.0 shape: {meta, properties[], excluded[]}. properties holds 2 to 4 cards, in request order, without the
// codes that were not found; fewer than two found is an error, raised by compare-check-lookups before this runs.
// Optional fields upstream has no value for are LEFT OUT (skipNullOn="everywhere"), not sent as null.
output application/json skipNullOn="everywhere"
import try from dw::Runtime
import take from dw::core::Arrays

var req = vars.compareRequest default {}
var lookups = vars.lookups default []
// The schema allows at most 6 highlight chips.
var maxAmenities = do { var m = p('t06.maxAmenityHighlights') default 6 --- if ((m as Number) < 6) (m as Number) else 6 }

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if ((v is Number) or (v is Boolean)) (v as String) else null
fun num(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun int(v) = do { var n = num(v) --- if (n == null) null else floor(n) }
fun bool(v) = if (v is Boolean) v else if (v is String) (["true", "y", "yes", "1"] contains lower(trim(v))) else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun obj(v) = if (v is Object) v else {}
fun money(n) = if (n == null) null else round(n * 100) / 100
fun atLeast(n, min) = if ((n != null) and (n >= min)) n else null
fun firstText(o, keys) = if (o is Object) ((keys map ((k) -> text(o[k]))) filter ($ != null))[0] else null
fun nonEmpty(arr) = if (isEmpty(arr)) null else arr
fun digits(v) = do { var s = text(v) --- if ((s != null) and (s matches /^[0-9]+$/)) s else null }
fun slug(v) = do {
	var s = (lower(text(v) default "") replace /[^a-z0-9]+/ with "-") replace /^-+|-+$/ with ""
	---
	if (s == "") null else s
}

// ---------- rates: the same filter as T-04 (room-rate-details.dwl)
// Only rates an anonymous user arriving from ChatGPT can book: no member rates (template AOA, template name
// "… Member …"), no comparison rates ("ACRS Compare") and no test rates (a TEST token in the name).
fun bookable(rp) = do {
	var template = upper(text(rp.ratePlanTemplate) default "")
	var templateName = lower(text(rp.ratePlanTemplateName) default "")
	var name = lower(text(rp.ratePlanName) default "")
	---
	(text(rp.ratePlanCode) != null) and (text(rp.ratePlanName) != null)
		and !((template == "AOA")
			or (templateName contains "member")
			or (name contains "acrs compare")
			or (name matches /(?s).*(^|[^a-z])test([^a-z].*|$)/))
}

// ---------- amenity highlights
// Upstream facilities.facilityGroup[].facilities[]: the label is description, else name / enName (some rows have a
// null description), and the icon path is the widget's icon key. De-duplicated by label, the facilities-amenities
// group first, then ranked by the keywords below so the chips are the highlights the card is meant to show
// (pool, gym, spa, business centre, …) rather than whatever upstream lists first.
var highlightKeywords = ["pool", "gym", "fitness", "spa", "business", "wifi", "internet", "breakfast",
	"restaurant", "lounge", "parking", "laundry", "airport", "shuttle", "reception", "kitchen", "pet"]
fun highlightRank(label) = do {
	var l = lower(label)
	var hit = (highlightKeywords map ((k, i) -> if (l contains k) i else null) filter ($ != null))[0]
	---
	hit default sizeOf(highlightKeywords)
}
fun amenityHighlights(src) = do {
	var groups = objects(obj(src.facilities).facilityGroup)
	var preferred = groups filter ((g) -> lower(text(g.entityName) default "") == "facilities-amenities")
	var rest = groups filter ((g) -> lower(text(g.entityName) default "") != "facilities-amenities")
	var rows = (flatten((preferred ++ rest) map ((g) -> objects(g.facilities)))
		filter ((f) -> bool(f.enable) default true)
		map ((f) -> {imagePath: text(f.imagePath), description: firstText(f, ["description", "name", "enName"])}))
		filter (($.imagePath != null) and ($.description != null))
	---
	nonEmpty(take(rows distinctBy lower($.description) orderBy highlightRank($.description), maxAmenities))
}

// ---------- nearby: the same points of interest as T-02 nearby, when the lookup carries them.
// T-06 does not call the POI system today (get-property-pois is T-02 only), so this is normally absent.
fun nearby(lookup) = nonEmpty((objects(lookup.pois default obj(lookup.property).pois)
	map ((poi) -> {
		title: firstText(poi, ["title", "name", "poiName"]),
		icon_code: firstText(poi, ["icon_code", "iconCode", "icon", "emoji"]),
		distance_minutes: atLeast(int(poi.distance_minutes default poi.distanceMinutes default poi.walkMinutes), 0)
	}))
	filter (($.title != null) and ($.icon_code != null)))

// ---------- one requested property -> its card
fun card(lookup) = do {
	var src = obj(lookup.property)
	var rooms = flatten(objects(src.apartments) map ((e) -> flatten((e pluck $) map ((v) -> objects(v)))))
	// This property's own cheapest bookable rate: the card's "from 175 SGD / Night" and its points banner.
	var rates = (flatten(rooms map ((a) -> objects(a.ratePlan) filter bookable($)))
		map ((rp) -> {
			perNight: num(rp.perNightRatePrefCurr) default num(rp.perNightRate),
			points: atLeast(int(rp.earnASRpoints), 0)
		})
		filter ($.perNight != null)) orderBy $.perNight
	var lead = rates[0]
	// A listing-style entry has no apartments at all; upstream still gives it a property-level lead-in rate.
	var perNight = (lead.perNight default (if (isEmpty(rooms)) (num(src.perNightRatePrefCurr) default num(src.perNightRate)) else null))
	var city = firstText(src, ["cityName", "city"])
	var country = firstText(src, ["countryName", "country"])
	---
	{
		property_code: digits(src.propertyCode) default digits(lookup.code),
		property_name: firstText(src, ["propertyEnName", "propertyName"]),
		brand_code: slug(src.brand) default slug(src.brandName) default "ascott",
		banner_image_url: firstText(src, ["bannerImageMobile", "newPropertyThumbnail"])
			default ((objects(src.gallery) map firstText($, ["galleryImage", "path", "image"])) filter ($ != null))[0],
		location_label: if (city == null) country
			else if ((country == null) or (lower(country) == lower(city))) city
			else city ++ ", " ++ country,
		// average_ratings / total_number_of_reviews: booking search has no reviews (PRD source v1/propertyreviews
		// is not integrated), and the schema wants both or neither, so the row is left out.
		amenity_highlights: amenityHighlights(src),
		nearby: nearby(lookup),
		availability_status: if (perNight != null) "available" else "on_request",
		per_night_rate: money(perNight),
		// next_available_date: upstream does not say when the next rate is, so it is left out (ER-08).
		is_asr_participating: bool(src.asrParticipating) default bool(src.isASR) default false,
		earn_asr_points: if (perNight == null) null else lead.points
	}
}

// Cards keep the request order. A card without the schema's required identifiers cannot be rendered, so it is
// treated as not found rather than sent half-built (no Ascott property code is anything but digits).
var cards = ((lookups filter ($.status == "ok")) map ((l) -> card(l)))
	filter (($.property_code != null) and ($.property_name != null))
var cardCodes = cards map $.property_code

// Every price in the response is in one currency (AC-07): the request's, else the first found property's.
var okProperties = (lookups filter ($.status == "ok")) map ((l) -> obj(l.property))
var currency = upper(text(req.currency) default ((okProperties map text($.currency)) filter ($ != null))[0]
	default (p('property.currency') default "SGD"))
var labels = (cards map $.location_label) filter ($ != null)
var childAges = ((if (req.childAges is Array) req.childAges else []) map int($)) filter ($ != null)
---
{
	meta: {
		total_results: sizeOf(cards),
		// Only when every card is in the same place, as the PRD's "Comparing 3 properties in Central Singapore".
		location_query: if ((sizeOf(labels) == sizeOf(cards)) and (sizeOf(labels distinctBy lower($)) == 1)) labels[0] else null,
		currency: currency,
		checkin_date: text(req.checkin) default text(req.checkinDate),
		checkout_date: text(req.checkout) default text(req.checkoutDate),
		noOfadults: atLeast(int(req.adults) default int(req.noOfadults), 1) default 1,
		noOfchildren: atLeast(int(req.children) default int(req.noOfchildren), 0) default 0,
		childAges: if (req.childAges is Array) childAges else null,
		asset_base_url: p('asset.baseUrl') default "https://www.discoverasr.com"
	},
	properties: cards,
	// Requested codes that matched no property. The schema's only reason is "not_found": a code whose lookup
	// failed (status unavailable) has no slot here, so it is reported in the xapi.downstream.error log instead.
	excluded: nonEmpty(((lookups filter ($.status == "not_found")) map ((l) -> {property_code: text(l.code), reason: "not_found"}))
		filter ($.property_code != null))
}
