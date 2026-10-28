%dw 2.0
// Booking search property (vars.property = one propertyList[] entry) + POIs (vars.pois) + the validated request
// (vars.request) -> get_property_details structuredContent, schemas/T02-get-property-details.structured-content.schema.json 0.6.0.
// Every required field is always emitted; an optional field upstream has no value for is left out (skipNullOn), and the
// sections the schema requires but upstream cannot fill (reviews, hotel_information, amenities, nearby) stay as empty
// shells rather than disappearing. Checked against the real 51052 response by tests/check_t02.py.
output application/json skipNullOn="everywhere"
import try from dw::Runtime
import take from dw::core::Arrays
import days from dw::core::Periods

// ---------- helpers
fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if ((v is Number) or (v is Boolean)) (v as String) else null
fun num(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun int(v) = do { var n = num(v) --- if (n == null) null else floor(n) }
fun positive(v) = do { var n = num(v) --- if ((n != null) and (n > 0)) n else null }
fun bool(v) = if (v is Boolean) v else if (v is String) (["true", "y", "yes", "1"] contains lower(trim(v))) else if (v is Number) (v != 0) else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun obj(v) = if (v is Object) v else {}
fun nonEmpty(arr) = if (isEmpty(arr)) null else arr
fun first(o, keys) = if (o is Object) ((keys map ((k) -> text(o[k]))) filter ($ != null))[0] else null
// brand_code pattern: ^[a-z0-9]+(-[a-z0-9]+)*$
fun slug(v) = do {
	var s = (lower(text(v) default "") replace /[^a-z0-9]+/ with "-") replace /^-+|-+$/ with ""
	---
	if (s == "") null else s
}
// CMS HTML -> plain text, for the one field the schema calls plain text.
fun plain(v) = do {
	var s = text(v)
	var out = if (s == null) null else trim(((s replace /<[^>]*>/ with " ") replace /&nbsp;|&#160;/ with " ") replace /\s+/ with " ")
	---
	if ((out == null) or (out == "")) null else out
}
// Upstream check-in / check-out are 12-hour ("03:00 PM"); the schema wants 24-hour ^([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$
fun time24(v) = do {
	var s = upper(text(v) default "")
	var parts = (s replace /\s+/ with "") match /^([0-9]{1,2}):([0-5][0-9])(:([0-5][0-9]))?(AM|PM)?$/
	---
	if (isEmpty(parts)) null
	else do {
		var h = parts[1] as Number
		var mer = parts[5] default ""
		var h24 = if (mer == "AM") (if (h == 12) 0 else h) else if (mer == "PM") (if (h == 12) 12 else h + 12) else h
		---
		if ((h24 < 0) or (h24 > 23)) null
		else (if (h24 < 10) "0" ++ (h24 as String) else h24 as String) ++ ":" ++ parts[2]
	}
}
fun isoDate(v) = do {
	var s = text(v)
	var d = if (s == null) {success: false} else try(() -> s[0 to 9] as Date {format: "yyyy-MM-dd"})
	---
	if (d.success) d.result as String {format: "yyyy-MM-dd"} else null
}
// Upstream nightlyRate dates are "MM/dd/yyyy": the fallback stay when the request has none.
fun usDate(v) = do {
	var s = text(v)
	var d = if (s == null) {success: false} else try(() -> s as Date {format: "MM/dd/yyyy"})
	---
	if (d.success) d.result else null
}

// ---------- sources
// The property: vars.property (set by get-property-common-info), else the payload itself, either the booking search
// response ({propertyList: [...]}) or one propertyList[] entry, so the script also works in a plain Transform Message.
var src = obj(vars.property default (if (payload.propertyList is Array) payload.propertyList[0] else payload))
var req = obj(vars.request)
var loc = obj(src.location)
var ratePlans = objects(flatten(flatten(objects(src.apartments) map objects($.room0)) map objects($.ratePlan)))

// ---------- identity
var propertyCode = first(src, ["propertyCode"]) default text(vars.propertyCode) default text(req.propertyCode)
var propertyName = first(src, ["propertyEnName", "propertyName"]) default text(req.propertyName) default propertyCode
var gallerySrc = objects(src.gallery)
var bannerImage = first(src, ["bannerImageMobile"])
// thumbnail_url is required: property thumbnail, else banner, gallery, the top room's images, then the location map.
var firstRoom = flatten(objects(src.apartments) map objects($.room0))[0]
var thumbnail = first(src, ["newPropertyThumbnail"]) default bannerImage default first(gallerySrc[0], ["path", "galleryImage"])
	default first(firstRoom, ["thumbnailImage", "bannerImageMobile"]) default first(obj(src.location), ["mapImage"])

// ---------- pricing
var perNight = positive(src.perNightRatePrefCurr) default positive(src.perNightRate)
var totalStay = positive(src.totalStayRatePrefCurr) default positive(src.totalStayRate)
// Upstream gives no property-level strikethrough: take it from the rate plan the lead-in rate comes from.
var strike = positive(src.strikethroughRatePrefCurr) default positive(src.strikethroughRate)
	default ((ratePlans filter ((rp) -> (positive(rp.perNightRatePrefCurr) default positive(rp.perNightRate)) == perNight)
		map (positive($.strikethroughRatePrefCurr) default positive($.strikethroughRate))) filter ($ != null))[0]
// The *PrefCurr prices are in the currency the request asked booking search for (currencyCode); upstream `currency` is the
// property's own. So the requested currency labels the prices, else the property's, else default.currency.
var requestedCurrency = upper(text(req.currency) default "")
var propertyCurrency = upper(first(src, ["currency", "currencyCode"]) default "")
var currency = if (requestedCurrency matches /^[A-Z]{3}$/) requestedCurrency
	else if (propertyCurrency matches /^[A-Z]{3}$/) propertyCurrency
	else upper(p('default.currency') default "SGD")
// The stay: the validated request, else the nightly rates upstream quoted.
var nightlyDates = ((flatten(ratePlans map objects($.nightlyRate)) map usDate($.date)) filter ($ != null)) orderBy $
var checkin = isoDate(req.checkin) default (if (isEmpty(nightlyDates)) null else nightlyDates[0] as String {format: "yyyy-MM-dd"})
var checkout = isoDate(req.checkout) default (if (isEmpty(nightlyDates)) null else (nightlyDates[-1] + days(1)) as String {format: "yyyy-MM-dd"})
var adults = do { var a = int(req.adults) --- if ((a != null) and (a >= 1)) a else 1 }
var children = do { var c = int(req.children) --- if ((c != null) and (c >= 0)) c else 0 }
var childAges = ((if (req.childAges is Array) req.childAges else []) map int($)) filter (($ != null) and ($ >= 0))

// ---------- amenities: facilities de-duplicated by label, within and across groups (schema: "De-duplicated by the server")
var groupsIn = objects(obj(src.facilities).facilityGroup default src.facilityGroup default obj(src.amenities).facilityGroup) map ((g) -> {
	entity_name: first(g, ["entityName", "entity_name"]),
	entity_title: first(g, ["entityTitle", "entity_title"]),
	facilities: (objects(g.facilities) map ((f) -> {
		description: first(f, ["description", "name", "enName"]),
		imagePath: first(f, ["imagePath", "image_path", "facilityIcon", "icon"]),
		charge: first(f, ["charge"]),
		enabled: bool(f.enable) default bool(f.enabled)
	}) filter (($.description != null) and ($.imagePath != null))) distinctBy lower($.description)
}) filter ($.entity_name != null)
var facilityGroups = (groupsIn reduce ((g, acc = {seen: [], out: []}) -> do {
	var fresh = g.facilities filter ((f) -> !(acc.seen contains lower(f.description)))
	---
	{
		seen: acc.seen ++ (fresh map lower($.description)),
		out: if (isEmpty(fresh)) acc.out else acc.out + {entity_name: g.entity_name, entity_title: g.entity_title, facilities: fresh}
	}
})).out

// ---------- hotel information
var staffSrc = obj(src.staffLanguages)
var languages = ((if (staffSrc.languages is Array) staffSrc.languages else []) map text($)) filter ($ != null) distinctBy $

// ---------- the "Accessibility" amenity highlight, when upstream flags one
var highlightItems = flatten(objects(src.tag) map (objects(obj($.susstainable).allItems) ++ objects(obj($.susstainable).sustainableItems)))
var accessibility = (highlightItems filter ((i) -> lower(first(i, ["identityName", "label"]) default "") == "accessibility"))[0]

// ---------- nearby: POIs for this property, from the getpropertypois response
fun poiGroupsOf(v): Array = if (v is Array) flatten(v map poiGroupsOf($))
	else if (v is Object) (if (v.pois is Array) [v] else flatten(valuesOf(v) map poiGroupsOf($)))
	else []
var poiGroups = poiGroupsOf(vars.pois)
var poiGroup = (poiGroups filter ((g) -> first(g, ["propertyCode", "property_code"]) == propertyCode))[0]
	default (if (sizeOf(poiGroups) == 1) poiGroups[0] else null)
var nearby = take(objects(obj(poiGroup).pois) map ((poi) -> do {
	var la = num(poi.latitude default obj(poi.coordinates).latitude)
	var lo = num(poi.longitude default obj(poi.coordinates).longitude)
	---
	{
		poi_id: first(poi, ["poiId", "poi_id"]),
		title: first(poi, ["poiName", "title", "name"]),
		category: first(poi, ["poiCategory", "category"]),
		"type": first(poi, ["poiType", "type"]),
		icon_code: first(poi, ["iconCode", "icon_code"]),
		coordinates: if ((la == null) or (lo == null) or (la < -90) or (la > 90) or (lo < -180) or (lo > 180)) null else {latitude: la, longitude: lo},
		address: first(poi, ["poiAddress", "address"]),
		distance_minutes: do { var m = num(poi.distanceMinutes default poi.distance_minutes) --- if ((m != null) and (m >= 0)) round(m) else null }
	}
}) filter ((n) -> (n.poi_id != null) and (n.title != null) and (n.category != null) and (n."type" != null) and (n.icon_code != null) and (n.coordinates != null)), 5)
---
{
	property_code: propertyCode,
	property_name: propertyName,
	brand_code: slug(src.brand) default slug(src.brandName) default "ascott",
	brand_name: first(src, ["brandName"]) default "Ascott",
	brand_logo_url: first(src, ["brandlogo", "brandLogo"]) default "",
	banner_image_url: bannerImage,
	thumbnail_url: thumbnail,
	property_type: first(src, ["propertyType"]) default "",
	asr_participating: bool(src.asrParticipating) default false,
	email: first(src, ["email"]),
	phone: first(src, ["phone", "phoneNumber"]),
	tags: nonEmpty(objects(src.tag) map ((t) -> {
		propertyTagTitle: first(t, ["propertyTagTitle", "title"]),
		propertyTagPresent: bool(t.propertyTagPresent) default false
	}) filter ($.propertyTagTitle != null)),
	description_title: first(src, ["descriptionTitle"]),
	description: first(src, ["description"]),
	gallery: nonEmpty(gallerySrc map ((g) -> {
		path: first(g, ["path", "galleryImage"]),
		gallery_image: first(g, ["galleryImage"]),
		gallery_type: first(g, ["galleryType"]) default "image",
		title: first(g, ["title"]) default propertyName
	}) filter ($.path != null)),
	pricing: {
		availability_status: if (perNight == null) "on_request" else "available",
		per_night_rate_pref_curr: perNight,
		total_stay_rate_pref_curr: totalStay,
		strikethrough_rate: if ((strike != null) and (perNight != null) and (strike > perNight)) strike else null,
		currency: currency,
		next_available_date: null,
		based_on: {
			checkin: checkin,
			checkout: checkout,
			adults: adults,
			children: children,
			child_ages: nonEmpty(childAges)
		}
	},
	location: {
		city: first(src, ["cityName", "city"]) default first(loc, ["city", "cityName"]),
		country: first(src, ["countryName"]) default first(loc, ["country", "countryName"]),
		country_code: do {
			var cc = upper(first(src, ["countryCode"]) default first(loc, ["countryCode"]) default "")
			---
			if (cc matches /^[A-Z]{2}$/) cc else null
		},
		address: first(src, ["address"]) default first(loc, ["address"]),
		local_address: first(src, ["localAddress"]) default first(loc, ["localAddress"]),
		coordinates: do {
			var la = num(loc.latitude default src.latitude default obj(loc.coordinates).latitude)
			var lo = num(loc.longitude default src.longitude default obj(loc.coordinates).longitude)
			---
			if ((la == null) or (lo == null) or (la < -90) or (la > 90) or (lo < -180) or (lo > 180)) null else {latitude: la, longitude: lo}
		},
		map_image_url: first(loc, ["mapImage"]) default first(src, ["mapImage"]),
		// Upstream titles carry a "{0}" placeholder for the property name.
		getting_to_property: do {
			var g = obj(loc.gettingToProperty default src.gettingToProperty)
			var t = first(g, ["title"])
			var d = first(g, ["description"])
			---
			if ((t == null) or (d == null)) null else {title: (t replace /\{0\}/ with propertyName), description: d}
		},
		public_transport: do {
			var g = obj(loc.publicTransport default src.publicTransport)
			var t = first(g, ["title"])
			var d = first(g, ["description"])
			---
			if ((t == null) or (d == null)) null else {title: (t replace /\{0\}/ with propertyName), description: d}
		}
	},
	amenities: {facility_groups: facilityGroups},
	// Booking search carries no reviews; the zeroes keep the section present (the widget then shows no score).
	reviews: {
		average_ratings: do { var r = num(obj(src.reviews).averageRatings default src.averageRatings) --- if (r == null) 0 else if (r < 0) 0 else if (r > 5) 5 else r },
		total_number_of_reviews: do { var t = int(obj(src.reviews).totalNumberOfReviews default src.totalNumberOfReviews) --- if ((t != null) and (t >= 0)) t else 0 },
		score_label: first(obj(src.reviews), ["scoreLabel"]),
		individual_reviews: nonEmpty(objects(obj(src.reviews).individualReviews) map ((r) -> {
			reviewer_name: first(r, ["reviewerName", "name"]),
			rating: do { var n = num(r.rating default r.score) --- if (n == null) null else if (n < 0) 0 else if (n > 5) 5 else n },
			posted_date: isoDate(r.postedDate default r.date),
			source: first(r, ["source"]),
			text: first(r, ["text", "reviewText", "comment"])
		}) filter (($.reviewer_name != null) and ($.rating != null) and ($.text != null)))
	},
	hotel_information: {
		check_in_time: time24(src.checkInTime),
		check_out_time: time24(src.checkOutTime),
		staff_languages: if (isEmpty(languages)) null else {title: first(staffSrc, ["title"]), languages: languages},
		cancellation_policy: first(src, ["cancellationPolicy"]),
		// Upstream has only the isBestRateGuaranteeEnabled flag; the sentence comes from t02.bestrateguaranteedtext.
		best_rate_guaranteed: if (bool(src.isBestRateGuaranteeEnabled) default false) text(p('t02.bestrateguaranteedtext')) else null
	},
	nearby: nearby,
	asset_base_url: p('asset.baseUrl') default "https://www.discoverasr.com",
	accessibility_note: do {
		var t = first(accessibility, ["sustainableLabel", "label", "identityName"])
		var b = plain(obj(accessibility).tooltip)
		---
		if ((t == null) or (b == null)) null else {title: t, body: b}
	},
	awards: nonEmpty(objects(src.listOfAwards) map ((a) -> {
		image: first(a, ["image", "imagePath", "path"]),
		label: first(a, ["title", "label", "name"])
	}) filter ($.image != null))
}
