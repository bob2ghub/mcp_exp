%dw 2.0
// get_property_details tool arguments -> {errors: [String], request: {...}} with server defaults applied.
// Unknown fields are ignored. No user or session fields: this is a non-logged-in journey.
output application/java
import try from dw::Runtime
import days from dw::core::Periods

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if (v is Number) (v as String) else null
fun number(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun isWhole(n) = if (n is Number) (n mod 1) == 0 else false
fun inRange(n, lo, hi) = if (isWhole(n)) (n >= lo and n <= hi) else false
fun matchesRe(s, re) = if (s is String) (s matches re) else false
fun parseDate(v) = if (v is String) try(() -> trim(v) as Date {format: "yyyy-MM-dd"}) else {success: false}
fun isoDate(d) = if (d is Date) d as String {format: "yyyy-MM-dd"} else null

var body = if (payload is Object) payload else {}
var today = now() as Date
var maxAdults = p('request.maxAdults') as Number
var maxChildren = p('request.maxChildren') as Number
var maxNights = p('request.maxNights') as Number
var maxPoisLimit = p('poi.maxPerProperty') as Number

var code = text(body.propertyCode)
var name = text(body.propertyName)
var checkinTry = if (body.checkin == null) {success: true, result: today + days(p('default.checkinOffsetDays') as Number)} else parseDate(body.checkin)
var checkin = checkinTry.result
var checkoutTry = if (body.checkout != null) parseDate(body.checkout)
	else if (checkin != null) {success: true, result: checkin + days(p('default.nights') as Number)}
	else {success: true}
var checkout = checkoutTry.result
var nights = if ((checkin != null) and (checkout != null)) daysBetween(checkin, checkout) else null
var adults = if (body.adults == null) p('default.adults') as Number else number(body.adults)
var children = if (body.children == null) p('default.children') as Number else number(body.children)
var maxPois = if (body.maxPois == null) maxPoisLimit else number(body.maxPois)
var language = if (body.language == null) p('default.language') else text(body.language)
var currency = if (body.currency == null) null else upper(text(body.currency) default "")

var errors = [
	if (!(payload is Object)) "Request body must be a JSON object." else null,
	if ((code == null) and (name == null)) "Provide propertyCode or propertyName." else null,
	if (code == null) null else if (!matchesRe(code, /^[A-Za-z0-9_-]{1,20}$/)) "propertyCode must be 1 to 20 letters, digits, hyphens or underscores." else null,
	if (name == null) null else if (sizeOf(name) > 200) "propertyName must be at most 200 characters." else null,
	if (!checkinTry.success) "checkin must be a date in yyyy-MM-dd format." else null,
	if (!checkoutTry.success) "checkout must be a date in yyyy-MM-dd format." else null,
	if (checkin == null) null else if (checkin < today) "checkin cannot be in the past." else null,
	if (nights == null) null else if (nights < 1) "checkout must be after checkin." else if (nights > maxNights) "The stay cannot be longer than $(maxNights) nights." else null,
	if (!inRange(adults, 1, maxAdults)) "adults must be a whole number from 1 to $(maxAdults)." else null,
	if (!inRange(children, 0, maxChildren)) "children must be a whole number from 0 to $(maxChildren)." else null,
	if (!inRange(maxPois, 0, maxPoisLimit)) "maxPois must be a whole number from 0 to $(maxPoisLimit)." else null,
	if (!matchesRe(language, /^[a-z]{2}(-[A-Za-z]{2,4})?$/)) "language must be a language code such as en or zh-CN." else null,
	if (currency == null) null else if (!matchesRe(currency, /^[A-Z]{3}$/)) "currency must be an ISO 4217 code such as SGD." else null
] filter ($ != null)
---
{
	errors: errors,
	request: {
		propertyCode: code,
		propertyName: name,
		checkin: isoDate(checkin),
		checkout: isoDate(checkout),
		adults: if (isWhole(adults)) floor(adults) else adults,
		children: if (isWhole(children)) floor(children) else children,
		currency: currency,
		language: language,
		maxPois: if (isWhole(maxPois)) floor(maxPois) else maxPois
	}
}
