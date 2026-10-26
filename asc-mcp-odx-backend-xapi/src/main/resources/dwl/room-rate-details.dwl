%dw 2.0
// Booking search property (vars.roomsSource, one propertyList[] entry) + the request (vars.roomsRequest)
// -> get_room_rate_details structuredContent, schemas/T04-get-room-rate-details.structured-content.schema.json 0.3.0.
//
// 0.3.0 shape: one room list PER REQUESTED ROOM (requested_rooms[], upstream apartments[i].room{i}),
// prices exactly as upstream gives them (no tax added) with each rate's tax amounts beside them,
// and no strikethrough price.
//
// Optional fields are left out when upstream has no value (skipNullOn="everywhere").
output application/json skipNullOn="everywhere"
import try from dw::Runtime

var src = vars.roomsSource default {}
var req = vars.roomsRequest default {}

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

// ---------------------------------------------------------------- rate plans

// Prices are passed through on upstream's own tax basis (isTaxInclusive says which), and the taxes
// are given beside them: per_night_tax = sum(taxes[].taxAmountPrefCurrPerNight), total_tax = totalTaxPrefCurrency.
// A tax-inclusive rate carries no tax on top, so both are 0.
fun ratePlan(rp) = do {
	var inclusive = bool(rp.isTaxInclusive) default false
	var perNight = num(rp.perNightRatePrefCurr) default num(rp.perNightRate)
	var stay = num(rp.totalStayRatePrefCurr) default num(rp.totalStayRate)
	var taxRows = objects(rp.taxes)
	var perNightTax = if (inclusive) 0
		else sum(taxRows map (num($.taxAmountPrefCurrPerNight) default num($.taxAmountPerNight) default 0))
	var totalTax = if (inclusive) 0 else (num(rp.totalTaxPrefCurrency) default num(rp.totalTax) default 0)
	var channel = upper(text(rp.ratePlanChannel) default "")
	---
	{
		rate_plan_code: text(rp.ratePlanCode),
		rate_plan_name: text(rp.ratePlanName),
		description: text(rp.ratePlanDescription),
		is_tax_inclusive: inclusive,
		per_night_rate: money(perNight),
		total_stay_rate: money(stay),
		per_night_tax: money(perNightTax),
		total_tax: money(totalTax),
		earn_asr_points: atLeast(int(rp.earnASRpoints), 0),
		non_refundable: bool(rp.nonRefundable),
		cancellation_description: text(rp.cancellationDescription),
		is_app_exclusive: if (channel == "") null else channel == "MOBILE"
	}
}

// Only rates an anonymous user arriving from ChatGPT can book on the website: no member rates
// (template AOA, template name "… Member …"), no comparison rates ("ACRS Compare") and no test rates
// (a TEST token in the name, e.g. "Best Flexible Rate_TEST NB").
fun bookable(rp) = do {
	var template = upper(text(rp.ratePlanTemplate) default "")
	var templateName = lower(text(rp.ratePlanTemplateName) default "")
	var name = lower(text(rp.ratePlanName) default "")
	---
	!((template == "AOA")
		or (templateName contains "member")
		or (name contains "acrs compare")
		or (name matches /(?s).*(^|[^a-z])test([^a-z].*|$)/))
}

// ---------------------------------------------------------------------- room

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
			map ((g) -> {
				group: text(g.refAmenityGroup),
				amenities: (objects(g.amenities) map (text($.description) default text($.name))) filter ($ != null)
			}))
			filter ((g) -> (g.group != null) and !isEmpty(g.amenities))
		---
		if (isEmpty(groups)) null else groups
	},
	// Bookable rates only, cheapest per night first.
	rate_plans: (objects(a.ratePlan) filter bookable($) map ratePlan($)
		filter ((rp) -> (rp.rate_plan_code != null) and (rp.rate_plan_name != null)
			and (rp.per_night_rate != null) and (rp.total_stay_rate != null)))
		orderBy $.per_night_rate
}

// ---------------------------------------------------------- requested rooms

// The stay that was searched. The booking search body is built from the same request, so these are the
// values upstream was asked for, not the user's words.
var apartmentList = do {
	var rows = objects(req.apartmentList)
	---
	// One room with the request's own guests when the validator does not send an apartmentList yet.
	if (isEmpty(rows)) [{noOfadults: req.adults, noOfchildren: req.children, childAges: req.childAges}] else rows
}

// Upstream answers apartmentList[i] with apartments[].room{i}, whether the room lists sit in one
// apartments entry or one entry each.
fun upstreamRooms(index) = do {
	var key = "room" ++ (index as String)
	---
	flatten(objects(src.apartments) map ((e) -> objects(e[key])))
}

fun requestedRoom(spec, index) = do {
	var rooms = ((upstreamRooms(index) map room($))
		filter ((r) -> (r.room_code != null) and (r.room_name != null) and !isEmpty(r.rate_plans)))
		orderBy ($.ranking default 999999)
	---
	{
		room_index: index + 1,
		noOfadults: atLeast(int(spec.noOfadults) default int(spec.adults), 1) default 1,
		noOfchildren: atLeast(int(spec.noOfchildren) default int(spec.children), 0) default 0,
		childAges: ((if (spec.childAges is Array) spec.childAges else []) map int($)) filter ($ != null),
		total_results: sizeOf(rooms),
		rooms: rooms
	}
}

var requestedRooms = apartmentList map ((spec, i) -> requestedRoom(spec, i))

// Every upstream room, whatever the room{i} key, for the fallbacks below.
var allRooms = flatten(objects(src.apartments) map ((e) -> flatten((e pluck $) map ((v) -> objects(v)))))

// The stay the rates were priced for, used only when the request carries no dates: upstream's
// nightlyRate dates are "MM/dd/yyyy", one per night, so checkout is the last night + 1 day.
fun usDate(v) = do { var s = text(v) --- if (s == null) null else try(() -> s as Date {format: "MM/dd/yyyy"}).result }
fun iso(d) = if (d is Date) (d as String {format: "yyyy-MM-dd"}) else null
var nightDates = ((flatten(allRooms map ((a) -> flatten(objects(a.ratePlan) map ((rp) -> objects(rp.nightlyRate)))))
	map usDate($.date)) filter ($ != null)) orderBy $
var stayFrom = iso(nightDates[0])
var stayTo = if (isEmpty(nightDates)) null else iso(nightDates[-1] + |P1D|)

var countryCode = upper(text(src.countryCode) default "")
// ISO 4217 of every price: the request's currency; upstream's …PrefCurr amounts are in it but
// upstream does not name it, so fall back to the property's, then a rate's, then the configured default.
var currency = upper(text(req.currency) default text(req.currencyCode) default text(src.currency)
	default text((allRooms[0].ratePlan default [])[0].currency) default (p('property.currency') default "SGD"))
---
{
	meta: {
		property_code: text(src.propertyCode) default text(req.propertyCode),
		property_name: text(src.propertyEnName) default text(src.propertyName) default text(req.propertyCode),
		brand_code: slug(src.brand) default slug(src.brandName) default "ascott",
		country_code: if (countryCode matches /^[A-Z]{2}$/) countryCode else null,
		asset_base_url: p('asset.baseUrl') default "https://www.discoverasr.com",
		checkin_date: text(req.checkin) default text(req.checkinDate) default stayFrom,
		checkout_date: text(req.checkout) default text(req.checkoutDate) default stayTo,
		// The guests of all requested rooms together.
		noOfadults: sum(requestedRooms map $.noOfadults),
		noOfchildren: sum(requestedRooms map $.noOfchildren),
		noOfRooms: sizeOf(requestedRooms),
		is_all_avail: bool(src.isAllAvail),
		currency: currency,
		price_includes_tax: bool(req.priceIncludesTax),
		// Only answered when the caller sent a voucher code.
		voucher_code_valid: if (text(req.voucherCode) == null) null else (bool(src.isCodeValid) default false)
	},
	requested_rooms: requestedRooms
}
