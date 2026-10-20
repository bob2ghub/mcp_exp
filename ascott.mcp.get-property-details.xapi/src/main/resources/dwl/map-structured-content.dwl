%dw 2.0
// Property details (vars.property) + POIs (vars.pois) -> get_property_details structuredContent,
// schemas/structured-content.schema.json 0.5.0. Optional fields are left out when the source has no value
// (null and blank strings are dropped); required fields fall back to the request or a neutral default.
output application/json skipNullOn="everywhere"
import try from dw::Runtime
import take from dw::core::Arrays

// ---------- helpers
fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if ((v is Number) or (v is Boolean)) (v as String) else null
fun number(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun positive(v) = do { var n = number(v) --- if (n == null) null else if (n > 0) n else null }
fun whole(v) = do { var n = number(v) --- if (n == null) null else floor(n) }
fun clamp(n, lo, hi) = if (n == null) null else if (n < lo) lo else if (n > hi) hi else n
fun bool(v) = if (v is Boolean) v
	else if (v is String) (["true", "y", "yes", "1"] contains lower(trim(v)))
	else if (v is Number) v != 0
	else null
fun matchesRe(s, re) = if (s is String) (s matches re) else false
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun nonEmpty(arr) = if (isEmpty(arr)) null else arr
// First non-null value / text among the given keys (upstream camelCase first, then snake_case).
fun firstVal(o, keys) = if (o is Object) ((keys map ((k) -> o[k])) filter ($ != null))[0] else null
fun firstText(o, keys) = if (o is Object) ((keys map ((k) -> text(o[k]))) filter ($ != null))[0] else null
fun obj(v) = if (v is Object) v else {}
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
	var d = if (s == null) {success: false} else try(() -> s[0 to 9] as Date {format: "yyyy-MM-dd"})
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
fun titled(o) = do {
	var t = firstText(o, ["title"])
	var d = firstText(o, ["description"])
	---
	if ((t != null) and (d != null)) {title: t, description: d} else null
}

// ---------- sources
var req = vars.request
var src = obj(vars.property)
var loc = obj(firstVal(src, ["location"]))
var pricingSrc = obj(firstVal(src, ["pricing"]))
var basedOnSrc = obj(firstVal(pricingSrc, ["basedOn", "based_on"]))
var amenitiesSrc = obj(firstVal(src, ["amenities"]))
var reviewsSrc = obj(firstVal(src, ["reviews"]))
var hotelSrc = obj(firstVal(src, ["hotel_information", "hotelInformation"]))
fun hotelVal(keys) = firstVal(hotelSrc, keys) default firstVal(src, keys)
fun locText(keys) = firstText(loc, keys) default firstText(src, keys)

// ---------- identity and media
var propertyCode = firstText(src, ["propertyCode", "property_code"]) default vars.propertyCode default req.propertyCode
var propertyName = firstText(src, ["propertyName", "property_name", "name"]) default req.propertyName default propertyCode
var brandName = firstText(src, ["brandName", "brand_name"])
var brandCode = slug(firstText(src, ["brand", "brandCode", "brand_code"])) default slug(brandName) default "ascott"

var gallery = objects(firstVal(src, ["gallery"])) map ((g) -> {
	path: firstText(g, ["path", "galleryImage", "gallery_image"]),
	gallery_image: firstText(g, ["galleryImage", "gallery_image"]),
	gallery_type: firstText(g, ["galleryType", "gallery_type"]) default "image",
	title: firstText(g, ["title"]) default propertyName
}) filter ($.path != null)
var bannerImage = firstText(src, ["bannerImageMobile", "bannerImage", "banner_image_url"])
var thumbnail = firstText(src, ["newPropertyThumbnail", "propertyThumbnail", "thumbnail_url"]) default bannerImage default gallery[0].path

var tags = objects(firstVal(src, ["tag", "tags"])) map ((t) -> {
	propertyTagTitle: firstText(t, ["propertyTagTitle", "title"]),
	propertyTagPresent: bool(firstVal(t, ["propertyTagPresent", "present"])) default false
}) filter ($.propertyTagTitle != null)

// ---------- pricing
var rate = positive(firstVal(pricingSrc, ["perNightRatePrefCurr", "per_night_rate_pref_curr"]) default firstVal(src, ["perNightRatePrefCurr"]))
var upstreamStatus = lower(firstText(pricingSrc, ["availabilityStatus", "availability_status"]) default "")
var onRequest = (rate == null) or (["on_request", "onrequest", "on request"] contains upstreamStatus)
var currencyIn = upper(firstText(pricingSrc, ["currency", "currencyCode"]) default firstText(src, ["currency", "currencyCode"]) default "")
var currency = if (matchesRe(currencyIn, /^[A-Z]{3}$/)) currencyIn else (req.currency default p('default.currency'))
var adultsQuoted = whole(firstVal(basedOnSrc, ["adults"]))
var childrenQuoted = whole(firstVal(basedOnSrc, ["children"]))
var pricing = {
	availability_status: if (onRequest) "on_request" else "available",
	per_night_rate_pref_curr: if (onRequest) null else rate,
	total_stay_rate_pref_curr: if (onRequest) null else positive(firstVal(pricingSrc, ["totalStayRatePrefCurr", "total_stay_rate_pref_curr"])),
	strikethrough_rate: if (onRequest) null else positive(firstVal(pricingSrc, ["strikethroughRate", "strikethrough_rate"])),
	currency: currency,
	next_available_date: if (onRequest) isoDate(firstVal(pricingSrc, ["nextAvailableDate", "next_available_date"])) else null,
	based_on: {
		checkin: isoDate(firstVal(basedOnSrc, ["checkin", "checkIn"])) default req.checkin,
		checkout: isoDate(firstVal(basedOnSrc, ["checkout", "checkOut"])) default req.checkout,
		adults: if ((adultsQuoted != null) and (adultsQuoted >= 1)) adultsQuoted else req.adults,
		children: if ((childrenQuoted != null) and (childrenQuoted >= 0)) childrenQuoted else req.children
	}
}

// ---------- location
var countryCodeIn = upper(locText(["countryCode", "country_code"]) default "")
var location = {
	city: locText(["city", "cityName"]),
	country: locText(["country", "countryName"]),
	country_code: if (matchesRe(countryCodeIn, /^[A-Z]{2}$/)) countryCodeIn else null,
	address: locText(["address"]) default locText(["localAddress", "local_address"]),
	local_address: locText(["localAddress", "local_address"]),
	coordinates: coords(
		firstVal(loc, ["latitude", "lat"]) default obj(loc.coordinates).latitude default firstVal(src, ["latitude"]),
		firstVal(loc, ["longitude", "lng", "lon"]) default obj(loc.coordinates).longitude default firstVal(src, ["longitude"])),
	map_image_url: locText(["mapImage", "map_image_url"]),
	getting_to_property: titled(firstVal(loc, ["gettingToProperty", "getting_to_property"]) default firstVal(src, ["gettingToProperty"])),
	public_transport: titled(firstVal(loc, ["publicTransport", "public_transport"]) default firstVal(src, ["publicTransport"]))
}

// ---------- amenities: facilities de-duplicated by label, within and across groups
var facilityGroupsIn = objects(firstVal(amenitiesSrc, ["facilityGroup", "facility_groups"]) default firstVal(src, ["facilityGroup"])) map ((g) -> {
	entity_name: firstText(g, ["entityName", "entity_name"]) default "facilities-amenities",
	entity_title: firstText(g, ["entityTitle", "entity_title"]),
	facilities: (objects(firstVal(g, ["facilities"])) map ((f) -> {
		description: firstText(f, ["description", "name"]),
		imagePath: firstText(f, ["imagePath", "image_path", "icon"]),
		charge: firstText(f, ["charge"]),
		enabled: bool(firstVal(f, ["enabled"]))
	}) filter (($.description != null) and ($.imagePath != null))) distinctBy lower($.description)
})
var facilityGroups = (facilityGroupsIn reduce ((g, acc = {seen: [], out: []}) -> do {
	var fresh = g.facilities filter ((f) -> !(acc.seen contains lower(f.description)))
	---
	{
		seen: acc.seen ++ (fresh map lower($.description)),
		out: if (isEmpty(fresh)) acc.out else acc.out + {entity_name: g.entity_name, entity_title: g.entity_title, facilities: fresh}
	}
})).out

// ---------- reviews
var individualReviews = objects(firstVal(reviewsSrc, ["individualReviews", "individual_reviews", "reviews"])) map ((r) -> {
	reviewer_name: firstText(r, ["reviewerName", "reviewer_name", "name", "author"]),
	rating: clamp(number(firstVal(r, ["rating", "score"])), 0, 5),
	posted_date: isoDate(firstVal(r, ["postedDate", "posted_date", "date"])),
	source: firstText(r, ["source"]),
	text: firstText(r, ["text", "reviewText", "comment"])
}) filter (($.reviewer_name != null) and ($.rating != null) and ($.text != null))
var totalReviews = whole(firstVal(reviewsSrc, ["totalNumberOfReviews", "total_number_of_reviews"]) default firstVal(src, ["totalNumberOfReviews"]))
var reviews = {
	average_ratings: clamp(number(firstVal(reviewsSrc, ["averageRatings", "average_ratings"]) default firstVal(src, ["averageRatings"])), 0, 5) default 0,
	total_number_of_reviews: if ((totalReviews != null) and (totalReviews >= 0)) totalReviews else 0,
	score_label: firstText(reviewsSrc, ["scoreLabel", "score_label"]),
	individual_reviews: nonEmpty(individualReviews)
}

// ---------- hotel information
var staffLanguagesIn = hotelVal(["staffLanguages", "staff_languages"])
var staffLanguageList = (if (staffLanguagesIn is Array) staffLanguagesIn else (if (staffLanguagesIn is Object) (staffLanguagesIn.languages default []) else []))
	map ((l) -> if (l is Object) (firstText(l, ["language", "name", "title"])) else text(l))
	filter ($ != null)
var hotelInformation = {
	check_in_time: timeOfDay(hotelVal(["checkInTime", "check_in_time"])),
	check_out_time: timeOfDay(hotelVal(["checkOutTime", "check_out_time"])),
	staff_languages: if (isEmpty(staffLanguageList)) null else {
		title: if (staffLanguagesIn is Object) firstText(staffLanguagesIn, ["title"]) else null,
		languages: staffLanguageList distinctBy $
	},
	cancellation_policy: text(hotelVal(["cancellationPolicy", "cancellation_policy"])),
	best_rate_guaranteed: text(hotelVal(["bestRateGuaranteed", "best_rate_guaranteed"]))
}

// ---------- nearby: POIs for this property, from the getpropertypois response
fun poiGroupsOf(v): Array = if (v is Array) flatten(v map poiGroupsOf($))
	else if (v is Object) (if (v.pois is Array) [v] else flatten(valuesOf(v) map poiGroupsOf($)))
	else []
fun poisOf(v): Array = if (v is Array) flatten(v map poisOf($))
	else if (v is Object) (if (v.poiId != null) [v] else flatten(valuesOf(v) map poisOf($)))
	else []
var poiGroups = poiGroupsOf(vars.pois)
var poiGroup = (poiGroups filter ((g) -> firstText(g, ["propertyCode", "property_code"]) == propertyCode))[0]
	default (if (sizeOf(poiGroups) == 1) poiGroups[0] else null)
var rawPois = if (poiGroup != null) objects(poiGroup.pois)
	else (poisOf(vars.pois) filter ((poi) -> do {
		var owner = firstText(poi, ["propertyCode", "property_code"])
		---
		if (owner != null) owner == propertyCode else ((firstText(poi, ["poiId"]) default "") startsWith "poi-$(propertyCode)-")
	}))
var walkingMetresPerMinute = p('poi.walkingMetresPerMinute') as Number
var nearby = take(rawPois map ((poi) -> do {
	var minutes = number(firstVal(poi, ["distanceMinutes", "distance_minutes", "walkingMinutes"]))
	var metres = number(firstVal(poi, ["distanceMetres", "distanceMeters"]))
	---
	{
		poi_id: firstText(poi, ["poiId", "poi_id"]),
		title: firstText(poi, ["poiName", "title", "name"]),
		category: firstText(poi, ["poiCategory", "category"]),
		"type": firstText(poi, ["poiType", "type"]),
		icon_code: firstText(poi, ["iconCode", "icon_code"]),
		coordinates: coords(firstVal(poi, ["latitude"]) default obj(poi.coordinates).latitude, firstVal(poi, ["longitude"]) default obj(poi.coordinates).longitude),
		address: firstText(poi, ["poiAddress", "address"]),
		distance_minutes: if ((minutes != null) and (minutes >= 0)) round(minutes)
			else if ((metres != null) and (metres >= 0)) ceil(metres / walkingMetresPerMinute)
			else null
	}
}) filter ((n) -> (n.poi_id != null) and (n.title != null) and (n.category != null) and (n."type" != null) and (n.icon_code != null) and (n.coordinates != null)),
	min([req.maxPois default 5, 5]))

// ---------- UI-only optional blocks
var accessibilityIn = obj(firstVal(src, ["accessibilityNote", "accessibility_note"]))
var awards = objects(firstVal(src, ["awards"])) map ((a) -> {
	image: firstText(a, ["image", "imagePath", "path"]),
	label: firstText(a, ["label", "title", "name"])
}) filter ($.image != null)
---
{
	property_code: propertyCode,
	property_name: propertyName,
	brand_code: brandCode,
	brand_name: brandName default "Ascott",
	brand_logo_url: firstText(src, ["brandlogo", "brandLogo", "brand_logo_url"]) default "",
	banner_image_url: bannerImage,
	thumbnail_url: thumbnail,
	property_type: firstText(src, ["propertyType", "property_type"]) default "",
	asr_participating: bool(firstVal(src, ["asrParticipating", "asr_participating"])) default false,
	email: firstText(src, ["email"]),
	phone: firstText(src, ["phone", "phoneNumber"]),
	tags: nonEmpty(tags),
	description_title: firstText(src, ["descriptionTitle", "description_title"]),
	description: firstText(src, ["description"]),
	gallery: nonEmpty(gallery),
	pricing: pricing,
	location: location,
	amenities: {facility_groups: facilityGroups},
	reviews: reviews,
	hotel_information: hotelInformation,
	nearby: nonEmpty(nearby),
	asset_base_url: p('asset.baseUrl'),
	accessibility_note: do {
		var t = firstText(accessibilityIn, ["title"])
		var b = firstText(accessibilityIn, ["body", "description"])
		---
		if ((t != null) and (b != null)) {title: t, body: b} else null
	},
	awards: nonEmpty(awards)
}
