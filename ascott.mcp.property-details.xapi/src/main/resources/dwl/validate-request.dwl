%dw 2.0
// get_property_details tool arguments -> {errors: [String], request: {...}} with server defaults applied.
// Non-logged-in journey: no user, member or session fields. Unknown fields are ignored.
// checkinDate / checkoutDate (the ODX names) are accepted as aliases of checkin / checkout.
// Date rules follow the ODX flow: checkin not before today, checkout after checkin.
output application/java
import try from dw::Runtime
import days from dw::core::Periods

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if (v is Number) (v as String) else null
// A whole number, the default when absent, or -1 when present but not a whole number (fails the range check).
fun wholeOr(v, dflt) = if (v == null) dflt
	else if ((v is Number) and ((v mod 1) == 0)) v
	else if ((v is String) and (trim(v) matches /^[0-9]+$/)) trim(v) as Number
	else -1
fun parseDate(v) = if ((v is String) and (trim(v) matches /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)) try(() -> trim(v) as Date {format: "yyyy-MM-dd"}) else {success: false}
fun isoDate(d) = if (d is Date) d as String {format: "yyyy-MM-dd"} else null
fun matchesRe(s, re) = if (s is String) (s matches re) else false

var body = if (payload is Object) payload else {}
var today = now() as Date
var maxAdults = p('request.maxAdults') as Number
var maxChildren = p('request.maxChildren') as Number
var maxNights = p('request.maxNights') as Number
var maxPoisLimit = p('poi.maxPerProperty') as Number

var code = text(body.propertyCode)
var name = text(body.propertyName)
var checkinIn = body.checkin default body.checkinDate
var checkoutIn = body.checkout default body.checkoutDate
var checkinTry = if (checkinIn == null) {success: true, result: today + days(p('default.checkinOffsetDays') as Number)} else parseDate(checkinIn)
var checkin = if (checkinTry.success) checkinTry.result else null
var checkoutTry = if (checkoutIn != null) parseDate(checkoutIn)
	else if (checkin != null) {success: true, result: checkin + days(p('default.nights') as Number)}
	else {success: true}
var checkout = if (checkoutTry.success) checkoutTry.result else null
var nights = if ((checkin != null) and (checkout != null)) daysBetween(checkin, checkout) else null
var adults = wholeOr(body.adults, p('default.adults') as Number)
var children = wholeOr(body.children, p('default.children') as Number)
var maxPois = wholeOr(body.maxPois, maxPoisLimit)
var language = if (body.language == null) p('property.language') else lower(text(body.language) default "")
var currency = if (body.currency == null) null else upper(text(body.currency) default "")

var errors = [
	("Request body must be a JSON object.") if (!(payload is Object)),
	("Provide propertyCode or propertyName.") if ((code == null) and (name == null)),
	("propertyCode must be 1 to 20 letters or digits.") if ((code != null) and !matchesRe(code, /^[A-Za-z0-9]{1,20}$/)),
	("propertyName must be at most 200 characters.") if ((name != null) and (sizeOf(name) > 200)),
	("checkin must be a date in yyyy-MM-dd format.") if (!checkinTry.success),
	("checkout must be a date in yyyy-MM-dd format.") if (!checkoutTry.success),
	("checkin cannot be before today.") if ((checkin != null) and (checkin < today)),
	("checkout must be after checkin.") if ((nights != null) and (nights < 1)),
	("The stay cannot be longer than $(maxNights) nights.") if ((nights != null) and (nights > maxNights)),
	("adults must be a whole number from 1 to $(maxAdults).") if ((adults < 1) or (adults > maxAdults)),
	("children must be a whole number from 0 to $(maxChildren).") if ((children < 0) or (children > maxChildren)),
	("maxPois must be a whole number from 0 to $(maxPoisLimit).") if ((maxPois < 0) or (maxPois > maxPoisLimit)),
	("language must be a language code such as en or zh-cn.") if (!matchesRe(language, /^[a-z]{2}(-[a-z]{2,4})?$/)),
	("currency must be an ISO 4217 code such as SGD.") if ((currency != null) and !matchesRe(currency, /^[A-Z]{3}$/))
]
---
{
	errors: errors,
	request: {
		propertyCode: code,
		propertyName: name,
		checkin: isoDate(checkin),
		checkout: isoDate(checkout),
		adults: adults,
		children: children,
		currency: currency,
		language: language,
		maxPois: maxPois
	}
}
