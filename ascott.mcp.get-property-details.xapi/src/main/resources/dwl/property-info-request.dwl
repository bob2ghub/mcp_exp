%dw 2.0
// Request to the property details process API. propertyName is sent only when no propertyCode was given.
output application/json skipNullOn="everywhere"
var r = vars.request
---
{
	version: p('app.version'),
	language: r.language,
	channel: p('app.channel'),
	propertyCode: r.propertyCode,
	propertyName: if (r.propertyCode == null) r.propertyName else null,
	checkin: r.checkin,
	checkout: r.checkout,
	adults: r.adults,
	children: r.children,
	// Always sent: calls with a currency succeed, and a service-offerings call without one got a 400.
	currency: r.currency default p('default.currency')
}
