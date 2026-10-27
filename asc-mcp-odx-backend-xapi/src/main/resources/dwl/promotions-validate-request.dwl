%dw 2.0
// get_promotions (T-05) tool arguments (payload) -> {errors: [String], request: {...}}.
// Input schema: schemas/T05-get-promotions.input.schema.json 0.1.0 (the owner's file, 2026-10-28).
//   countryCode      required, two letters (upper-cased)
//   city             optional; echoed (no property cache here to turn it into property codes)
//   propertyCode     optional, digits only
//   voucherName      optional keyword, matched against the title ignoring case
//   voucherCategory  optional array of categories, matched ignoring case (duplicates removed)
//   currencyCode     optional ISO 4217 (upper-cased); default property.currency, the one currency of every price
//   language         optional; one of the schema's tags, passed through. Any other value -> default.language
// memberId and any other field are ignored (anonymous MVP).
output application/java

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else null

var body = if (payload is Object) payload else {}
var languages = ["en", "zh-Hans", "zh-Hant", "fr", "de", "es", "ko", "ja", "id", "vi", "th"]

var country = upper(text(body.countryCode) default "")
var city = text(body.city)
var code = text(body.propertyCode)
var name = text(body.voucherName)
var categoriesIn = body.voucherCategory
var categories = if (categoriesIn is Array) ((categoriesIn map text($)) filter ($ != null)) distinctBy lower($) else []
var currencyIn = text(body.currencyCode)
var currency = if (currencyIn == null) null else upper(currencyIn)
var languageIn = text(body.language)
---
{
	errors: [
		if (!(payload is Object)) "Request body must be a JSON object." else null,
		if (country == "") "countryCode is required, for example \"SG\"." else if (!(country matches /^[A-Z]{2}$/)) "countryCode must be two letters, for example \"SG\"." else null,
		if ((body.city != null) and (city == null)) "city must be a non-blank string." else null,
		if (code == null) null else if (!(code matches /^[0-9]{1,20}$/)) "propertyCode must be digits only, for example \"51052\"." else null,
		if ((body.voucherName != null) and (name == null)) "voucherName must be a non-blank string." else null,
		if ((categoriesIn != null) and !(categoriesIn is Array)) "voucherCategory must be an array of categories, for example [\"package\"]."
			else if ((categoriesIn is Array) and (isEmpty(categories) or (sizeOf((categoriesIn map text($)) filter ($ == null)) > 0))) "voucherCategory must hold non-blank strings."
			else null,
		if (currency == null) null else if (!(currency matches /^[A-Z]{3}$/)) "currencyCode must be an ISO 4217 code such as SGD." else null
	] filter ($ != null),
	request: {
		countryCode: country,
		city: city,
		propertyCode: code,
		voucherName: name,
		voucherCategory: if (isEmpty(categories)) null else categories,
		currency: currency default (p('property.currency') default "SGD"),
		language: if (languages contains languageIn) languageIn else (p('default.language') default "en")
	}
}
