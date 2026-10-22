%dw 2.0
// Booking search propertyList entry (vars.property) + POIs (vars.pois) -> get_property_details structuredContent,
// schemas/structured-content.schema.json 0.5.0.
// Source names are the PRD camelCase names quoted in the schema (propertyName, brandlogo, perNightRatePrefCurr, ...).
// Each is read at the top level of the entry first, then inside the PRD block it belongs to (pricing, location, ...).
// Optional fields with no value are left out; nulls and blank strings are dropped.
output application/json skipNullOn="everywhere"
import try from dw::Runtime

// ---------- helpers
fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if ((v is Number) or (v is Boolean)) (v as String) else null
fun number(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun positive(v) = do { var n = number(v) --- if ((n != null) and (n > 0)) n else null }
fun whole(v) = do { var n = number(v) --- if (n == null) null else floor(n) }
fun clamp(n, lo, hi) = if (n == null) null else if (n < lo) lo else if (n > hi) hi else n
fun bool(v) = if (v is Boolean) v
	else if (v is String) (["true", "y", "yes", "1"] contains lower(trim(v)))
	else if (v is Number) v != 0
	else null
fun matchesRe(s, re) = if (s is String) (s matches re) else false
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun nonEmpty(arr) = if (isEmpty(arr)) null else arr
fun limit(arr, n) = if (sizeOf(arr) <= n) arr else arr[0 to (n - 1)]
// Value at a key path, e.g. at(p, ["pricing", "currency"]).
fun at(o, path) = path reduce ((k, acc = o) -> if (acc is Object) acc[k] else null)
// First non-null value / non-blank text among several key paths.
fun pick(o, paths) = ((paths map at(o, $)) filter ($ != null))[0]
fun pickText(o, paths) = ((paths map text(at(o, $))) filter ($ != null))[0]
fun slug(v) = do {
	var s = text(v)
	var out = if (s == null) "" else ((lower(s) replace /[^a-z0-9]+/ with "-") replace /^-+|-+$/ with "")
	---
	if (out == "") null else out
}
fun timeOfDay(v) = do {
	var s = text(v)
	var padded = if (matchesRe(s, /^[0-9]:[0-5][0-9](:[0-5][0-9])?$/)) "0" ++ s else s
	---
	if (matchesRe(padded, /^([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$/)) padded else null
}
fun isoDate(v) = do {
	var s = text(v)
	var d = if ((s == null) or (sizeOf(s) < 10)) {success: false} else try(() -> s[0 to 9] as Date {format: "yyyy-MM-dd"})
	---
	if (d.success) d.result as String {format: "yyyy-MM-dd"} else null
}
fun coords(lat, lng) = do {
	var la = number(lat)
	var lo = number(lng)
	---
	if ((la == null) or (lo == null)) null
	else if ((la >= -90) and (la <= 90) and (lo >= -180) and (lo <= 180)) {latitude: la, longitude: lo}
	else null
}
fun titled(o) = if (!(o is Object)) null else do {
	var t = text(o.title)
	var d = text(o.description)
	---
	if ((t != null) and (d != null)) {title: t, description: d} else null
}

// ---------- sources
var req = vars.request
var p = vars.property

// ---------- identity
var propertyCode = pickText(p, [["propertyCode"]]) default req.propertyCode
var propertyName = pickText(p, [["propertyName"], ["name"]]) default req.propertyName default propertyCode
var brandName = pickText(p, [["brandName"]])
var gallery = objects(pick(p, [["gallery"]])) map ((g) -> do {
		var path = text(g.path) default text(g.galleryImage) default text(g.gallery_image)
		---
		if (path == null) null else {
			path: path,
			gallery_image: text(g.galleryImage) default text(g.gallery_image),
			gallery_type: text(g.galleryType) default text(g.gallery_type) default "image",
			title: text(g.title) default propertyName
		}
	}) filter ($ != null)
var banner = pickText(p, [["bannerImageMobile"], ["bannerImage"]])

// ---------- pricing
var nightly = positive(pick(p, [["perNightRatePrefCurr"], ["pricing", "perNightRatePrefCurr"]]))
var available = nightly != null
var upstreamCurrency = upper(pickText(p, [["currency"], ["currencyCode"], ["pricing", "currency"]]) default "")

// ---------- location
var city = pickText(p, [["city"], ["location", "city"]])
var country = pickText(p, [["country"], ["location", "country"]])
var address = pickText(p, [["address"], ["location", "address"]])
	default do { var parts = [city, country] filter ($ != null) --- if (isEmpty(parts)) null else (parts joinBy ", ") }

// ---------- amenities: facilities de-duplicated by label (case-insensitive) within and across groups
var groups = objects(pick(p, [["facilityGroup"], ["amenities", "facilityGroup"]])) map ((g) -> {
		entity_name: text(g.entityName) default text(g.entity_name),
		entity_title: text(g.entityTitle) default text(g.entity_title),
		facilities: objects(g.facilities) map ((f) -> {
				description: text(f.description),
				imagePath: text(f.imagePath),
				charge: text(f.charge),
				enabled: bool(f.enabled)
			}) filter (($.description != null) and ($.imagePath != null))
	}) filter ($.entity_name != null)
var dedupedGroups = ((groups reduce ((g, acc = {seen: [], out: []}) -> do {
		var fresh = (g.facilities filter !(acc.seen contains lower($.description))) distinctBy lower($.description)
		---
		{
			seen: acc.seen ++ (fresh map lower($.description)),
			out: acc.out ++ [{entity_name: g.entity_name, entity_title: g.entity_title, facilities: fresh}]
		}
	})) default {out: []}).out filter !isEmpty($.facilities)

// ---------- reviews
var reviewList = objects(pick(p, [["individualReviews"], ["reviews", "individualReviews"]])) map ((r) -> {
		reviewer_name: text(r.reviewerName) default text(r.reviewer_name),
		rating: clamp(number(r.rating), 0, 5),
		posted_date: isoDate(r.postedDate default r.posted_date),
		source: text(r.source),
		text: text(r.text) default text(r.reviewText)
	}) filter (($.reviewer_name != null) and ($.rating != null) and ($.text != null))

// ---------- hotel information
var staff = pick(p, [["staffLanguages"], ["hotelInformation", "staffLanguages"], ["hotel_information", "staffLanguages"]])
var staffLanguages = (if (staff is Object) (if (staff.languages is Array) staff.languages else []) else if (staff is Array) staff else [])
	map text($) filter ($ != null)

// ---------- nearby: POIs of this property from the getpropertypois response
var poiBody = vars.pois
var poiGroups = if ((poiBody is Object) and (poiBody.properties is Array)) objects(poiBody.properties) else []
var groupedPois = (poiGroups filter (text($.propertyCode) == propertyCode)) flatMap objects($.pois)
var flatPois = (if ((poiBody is Object) and (poiBody.pois is Array)) objects(poiBody.pois) else if (poiBody is Array) objects(poiBody) else [])
	filter ((text($.propertyCode) == null) or (text($.propertyCode) == propertyCode))
var walk = p('poi.walkingMetresPerMinute') as Number
var nearby = (if (!isEmpty(groupedPois)) groupedPois else flatPois) map ((poi) -> {
		poi_id: text(poi.poiId),
		title: text(poi.poiName),
		category: text(poi.poiCategory),
		"type": text(poi.poiType),
		icon_code: text(poi.iconCode),
		coordinates: coords(poi.latitude, poi.longitude),
		address: text(poi.poiAddress),
		distance_minutes: whole(poi.distanceMinutes) default do {
			var m = number(poi.distanceMetres)
			---
			if ((m == null) or (m < 0)) null else ceil(m / walk)
		}
	}) filter (($.poi_id != null) and ($.title != null) and ($.category != null) and ($."type" != null) and ($.icon_code != null) and ($.coordinates != null))

var accessibility = pick(p, [["accessibilityNote"]])
---
{
	property_code: propertyCode,
	property_name: propertyName,
	brand_code: slug(pickText(p, [["brand"], ["brandCode"]])) default slug(brandName) default "ascott",
	brand_name: brandName default "Ascott",
	brand_logo_url: pickText(p, [["brandlogo"], ["brandLogo"]]) default "",
	banner_image_url: banner,
	thumbnail_url: pickText(p, [["newPropertyThumbnail"], ["propertyThumbnail"]]) default banner default gallery[0].path,
	property_type: pickText(p, [["propertyType"]]) default "",
	asr_participating: bool(pick(p, [["asrParticipating"]])) default false,
	email: pickText(p, [["email"]]),
	phone: pickText(p, [["phone"]]),
	tags: objects(pick(p, [["tag"], ["tags"]])) map ((t) -> {
			propertyTagTitle: text(t.propertyTagTitle),
			propertyTagPresent: bool(t.propertyTagPresent) default false
		}) filter ($.propertyTagTitle != null),
	description_title: pickText(p, [["descriptionTitle"]]),
	description: pickText(p, [["description"]]),
	gallery: nonEmpty(gallery),
	pricing: {
		availability_status: if (available) "available" else "on_request",
		per_night_rate_pref_curr: nightly,
		total_stay_rate_pref_curr: if (available) positive(pick(p, [["totalStayRatePrefCurr"], ["pricing", "totalStayRatePrefCurr"]])) else null,
		strikethrough_rate: if (available) positive(pick(p, [["strikethroughRate"], ["pricing", "strikethroughRate"]])) else null,
		currency: if (upstreamCurrency matches /^[A-Z]{3}$/) upstreamCurrency else (req.currency default p('property.currency')),
		next_available_date: if (available) null else isoDate(pick(p, [["nextAvailableDate"], ["pricing", "nextAvailableDate"]])),
		based_on: {
			checkin: req.checkin,
			checkout: req.checkout,
			adults: req.adults,
			children: req.children
		}
	},
	location: {
		city: city,
		country: country,
		country_code: do { var c = upper(pickText(p, [["countryCode"], ["location", "countryCode"]]) default "") --- if (c matches /^[A-Z]{2}$/) c else null },
		address: address,
		local_address: pickText(p, [["localAddress"], ["location", "localAddress"]]),
		coordinates: coords(
			pick(p, [["latitude"], ["location", "latitude"], ["coordinates", "latitude"]]),
			pick(p, [["longitude"], ["location", "longitude"], ["coordinates", "longitude"]])),
		map_image_url: pickText(p, [["mapImage"], ["location", "mapImage"]]),
		getting_to_property: titled(pick(p, [["gettingToProperty"], ["location", "gettingToProperty"]])),
		public_transport: titled(pick(p, [["publicTransport"], ["location", "publicTransport"]]))
	},
	amenities: {
		facility_groups: dedupedGroups
	},
	reviews: {
		average_ratings: clamp(number(pick(p, [["averageRatings"], ["reviews", "averageRatings"]])), 0, 5) default 0,
		total_number_of_reviews: clamp(whole(pick(p, [["totalNumberOfReviews"], ["reviews", "totalNumberOfReviews"]])), 0, 2147483647) default 0,
		score_label: pickText(p, [["scoreLabel"], ["reviews", "scoreLabel"]]),
		individual_reviews: nonEmpty(reviewList)
	},
	hotel_information: {
		check_in_time: timeOfDay(pick(p, [["checkInTime"], ["hotelInformation", "checkInTime"], ["hotel_information", "checkInTime"]])),
		check_out_time: timeOfDay(pick(p, [["checkOutTime"], ["hotelInformation", "checkOutTime"], ["hotel_information", "checkOutTime"]])),
		staff_languages: if (isEmpty(staffLanguages)) null else {
			title: if (staff is Object) text(staff.title) else null,
			languages: staffLanguages
		},
		cancellation_policy: pickText(p, [["cancellationPolicy"], ["hotelInformation", "cancellationPolicy"], ["hotel_information", "cancellationPolicy"]]),
		best_rate_guaranteed: pickText(p, [["bestRateGuaranteed"], ["hotelInformation", "bestRateGuaranteed"], ["hotel_information", "bestRateGuaranteed"]])
	},
	nearby: if (poiBody == null) null else limit(nearby, req.maxPois),
	asset_base_url: p('asset.baseUrl'),
	accessibility_note: if ((accessibility is Object) and (text(accessibility.title) != null) and (text(accessibility.body) != null))
		{title: text(accessibility.title), body: text(accessibility.body)} else null,
	awards: nonEmpty(objects(pick(p, [["awards"]])) map ((a) -> {image: text(a.image), label: text(a.label)}) filter ($.image != null))
}
