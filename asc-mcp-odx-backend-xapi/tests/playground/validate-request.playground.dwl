%dw 2.0
// get_property_details (T-02) tool arguments -> {errors: [String], request: {...}} with server defaults applied.
// Input contract: schemas/T02-get-property-details.input.schema.json 0.2.0 (the owner's file, 2026-10-28):
//   propertyCode   required, digits only
//   checkinDate    yyyy-MM-dd, today or later; default today + t02.checkinOffsetDays (30)
//   checkoutDate   yyyy-MM-dd, after checkinDate; default check-in + t02.nights (1)
//   noOfadults     whole number >= 1 (up to request.maxAdults); default 1
//   noOfchildren   whole number >= 0 (up to request.maxChildren); default 0
//   childAges      whole numbers >= 0, one per child: REQUIRED when noOfchildren > 0, length = noOfchildren
//   currencyCode   ISO 4217 (upper-cased); default: the property's own currency (left null here)
//   language       one of the schema's 11 tags; any other value falls back to default.language (as T-05 / T-08)
// Also accepted, so older callers keep working: the short names checkin, checkout, adults, children, currency
// (the schema name wins when both are sent), a propertyCode sent as a number or as a one-code array (the booking
// search shape), and maxPois (server-side, not in the schema). propertyName is no longer accepted (not in 0.2.0).
// Every other field is ignored: this is a non-logged-in journey.
//
// The request keeps the names property-info-request.dwl, get-poi-details.xml and map-structured-content.dwl read
// (propertyCode, checkin, checkout, adults, children, currency, language, maxPois) and adds childAges and nights.
output application/java
import try from dw::Runtime
import days from dw::core::Periods

// ---------- PLAYGROUND SHIM (not in the deployed file)
// Copy of dwl/validate-request.dwl for https://dataweave.mulesoft.com/learn/playground.
// Input 'payload' = the tool arguments (validate-request.playground-input.json). t02.* keys unset: their defaults apply.
var props = {
	"request.maxAdults": 8, "request.maxChildren": 6, "request.maxNights": 30, "poi.maxPerProperty": 5,
	"default.language": "en"
}
fun p(key: String) = props[key]
// ---------- END SHIM

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if (v is Number) (v as String) else null
fun number(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun isWhole(n) = if (n is Number) (n mod 1) == 0 else false
fun inRange(n, lo, hi) = if (isWhole(n)) (n >= lo and n <= hi) else false
fun matchesRe(s, re) = if (s is String) (s matches re) else false
fun parseDate(v) = if (v is String) try(() -> trim(v) as Date {format: "yyyy-MM-dd"}) else {success: false}
fun isoDate(d) = if (d is Date) d as String {format: "yyyy-MM-dd"} else null
fun whole(n) = if (isWhole(n)) floor(n) else n

var languages = ["en", "zh-Hans", "zh-Hant", "fr", "de", "es", "ko", "ja", "id", "vi", "th"]

var body = if (payload is Object) payload else {}
var today = now() as Date
var maxAdults = p('request.maxAdults') as Number
var maxChildren = p('request.maxChildren') as Number
var maxNights = p('request.maxNights') as Number
var maxPoisLimit = (p('poi.maxPerProperty') default 5) as Number

var codeIn = if ((body.propertyCode is Array) and (sizeOf(body.propertyCode) == 1)) body.propertyCode[0] else body.propertyCode
var code = text(codeIn)

var checkinIn = body.checkinDate default body.checkin
var checkinTry = if (checkinIn == null) {success: true, result: today + days((p('t02.checkinOffsetDays') default 30) as Number)} else parseDate(checkinIn)
var checkin = checkinTry.result
var checkoutIn = body.checkoutDate default body.checkout
var checkoutTry = if (checkoutIn != null) parseDate(checkoutIn)
	else if (checkin is Date) {success: true, result: checkin + days((p('t02.nights') default 1) as Number)}
	else {success: true}
var checkout = checkoutTry.result
var nights = if ((checkin is Date) and (checkout is Date)) daysBetween(checkin, checkout) else null

var adultsIn = body.noOfadults default body.adults
var childrenIn = body.noOfchildren default body.children
var adults = if (adultsIn == null) 1 else number(adultsIn)
var children = if (childrenIn == null) 0 else number(childrenIn)
var agesIn = body.childAges
var childAges = if (agesIn is Array) (agesIn map number($)) else []

var currencyIn = body.currencyCode default body.currency
var currency = if (currencyIn == null) null else upper(text(currencyIn) default "")
var languageIn = text(body.language)
var language = if (languages contains languageIn) languageIn else p('default.language')
var maxPois = if (body.maxPois == null) maxPoisLimit else number(body.maxPois)

var errors = [
	if (!(payload is Object)) "Request body must be a JSON object." else null,
	if ((body.propertyCode is Array) and (sizeOf(body.propertyCode) != 1)) "propertyCode must be one code, such as \"51052\"."
		else if (code == null) "propertyCode is required." else if (!matchesRe(code, /^[0-9]{1,20}$/)) "propertyCode must be digits only, such as \"51052\"." else null,
	if (!checkinTry.success) "checkinDate must be a date in YYYY-MM-DD format." else null,
	if (!checkoutTry.success) "checkoutDate must be a date in YYYY-MM-DD format." else null,
	if (!(checkin is Date)) null else if (checkin < today) "checkinDate cannot be in the past." else null,
	if (nights == null) null else if (nights < 1) "checkoutDate must be after checkinDate." else if (nights > maxNights) "The stay cannot be longer than $(maxNights) nights." else null,
	if (!inRange(adults, 1, maxAdults)) "noOfadults must be a whole number from 1 to $(maxAdults)." else null,
	if (!inRange(children, 0, maxChildren)) "noOfchildren must be a whole number from 0 to $(maxChildren)." else null,
	if ((agesIn != null) and !(agesIn is Array)) "childAges must be an array of ages." else null,
	if ((childAges filter (!inRange($, 0, 17))) != []) "childAges must be whole numbers from 0 to 17." else null,
	if (!inRange(children, 1, maxChildren)) null
		else if (isEmpty(childAges)) "childAges is required when noOfchildren is above 0: give one age per child."
		else if (sizeOf(childAges) != children) "childAges must list exactly one age per child ($(children))." else null,
	if (inRange(children, 0, 0) and !isEmpty(childAges)) "childAges must be empty when noOfchildren is 0." else null,
	if (currency == null) null else if (!matchesRe(currency, /^[A-Z]{3}$/)) "currencyCode must be an ISO 4217 code such as SGD." else null,
	if (!inRange(maxPois, 0, maxPoisLimit)) "maxPois must be a whole number from 0 to $(maxPoisLimit)." else null
] filter ($ != null)
---
{
	errors: errors,
	request: {
		propertyCode: code,
		checkin: isoDate(checkin),
		checkout: isoDate(checkout),
		nights: nights,
		adults: whole(adults),
		children: whole(children),
		childAges: childAges map whole($),
		currency: currency,
		language: language,
		maxPois: whole(maxPois)
	}
}
