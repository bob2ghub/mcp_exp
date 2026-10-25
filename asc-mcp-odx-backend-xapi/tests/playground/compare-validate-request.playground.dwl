%dw 2.0
// compare_properties tool arguments (payload, already parsed) -> {errors: [String], request: {...}} with server defaults.
// Accepts the PRD TC-06 names (propertyCodes, checkinDate, noOfadults, currencyCode, ...) and the T-02 names (checkin,
// adults, currency, ...). memberId is ignored: this is a non-logged-in journey. The PRD's filter and scoring inputs
// (maxRate, facilities, roomType, poi, travellerProfile, serviceCategory) are ignored too: T-06 only returns the
// properties, it does not compare them. The request keeps the field names property-info-request.dwl reads
// (language, currency, checkin, checkout, adults, children).
output application/json
import try from dw::Runtime
import days from dw::core::Periods
import take, drop from dw::core::Arrays

// ---------- PLAYGROUND SHIM (not in the deployed file)
// Copy of dwl/compare-validate-request.dwl (output switched to JSON so the playground shows it).
// Input 'payload' = the T-06 request body (compare-validate-request.playground-input.json)
// Mule's vars.* are read from the payload (renamed ctx.*) and p('key') from the values below (compare-properties.yaml and uat-missing-keys.yaml).
var ctx = payload
var props = {"t06.minProperties": "2", "t06.maxProperties": "4", "t06.checkinOffsetDays": "30", "t06.nights": "1", "t06.adults": "1", "t06.children": "0", "t06.maxAmenityHighlights": "6", "t06.maxRoomTypes": "6", "request.maxAdults": "10", "request.maxChildren": "10", "request.maxNights": "90", "default.language": "en", "property.currency": "SGD", "asset.baseUrl": "https://www.discoverasr.com"}
fun p(key: String) = props[key]
// ---------- END SHIM

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if (v is Number) (v as String) else null
fun number(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun isWhole(n) = if (n is Number) (n mod 1) == 0 else false
fun inRange(n, lo, hi) = if (isWhole(n)) (n >= lo and n <= hi) else false
fun matchesRe(s, re) = if (s is String) (s matches re) else false
fun parseDate(v) = if (v is String) try(() -> trim(v) as Date {format: "yyyy-MM-dd"}) else {success: false}
fun isoDate(d) = if (d is Date) d as String {format: "yyyy-MM-dd"} else null
fun texts(v) = if (v is Array) ((v map text($)) filter ($ != null)) else if (text(v) != null) [text(v)] else []

var body = if (payload is Object) payload else {}
var today = now() as Date
var minProps = p('t06.minProperties') as Number
var maxProps = p('t06.maxProperties') as Number
var maxAdults = p('request.maxAdults') as Number
var maxChildren = p('request.maxChildren') as Number
var maxNights = p('request.maxNights') as Number

// Duplicates removed (PRD EC-01); only the first maxProps are compared and the rest are echoed back (EC-02, AC-04).
var codesAll = texts(body.propertyCodes default body.propertyCode) distinctBy $
var codes = take(codesAll, maxProps)
var badCodes = codes filter (!matchesRe($, /^[A-Za-z0-9_-]{1,20}$/))

var checkinIn = body.checkinDate default body.checkin
var checkinTry = if (checkinIn == null) {success: true, result: today + days(p('t06.checkinOffsetDays') as Number)} else parseDate(checkinIn)
var checkin = checkinTry.result
var checkoutIn = body.checkoutDate default body.checkout
var checkoutTry = if (checkoutIn != null) parseDate(checkoutIn)
	else if (checkin != null) {success: true, result: checkin + days(p('t06.nights') as Number)}
	else {success: true}
var checkout = checkoutTry.result
var nights = if ((checkin is Date) and (checkout is Date)) daysBetween(checkin, checkout) else null
var adultsIn = body.noOfadults default body.adults
var childrenIn = body.noOfchildren default body.children
var adults = if (adultsIn == null) p('t06.adults') as Number else number(adultsIn)
var children = if (childrenIn == null) p('t06.children') as Number else number(childrenIn)
var currencyIn = body.currencyCode default body.currency
var currency = if (currencyIn == null) null else upper(text(currencyIn) default "")
var language = if (body.language == null) p('default.language') else text(body.language)

var errors = [
	if (!(payload is Object)) "Request body must be a JSON object." else null,
	if (sizeOf(codesAll) < minProps) "propertyCodes must list at least $(minProps) different property codes." else null,
	if (isEmpty(badCodes)) null else "Each property code must be 1 to 20 letters, digits, hyphens or underscores: " ++ (badCodes joinBy ", ") ++ ".",
	if (!checkinTry.success) "checkinDate must be a date in yyyy-MM-dd format." else null,
	if (!checkoutTry.success) "checkoutDate must be a date in yyyy-MM-dd format." else null,
	if (checkin == null) null else if (checkin < today) "checkinDate cannot be in the past." else null,
	if (nights == null) null else if (nights < 1) "checkoutDate must be after checkinDate." else if (nights > maxNights) "The stay cannot be longer than $(maxNights) nights." else null,
	if (!inRange(adults, 1, maxAdults)) "noOfadults must be a whole number from 1 to $(maxAdults)." else null,
	if (!inRange(children, 0, maxChildren)) "noOfchildren must be a whole number from 0 to $(maxChildren)." else null,
	if (!matchesRe(language, /^[a-z]{2}(-[A-Za-z]{2,4})?$/)) "language must be a language code such as en or zh-CN." else null,
	if (currency == null) null else if (!matchesRe(currency, /^[A-Z]{3}$/)) "currencyCode must be an ISO 4217 code such as SGD." else null
] filter ($ != null)
---
{
	errors: errors,
	request: {
		propertyCodes: codes,
		droppedPropertyCodes: drop(codesAll, maxProps),
		checkin: isoDate(checkin),
		checkout: isoDate(checkout),
		nights: nights,
		adults: if (isWhole(adults)) floor(adults) else adults,
		children: if (isWhole(children)) floor(children) else children,
		currency: currency,
		language: language
	}
}
