%dw 2.0
// create_booking (T-08) tool arguments (payload) -> {errors: [String], request: {...}} with server defaults.
// Input schema: schemas/T08-create-booking.input.schema.json 0.1.0 (the owner's file, 2026-10-28).
//
//   propertyCode   required, digits only
//   checkinDate    default today + t08.checkinOffsetDays (30, PRD §5); today or later
//   checkoutDate   default check-in + t08.nights (1); after check-in, at most request.maxNights nights
//   apartmentList  default one room for 1 adult; 1 to rooms.maxRooms entries, each {noOfadults >= 1, noOfchildren >= 0,
//                  childAges (one age 0-17 per child: its length MUST equal noOfchildren), roomCode + ratePlanCode
//                  (both or neither)}
//   currencyCode   optional ISO 4217 (upper-cased); default: the property's currency (T-04 rule, in room-rate-details.dwl)
//   voucherCode    optional; sent to booking search, answered in meta.voucher_code_valid
//   language       optional; one of the schema's tags, passed through. Any other value is ignored (default.language),
//                  as the schema tells the model to omit it then.
// memberId, enrollAsrOnCheckout and any other field are ignored (anonymous MVP).
//
// The request keeps the names dwl/room-rate-details.dwl reads (propertyCode, checkin, checkout, adults, children,
// childAges, apartmentList, currency, voucherCode), so the T-04 mapping can price every room.
output application/java
import try from dw::Runtime
import days from dw::core::Periods

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else null
fun isInt(v) = if (v is Number) (v mod 1) == 0 else false
fun inRange(v, lo, hi) = if (isInt(v)) (v >= lo and v <= hi) else false
fun parseDate(v) = if (v is String) try(() -> trim(v) as Date {format: "yyyy-MM-dd"}) else {success: false}
fun iso(d) = if (d is Date) d as String {format: "yyyy-MM-dd"} else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun whole(n) = if (isInt(n)) floor(n) else n

var body = if (payload is Object) payload else {}
var today = now() as Date
var maxAdults = p('request.maxAdults') as Number
var maxChildren = p('request.maxChildren') as Number
var maxNights = p('request.maxNights') as Number
var maxRooms = p('rooms.maxRooms') as Number
var offsetDays = (p('t08.checkinOffsetDays') default 30) as Number
var defaultNights = (p('t08.nights') default 1) as Number
var languages = ["en", "zh-Hans", "zh-Hant", "fr", "de", "es", "ko", "ja", "id", "vi", "th"]

var code = text(body.propertyCode)

var checkinTry = if (body.checkinDate == null) {success: true, result: today + days(offsetDays)} else parseDate(body.checkinDate)
var checkin = checkinTry.result
var checkoutTry = if (body.checkoutDate != null) parseDate(body.checkoutDate)
	else if (checkin is Date) {success: true, result: checkin + days(defaultNights)}
	else {success: true}
var checkout = checkoutTry.result
var nights = if ((checkin is Date) and (checkout is Date)) daysBetween(checkin, checkout) else null

var currencyIn = text(body.currencyCode)
var currency = if (currencyIn == null) null else upper(currencyIn)
var languageIn = text(body.language)
var language = if (languages contains languageIn) languageIn else p('default.language')

var listGiven = body.apartmentList != null
var roomsIn = if (listGiven) objects(body.apartmentList) else [{noOfadults: 1, noOfchildren: 0, childAges: []}]
var rooms = roomsIn map ((a) -> {
	noOfadults: a.noOfadults,
	noOfchildren: a.noOfchildren,
	childAges: a.childAges,
	roomCode: text(a.roomCode),
	ratePlanCode: text(a.ratePlanCode),
	roomCodeSent: a.roomCode != null,
	ratePlanCodeSent: a.ratePlanCode != null
})

// One message per problem; per-room messages name the room as the input does (apartmentList[0] is "Room 1").
var roomErrors = flatten(rooms map ((a, i) -> [
	if (!inRange(a.noOfadults, 1, maxAdults)) "apartmentList[$(i)].noOfadults must be a whole number from 1 to $(maxAdults)." else null,
	if (!inRange(a.noOfchildren, 0, maxChildren)) "apartmentList[$(i)].noOfchildren must be a whole number from 0 to $(maxChildren)." else null,
	if (!(a.childAges is Array)) "apartmentList[$(i)].childAges must be an array of ages ([] when there are no children)."
		else if ((a.childAges filter (!inRange($, 0, 17))) != []) "apartmentList[$(i)].childAges must be whole numbers from 0 to 17."
		else if (inRange(a.noOfchildren, 0, maxChildren) and (sizeOf(a.childAges) != a.noOfchildren)) "apartmentList[$(i)].childAges must list one age per child: $(sizeOf(a.childAges)) age(s) for $(a.noOfchildren) child(ren)."
		else null,
	if (a.roomCodeSent and a.roomCode == null) "apartmentList[$(i)].roomCode must be a non-blank string." else null,
	if (a.ratePlanCodeSent and a.ratePlanCode == null) "apartmentList[$(i)].ratePlanCode must be a non-blank string." else null,
	if ((a.roomCode != null) != (a.ratePlanCode != null)) "apartmentList[$(i)] must have both roomCode and ratePlanCode, or neither." else null
]))

var errors = ([
	if (!(payload is Object)) "Request body must be a JSON object." else null,
	if (code == null) "propertyCode is required." else if (!(code matches /^[0-9]{1,20}$/)) "propertyCode must be digits only, for example \"51052\"." else null,
	if (!checkinTry.success) "checkinDate must be a date in yyyy-MM-dd format." else null,
	if (!checkoutTry.success) "checkoutDate must be a date in yyyy-MM-dd format." else null,
	if (!(checkin is Date)) null else if (checkin < today) "checkinDate cannot be in the past." else null,
	if (nights == null) null else if (nights < 1) "checkoutDate must be after checkinDate." else if (nights > maxNights) "The stay cannot be longer than $(maxNights) nights." else null,
	if (listGiven and !(body.apartmentList is Array)) "apartmentList must be an array of rooms." else null,
	if ((body.apartmentList is Array) and (sizeOf(roomsIn) != sizeOf(body.apartmentList))) "Each apartmentList entry must be an object." else null,
	if (sizeOf(rooms) < 1 or sizeOf(rooms) > maxRooms) "apartmentList must have 1 to $(maxRooms) rooms." else null,
	if (currency == null) null else if (!(currency matches /^[A-Z]{3}$/)) "currencyCode must be an ISO 4217 code such as SGD." else null,
	if ((body.voucherCode != null) and (text(body.voucherCode) == null)) "voucherCode must be a non-blank string." else null
] ++ roomErrors) filter ($ != null)

var apartmentList = rooms map ((a) -> {
	noOfadults: whole(a.noOfadults),
	noOfchildren: whole(a.noOfchildren),
	childAges: if (a.childAges is Array) (a.childAges map whole($)) else [],
	roomCode: a.roomCode,
	ratePlanCode: a.ratePlanCode
})
---
{
	errors: errors,
	request: {
		propertyCode: code,
		checkin: iso(checkin),
		checkout: iso(checkout),
		nights: nights,
		// The guests of all rooms together, for the booking search body and meta.
		adults: sum(apartmentList map (if ($.noOfadults is Number) $.noOfadults else 0)),
		children: sum(apartmentList map (if ($.noOfchildren is Number) $.noOfchildren else 0)),
		childAges: flatten(apartmentList map $.childAges),
		rooms: sizeOf(apartmentList),
		apartmentList: apartmentList,
		currency: currency,
		language: language,
		voucherCode: text(body.voucherCode),
		// get-poi-details.xml only runs when maxPois > 0; T-08 never asks for POIs.
		maxPois: 0
	}
}
