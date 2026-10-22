%dw 2.0
// Body of PUT /v3/checkpropertyavailability. Same fields as the "Request Payload" step of
// ODX_Booking_Search_Result_Apartment_Rate_Details_V3.xml; only what MCP cannot know is left out
// (memberId, promo / voucher / corporate codes, the guest's countryOfResidence).
output application/json skipNullOn="everywhere"
var r = vars.request
---
{
	messageId: vars.traceId,
	language: r.language,
	currencyCode: r.currency default p('property.currency'),
	propertyListing: false,
	propertyCode: [r.propertyCode],
	checkinDate: r.checkin,
	checkoutDate: r.checkout,
	noOfRooms: 1,
	// ODX sends these as strings ("1"), and noOfchildren only when given.
	noOfadults: r.adults as String,
	noOfchildren: if (r.children > 0) (r.children as String) else null,
	userCountry: p('https.bookingsearchprocessapi.userCountry'),
	isExcludePriceStartFrom: false,
	channel: p('https.bookingsearchprocessapi.channel')
}
