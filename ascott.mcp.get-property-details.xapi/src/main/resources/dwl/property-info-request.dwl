%dw 2.0
// Request to booking search POST /v3/checkpropertyavailability (PUT returns 405), built from vars.request (the validated tool
// arguments). Mirrors the reference caller ODX_Booking_Search_Result_Apartment_Rate_Details_V3.xml ("Request
// Payload"), which follows the Mobile experience API. Only fields an anonymous MCP user can have are filled.
output application/json skipNullOn="everywhere"
var r = vars.request
var adults = (r.adults default 1) as String
var children = (r.children default 0) as String
---
{
	messageId: vars.traceId,
	memberId: "",
	language: r.language,
	currencyCode: r.currency default p('property.currency'),
	promoCorpCode: "",
	propertyListing: false,
	isModifyJourney: false,
	// An array, one code: propertyListing false allows exactly one.
	propertyCode: if (r.propertyCode == null) null else [r.propertyCode],
	checkinDate: r.checkin,
	checkoutDate: r.checkout,
	voucherCode: "",
	noOfRooms: 1,
	noOfadults: adults,
	noOfchildren: children,
	minPrice: "",
	maxPrice: "",
	perNightRate: true,
	apartmentList: [{childAges: [], noOfadults: adults, noOfchildren: children}],
	// Booking search's minBaseRate fails (500) when userCountry is empty; also sent as the "country" header.
	userCountry: p('default.userCountry') default "SG",
	isExcludePriceStartFrom: false,
	// Rate plans are tagged MOBILE / WEB; "mcp" matches none.
	channel: "mobile"
}
