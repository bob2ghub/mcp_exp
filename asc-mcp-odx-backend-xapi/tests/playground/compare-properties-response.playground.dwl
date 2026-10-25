%dw 2.0
// Booking search properties (ctx.lookups, one entry per requested code, in request order) + the request
// (ctx.compareRequest) -> compare_properties structuredContent, schemas/T06-compare-properties.structured-content.schema.json 0.2.0.
// T-06 only puts the requested properties side by side in one payload. It does not compare, rank, filter or recommend:
// that is left to the model and the widget.
// Every card has the same keys: a value upstream does not have is null, never left out (PRD EC-10).
// Prices follow the T-04 rules (room-rate-details.dwl): bookable rates only, taxes and fees included, per night,
// so a card's "from" price matches what T-04 shows after "See room and rates".
output application/json
import try from dw::Runtime
import take from dw::core::Arrays

// ---------- PLAYGROUND SHIM (not in the deployed file)
// Copy of dwl/compare-properties-response.dwl for https://dataweave.mulesoft.com/learn/playground.
// Input 'payload' = {compareRequest: <vars.compareRequest>, lookups: <vars.lookups>} (compare-properties-response.playground-input.json)
// Mule's vars.* are read from the payload (renamed ctx.*) and p('key') from the values below (compare-properties.yaml and uat-missing-keys.yaml).
var ctx = payload
var props = {"t06.minProperties": "2", "t06.maxProperties": "4", "t06.checkinOffsetDays": "30", "t06.nights": "1", "t06.adults": "1", "t06.children": "0", "t06.maxAmenityHighlights": "6", "t06.maxRoomTypes": "6", "request.maxAdults": "10", "request.maxChildren": "10", "request.maxNights": "90", "default.language": "en", "property.currency": "SGD", "asset.baseUrl": "https://www.discoverasr.com"}
fun p(key: String) = props[key]
// ---------- END SHIM

var req = ctx.compareRequest default {}
var nights = req.nights default 1
var currency = upper(req.currency default (p('property.currency') default ""))
var maxAmenities = p('t06.maxAmenityHighlights') as Number
var maxRoomTypes = p('t06.maxRoomTypes') as Number

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if ((v is Number) or (v is Boolean)) (v as String) else null
fun num(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun int(v) = do { var n = num(v) --- if (n == null) null else floor(n) }
fun bool(v) = if (v is Boolean) v else if (v is String) (["true", "y", "yes", "1"] contains lower(trim(v))) else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun obj(v) = if (v is Object) v else {}
fun money(n) = if (n == null) null else round(n * 100) / 100
fun firstText(o, keys) = if (o is Object) ((keys map ((k) -> text(o[k]))) filter ($ != null))[0] else null
fun nonEmpty(arr) = if (isEmpty(arr)) null else arr

// ---------- rates: the same rules as T-04
fun bookable(rp) = do {
	var template = upper(text(rp.ratePlanTemplate) default "")
	var templateName = lower(text(rp.ratePlanTemplateName) default "")
	var name = lower(text(rp.ratePlanName) default "")
	---
	(text(rp.ratePlanCode) != null) and (text(rp.ratePlanName) != null)
		and !((template == "AOA") or (templateName contains "member") or (name contains "acrs compare"))
}
fun rateOf(rp) = do {
	var stay = num(rp.totalStayRatePrefCurr)
	var total = if (stay == null) null else stay + (num(rp.totalTaxPrefCurrency) default 0)
	var perNight = if (total == null) null else total / nights
	var taxFactor = if ((stay != null) and (stay > 0)) total / stay else 1
	var strike = do { var s = num(rp.strikethroughRatePrefCurr) --- if (s == null) null else s * taxFactor / nights }
	---
	{
		perNight: perNight,
		total: total,
		strike: if ((strike != null) and (perNight != null) and (strike > perNight)) strike else null
	}
}

// ---------- one requested property -> its card
fun entry(lookup) = do {
	var src = obj(lookup.property)
	var rooms = flatten(objects(src.apartments) map objects($.room0)) orderBy (int($.ranking) default 999999)
	var ratedRooms = rooms map ((a) -> {
		room: a,
		rates: ((objects(a.ratePlan) filter bookable($)) map rateOf($)) filter (($.perNight != null) and ($.total != null))
	}) filter (!isEmpty($.rates))
	// This property's own lowest bookable rate (the card's "from" price).
	var cheapest = (flatten(ratedRooms map $.rates) orderBy $.perNight)[0]
	// Room types with a bookable rate; when the property has no rate at all, the rooms it lists.
	var typeRooms = if (isEmpty(ratedRooms)) rooms else (ratedRooms map $.room)
	var roomTypes = ((typeRooms map (text($.apartmentName) default text($.apartmentType))) filter ($ != null)) distinctBy lower($)
	var occupancy = max(((rooms map (int($.maxOccupancy) default int($.maxPersonInRoom))) filter (($ != null) and ($ > 0)))) default null
	var facilitiesSrc = obj(src.facilities)
	var groups = objects(facilitiesSrc.facilityGroup default src.facilityGroup default obj(src.amenities).facilityGroup)
	// The icon group ("Facilities & Amenities with Icon") first.
	var orderedGroups = (groups filter (text($.entityName) == "facilities-amenities")) ++ (groups filter (text($.entityName) != "facilities-amenities"))
	var amenities = ((flatten(orderedGroups map objects($.facilities)) filter (bool($.enabled) default true)) map ((f) -> {
		label: firstText(f, ["description", "name"]),
		icon_url: firstText(f, ["imagePath", "icon"])
	}) filter ($.label != null)) distinctBy lower($.label)
	var loc = obj(src.location)
	var city = firstText(src, ["cityName", "city"]) default firstText(loc, ["city"])
	var country = firstText(src, ["countryName"]) default firstText(loc, ["country"])
	var reviews = obj(src.reviews)
	var avgRating = num(reviews.averageRatings default src.averageRatings)
	var countryCode = upper(firstText(src, ["countryCode"]) default firstText(loc, ["countryCode"]) default "")
	---
	{
		code: lookup.code,
		status: lookup.status,
		city: city,
		card: {
			property_code: firstText(src, ["propertyCode"]) default lookup.code,
			property_name: firstText(src, ["propertyEnName", "propertyName"]) default lookup.code,
			is_asr: bool(src.asrParticipating),
			property_type: firstText(src, ["propertyType"]),
			brand_name: firstText(src, ["brandName"]),
			brand_logo_url: firstText(src, ["brandlogo", "brandLogo"]),
			banner_image_url: firstText(src, ["bannerImageMobile", "newPropertyThumbnail"]) default firstText(objects(src.gallery)[0], ["path", "galleryImage"]),
			card_location_line: do {
				var parts = ([city, country] filter ($ != null)) distinctBy lower($)
				---
				if (isEmpty(parts)) null else parts joinBy ", "
			},
			rating: if (avgRating == null) null else {
				average_ratings: if (avgRating < 0) 0 else if (avgRating > 5) 5 else avgRating,
				total_number_of_reviews: do { var t = int(reviews.totalNumberOfReviews default src.totalNumberOfReviews) --- if ((t != null) and (t >= 0)) t else 0 }
			},
			location: {
				area_label: firstText(loc, ["areaLabel", "area", "neighbourhood"]) default city,
				district_label: firstText(loc, ["districtLabel", "district"]) default country,
				country_code: if (countryCode matches /^[A-Z]{2}$/) countryCode else null
			},
			max_person_in_room: occupancy,
			room_types: nonEmpty(take(roomTypes, maxRoomTypes)),
			amenity_highlights: nonEmpty(take(amenities, maxAmenities)),
			pricing: {
				availability_status: if (cheapest == null) "on_request" else "available",
				per_night_rate_pref_curr: money(cheapest.perNight),
				strikethrough_rate: money(cheapest.strike),
				total_stay_rate_pref_curr: money(cheapest.total),
				currency: currency,
				// PRD ER-08 asks for the next available date; booking search does not return one.
				next_available_date: null
			}
		}
	}
}

var entries = (ctx.lookups default []) map entry($)
var found = entries filter ($.status == "ok")
var cities = ((found map $.city) filter ($ != null)) distinctBy lower($)
---
{
	meta: {
		total_results: sizeOf(found),
		location_query: if (isEmpty(cities)) null else cities joinBy ", ",
		currency: currency,
		checkin_date: req.checkin,
		checkout_date: req.checkout,
		nights: nights,
		noOfadults: req.adults,
		noOfchildren: req.children,
		attribution: "discoverasr.com",
		asset_base_url: p('asset.baseUrl') default "https://www.discoverasr.com",
		requested_property_codes: req.propertyCodes,
		dropped_property_codes: req.droppedPropertyCodes default []
	},
	properties: found map $.card,
	// Requested codes with no card, and why (PRD ER-04 / ER-03).
	missing_properties: (entries filter ($.status != "ok")) map ((e) -> if (e.status == "not_found")
		{property_code: e.code, reason_code: "not_found", message: "No property data was returned for this code and these dates."}
	else
		{property_code: e.code, reason_code: "lookup_failed", message: "The property details service did not answer for this property."})
}
