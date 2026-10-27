%dw 2.0
// get_room_rate_details (T-04) tool arguments (payload) -> {errors: [String], request: {...}} with server defaults.
// Accepts the short T-02 names (checkin, checkout, adults, children, currency) and the PRD names
// (checkinDate, checkoutDate, noOfadults, noOfchildren, currencyCode). memberId and any other unknown field
// are ignored: this is a non-logged-in journey.
//
// The request keeps the field names property-info-request.dwl reads (propertyCode, propertyName, checkin,
// checkout, adults, children, currency, language) and adds what dwl/room-rate-details.dwl needs:
// apartmentList (one entry per requested room, the order upstream answers in), childAges and priceIncludesTax.
// voucherCode is NOT accepted yet: property-info-request.dwl hardcodes voucherCode "", so upstream would never
// see it and meta.voucher_code_valid would report a flag computed without it.
output application/java
import try from dw::Runtime
import days from dw::core::Periods

// ---------- PLAYGROUND SHIM (not in the deployed file)
// Copy of dwl/rooms-validate-request.dwl for https://dataweave.mulesoft.com/learn/playground.
// Input 'payload' = the tool arguments (rooms-validate-request.playground-input.json).
var props = {
	"request.maxAdults": 8, "request.maxChildren": 6, "request.maxNights": 30, "rooms.maxRooms": 4,
	"default.checkinOffsetDays": 7, "default.nights": 1, "default.adults": 2, "default.children": 0,
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
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []

var body = if (payload is Object) payload else {}
var today = now() as Date
var maxAdults = p('request.maxAdults') as Number
var maxChildren = p('request.maxChildren') as Number
var maxNights = p('request.maxNights') as Number
var maxRooms = p('rooms.maxRooms') as Number

var code = text(body.propertyCode)
var name = text(body.propertyName)

var checkinIn = body.checkin default body.checkinDate
var checkinTry = if (checkinIn == null) {success: true, result: today + days(p('default.checkinOffsetDays') as Number)} else parseDate(checkinIn)
var checkin = checkinTry.result
var checkoutIn = body.checkout default body.checkoutDate
var checkoutTry = if (checkoutIn != null) parseDate(checkoutIn)
	else if (checkin is Date) {success: true, result: checkin + days(p('default.nights') as Number)}
	else {success: true}
var checkout = checkoutTry.result
var nights = if ((checkin is Date) and (checkout is Date)) daysBetween(checkin, checkout) else null

var adultsIn = body.adults default body.noOfadults
var childrenIn = body.children default body.noOfchildren
var adults = if (adultsIn == null) p('default.adults') as Number else number(adultsIn)
var children = if (childrenIn == null) p('default.children') as Number else number(childrenIn)
var currencyIn = body.currency default body.currencyCode
var currency = if (currencyIn == null) null else upper(text(currencyIn) default "")
var language = if (body.language == null) p('default.language') else text(body.language)

// One entry per requested room, in the order upstream answers (apartmentList[i] -> apartments[].room{i}).
// Without an apartmentList the top-level guests are one room, which is what the tool sends today.
fun ages(v) = if (v is Array) (v map number($)) else []
var topAges = ages(body.childAges)
var apartmentsIn = objects(body.apartmentList)
var apartmentList = if (isEmpty(apartmentsIn))
		[{noOfadults: adults, noOfchildren: children, childAges: topAges}]
	else apartmentsIn map ((a) -> do {
		var aIn = a.noOfadults default a.adults
		var cIn = a.noOfchildren default a.children
		---
		{
			noOfadults: if (aIn == null) adults else number(aIn),
			noOfchildren: if (cIn == null) 0 else number(cIn),
			childAges: ages(a.childAges)
		}
	})
var rooms = sizeOf(apartmentList)

// Each requested room is checked on its own, so the message names the room. Only when the caller sent an
// apartmentList: the single entry derived from the top-level guests is already covered by the checks above.
var roomErrors = if (isEmpty(apartmentsIn)) [] else flatten(apartmentList map ((a, i) -> [
	if (!inRange(a.noOfadults, 1, maxAdults)) "apartmentList[$(i)].noOfadults must be a whole number from 1 to $(maxAdults)." else null,
	if (!inRange(a.noOfchildren, 0, maxChildren)) "apartmentList[$(i)].noOfchildren must be a whole number from 0 to $(maxChildren)." else null,
	if ((a.childAges filter (!inRange($, 0, 17))) != []) "apartmentList[$(i)].childAges must be whole numbers from 0 to 17." else null,
	if (inRange(a.noOfchildren, 0, maxChildren) and (sizeOf(a.childAges) > a.noOfchildren)) "apartmentList[$(i)].childAges cannot list more ages than noOfchildren." else null
]))

var errors = ([
	if (!(payload is Object)) "Request body must be a JSON object." else null,
	if ((code == null) and (name == null)) "Provide propertyCode or propertyName." else null,
	if (code == null) null else if (!matchesRe(code, /^[A-Za-z0-9_-]{1,20}$/)) "propertyCode must be 1 to 20 letters, digits, hyphens or underscores." else null,
	if (name == null) null else if (sizeOf(name) > 200) "propertyName must be at most 200 characters." else null,
	if (!checkinTry.success) "checkin must be a date in yyyy-MM-dd format." else null,
	if (!checkoutTry.success) "checkout must be a date in yyyy-MM-dd format." else null,
	if (!(checkin is Date)) null else if (checkin < today) "checkin cannot be in the past." else null,
	if (nights == null) null else if (nights < 1) "checkout must be after checkin." else if (nights > maxNights) "The stay cannot be longer than $(maxNights) nights." else null,
	if (!inRange(adults, 1, maxAdults)) "adults must be a whole number from 1 to $(maxAdults)." else null,
	if (!inRange(children, 0, maxChildren)) "children must be a whole number from 0 to $(maxChildren)." else null,
	if ((topAges filter (!inRange($, 0, 17))) != []) "childAges must be whole numbers from 0 to 17." else null,
	if (!inRange(rooms, 1, maxRooms)) "apartmentList must have 1 to $(maxRooms) entries." else null,
	if ((body.priceIncludesTax != null) and !(body.priceIncludesTax is Boolean)) "priceIncludesTax must be true or false." else null,
	if (!matchesRe(language, /^[a-z]{2}(-[A-Za-z]{2,4})?$/)) "language must be a language code such as en or zh-CN." else null,
	if (currency == null) null else if (!matchesRe(currency, /^[A-Z]{3}$/)) "currency must be an ISO 4217 code such as SGD." else null
] ++ roomErrors) filter ($ != null)
---
{
	errors: errors,
	request: {
		propertyCode: code,
		propertyName: name,
		checkin: isoDate(checkin),
		checkout: isoDate(checkout),
		nights: nights,
		// The guests of all requested rooms together, for the booking search body and meta.
		adults: whole(sum(apartmentList map ((a) -> if (a.noOfadults is Number) a.noOfadults else 0))),
		children: whole(sum(apartmentList map ((a) -> if (a.noOfchildren is Number) a.noOfchildren else 0))),
		childAges: flatten(apartmentList map ((a) -> a.childAges map whole($))),
		rooms: rooms,
		apartmentList: apartmentList map ((a) -> {
			noOfadults: whole(a.noOfadults),
			noOfchildren: whole(a.noOfchildren),
			childAges: a.childAges map whole($)
		}),
		currency: currency,
		language: language,
		priceIncludesTax: if (body.priceIncludesTax is Boolean) body.priceIncludesTax else null,
		// get-poi-details.xml only runs when maxPois > 0; T-04 never asks for POIs.
		maxPois: 0,
		// Carried for the multi-room flow (get-multi-room-rates.xml), which sends them on to booking search and checks
		// noOfRooms against apartmentList. property-info-request.dwl (single room) reads none of them.
		// noOfRooms (mobile app) or rooms (older T-04 callers): only checked, the room count is apartmentList's.
		noOfRoomsSent: body.noOfRooms default body.rooms,
		perNightRate: if (body.perNightRate is Boolean) body.perNightRate else null,
		isExcludePriceStartFrom: if (body.isExcludePriceStartFrom is Boolean) body.isExcludePriceStartFrom else null,
		promoCorpCode: text(body.promoCorpCode)
	}
}
