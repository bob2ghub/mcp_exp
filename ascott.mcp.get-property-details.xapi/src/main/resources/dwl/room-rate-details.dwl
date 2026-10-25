%dw 2.0
// Booking search property (vars.roomsSource, one propertyList[] entry) + the request (vars.roomsRequest)
// -> get_room_rate_details structuredContent, schemas/room-rate-details-structured-content.schema.json 0.1.0.
// Upstream names are the ones the schema cites. Optional fields are left out when upstream has no value.
output application/json skipNullOn="everywhere"
import try from dw::Runtime

var src = vars.roomsSource default {}
var req = vars.roomsRequest
var nights = req.nights default 1

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if ((v is Number) or (v is Boolean)) (v as String) else null
fun num(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun int(v) = do { var n = num(v) --- if (n == null) null else floor(n) }
fun bool(v) = if (v is Boolean) v else if (v is String) (lower(trim(v)) == "true") else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun money(n) = if (n == null) null else round(n * 100) / 100
fun atLeast(n, min) = if ((n != null) and (n >= min)) n else null
fun slug(v) = do {
	var s = (lower(text(v) default "") replace /[^a-z0-9]+/ with "-") replace /^-+|-+$/ with ""
	---
	if (s == "") null else s
}

// Prices are taxes and fees included: stay + tax, per night = that / nights. Strikethrough on the same basis.
fun ratePlan(rp) = do {
	var stay = num(rp.totalStayRatePrefCurr)
	var total = if (stay == null) null else stay + (num(rp.totalTaxPrefCurrency) default 0)
	var perNight = if (total == null) null else total / nights
	var taxFactor = if ((stay != null) and (stay > 0)) total / stay else 1
	var strike = do { var s = num(rp.strikethroughRatePrefCurr) --- if (s == null) null else s * taxFactor }
	var hasStrike = (strike != null) and (perNight != null) and (strike > perNight)
	var save = num(rp.savePercentage)
	var channel = upper(text(rp.ratePlanChannel) default "")
	---
	{
		rate_plan_code: text(rp.ratePlanCode),
		rate_plan_name: text(rp.ratePlanName),
		description: text(rp.ratePlanDescription),
		per_night_rate: money(perNight),
		total_stay_rate: money(total),
		strikethrough_rate: if (hasStrike) money(strike) else null,
		save_percentage: if (hasStrike and (save != null) and (save > 0) and (save <= 100)) save else null,
		earn_asr_points: atLeast(int(rp.earnASRpoints), 0),
		non_refundable: bool(rp.nonRefundable),
		cancellation_description: text(rp.cancellationDescription),
		is_app_exclusive: if (channel == "") null else channel == "MOBILE"
	}
}

fun room(a) = {
	room_code: text(a.apartmentType),
	room_name: text(a.apartmentName),
	room_category: text(a.apartmentCategoryCode),
	ranking: atLeast(int(a.ranking), 1),
	description: text(a.roomInformation),
	bed_type: text(a.bedType),
	max_person_in_room: text(a.maxPersonInRoom),
	max_occupancy: atLeast(int(a.maxOccupancy), 1),
	size_sqm: do { var d = num(a.dimension) --- if ((d != null) and (d > 0)) d else null },
	units_remaining: atLeast(int(a.noOfUnitRemaining), 0),
	thumbnail_url: text(a.thumbnailImage),
	banner_image_url: text(a.bannerImageMobile),
	floor_plan_url: text(a.floorPlanPath),
	gallery: do {
		var g = (objects(a.imageGalleryItems)
			filter ((i) -> lower(text(i.galleryType) default "image") == "image")
			map ((i) -> {path: text(i.galleryImage) default text(i.path), title: text(i.title)}))
			filter ($.path != null)
		---
		if (isEmpty(g)) null else g
	},
	amenity_groups: do {
		var groups = (objects(a.amenityGroups)
			map ((g) -> {group: text(g.refAmenityGroup), amenities: (objects(g.amenities) map text($.description)) filter ($ != null)}))
			filter ((g) -> (g.group != null) and !isEmpty(g.amenities))
		---
		if (isEmpty(groups)) null else groups
	},
	// Every rate is kept until the 'Which rates' filter (test / member-only rates) is defined; cheapest first.
	rate_plans: (objects(a.ratePlan) map ratePlan($)
		filter ((p) -> (p.rate_plan_code != null) and (p.rate_plan_name != null) and (p.per_night_rate != null) and (p.total_stay_rate != null)))
		orderBy $.per_night_rate
}

// apartments[].room0[]: only room0 is listed (schema: 'Several rooms').
var rooms = ((flatten(objects(src.apartments) map objects($.room0)) map room($))
	filter ((r) -> (r.room_code != null) and (r.room_name != null) and !isEmpty(r.rate_plans)))
	orderBy ($.ranking default 999999)

var countryCode = upper(text(src.countryCode) default "")
var currency = upper(req.currency default (p('property.currency') default ""))
---
{
	meta: {
		property_code: text(src.propertyCode) default req.propertyCode,
		property_name: text(src.propertyEnName) default text(src.propertyName) default req.propertyCode,
		brand_code: slug(src.brand) default slug(src.brandName) default "ascott",
		country_code: if (countryCode matches /^[A-Z]{2}$/) countryCode else null,
		asset_base_url: p('asset.baseUrl') default "https://www.discoverasr.com",
		checkin_date: req.checkin,
		checkout_date: req.checkout,
		noOfadults: req.adults,
		noOfchildren: req.children,
		// The booking search request always asks for one room (property-info-request.dwl).
		noOfRooms: 1,
		is_all_avail: bool(src.isAllAvail),
		currency: currency,
		total_results: sizeOf(rooms)
	},
	rooms: rooms
}
