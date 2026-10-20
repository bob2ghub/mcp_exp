%dw 2.0
// Request to getpropertypois for the one property this call is about.
output application/json
---
{
	version: p('app.version'),
	language: vars.request.language,
	channel: p('app.channel'),
	propertyCode: [vars.propertyCode],
	maxPoisPerProperty: vars.request.maxPois
}
