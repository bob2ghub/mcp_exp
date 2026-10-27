%dw 2.0
// Booking search POST /v3/checkpropertyavailability body for SEVERAL rooms, built from vars.roomsRequest (validated
// by dwl/rooms-validate-request.dwl) and the caller's own body (vars.multiRoomInput) for the few pass-through flags.
//
// Same contract as dwl/property-info-request.dwl (the single-room body every other tool sends), except that
// apartmentList carries one entry per requested room, with that room's guests and child ages, and noOfRooms is its
// length. Upstream answers apartmentList[i] with apartments[].room{i}, which dwl/room-rate-details.dwl maps.
//
// Not passed through: memberId (non-logged-in journey, always ""), messageId (vars.traceId, as every other call),
// version / platform (not part of the booking search contract) and voucherCode (see rooms-validate-request.dwl).
output application/json skipNullOn="everywhere"

var r = vars.roomsRequest default {}
var input = if (vars.multiRoomInput is Object) vars.multiRoomInput else {}
var rooms = r.apartmentList default []
fun bool(v, dflt) = if (v is Boolean) v else dflt
fun text(v) = if (v is String) trim(v) else ""
---
{
	messageId: vars.traceId,
	memberId: "",
	language: r.language,
	currencyCode: r.currency default p('property.currency'),
	promoCorpCode: text(input.promoCorpCode),
	propertyListing: false,
	isModifyJourney: false,
	// An array, one code: propertyListing false allows exactly one.
	propertyCode: if (r.propertyCode == null) null else [r.propertyCode],
	checkinDate: r.checkin,
	checkoutDate: r.checkout,
	voucherCode: "",
	noOfRooms: sizeOf(rooms),
	// The guests of all rooms together, as strings like the single-room body. The mobile app's own body leaves these
	// two out for multi-room searches; drop them here if upstream ever prices the property lead-in from them wrongly.
	noOfadults: (r.adults default 1) as String,
	noOfchildren: (r.children default 0) as String,
	minPrice: "",
	maxPrice: "",
	perNightRate: bool(input.perNightRate, true),
	apartmentList: rooms map ((a) -> {
		childAges: a.childAges default [],
		noOfadults: (a.noOfadults default 1) as String,
		noOfchildren: (a.noOfchildren default 0) as String
	}),
	// Booking search's minBaseRate fails (500) when userCountry is empty.
	userCountry: p('default.userCountry') default "SG",
	isExcludePriceStartFrom: bool(input.isExcludePriceStartFrom, false),
	// Rate plans are tagged MOBILE / WEB; "mcp" matches none.
	channel: "mobile"
}
