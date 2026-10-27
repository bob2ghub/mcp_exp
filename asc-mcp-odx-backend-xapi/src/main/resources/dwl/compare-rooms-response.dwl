%dw 2.0
// T-04 structuredContent (vars.roomsT04, from dwl/room-rate-details.dwl) + the requested room codes
// (vars.roomCodesRequest) -> compare_rooms_rates (T-07) structuredContent,
// schemas/T07-compare-rooms-rates.structured-content.schema.json 0.4.0 (the owner's file, 2026-10-28).
//
// {meta, rooms[], excluded[]}: one stay, one room's guests, 2 to 4 room types side by side. Each room is the T-04 `room`
// object unchanged (same fields, bookable rate_plans cheapest first), taken from requested_rooms[0].rooms, which holds
// only room types with a bookable rate, in ranking order.
//   With roomCodes: one room per code, in the order of the codes. A code matches apartmentType (room_code), else
//     apartmentCategoryCode (room_category), ignoring case; the first match not already picked wins. A code with no
//     match is excluded as "not_available" (no such room, or no bookable rate: upstream cannot tell them apart).
//   Without roomCodes: the first four room types; the rest are excluded as "over_limit" with their own room_code.
// excluded is left out when empty. Fewer than two rooms is an error, raised by the flow (get-room-rates.xml).
output application/json skipNullOn="everywhere"

var t04 = vars.roomsT04 default {}
var codes = vars.roomCodesRequest.roomCodes default []

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun upperOf(v) = upper(text(v) default "")

var m = t04.meta default {}
// T-07 compares one room's guests: the validator refuses more than one requested room.
var requested = objects(t04.requested_rooms)[0] default {}
var available = objects(requested.rooms)

fun matches(r, c) = (upperOf(r.room_code) == upper(c)) or (upperOf(r.room_category) == upper(c))

var picks = codes reduce ((c, acc = []) -> do {
	var taken = (acc filter ($.room != null)) map $.room.room_code
	var hit = (available filter ((r) -> matches(r, c) and !(taken contains r.room_code)))[0]
	---
	acc + {code: c, room: hit}
})

var rooms = if (isEmpty(codes)) (available filter ((r, i) -> i < 4))
	else ((picks filter ($.room != null)) map $.room)

var excluded = if (isEmpty(codes))
		((available filter ((r, i) -> i >= 4)) map {room_code: $.room_code, reason: "over_limit"})
	else ((picks filter ($.room == null)) map {room_code: $.code, reason: "not_available"})
---
{
	meta: {
		property_code: m.property_code,
		property_name: m.property_name,
		brand_code: m.brand_code,
		country_code: m.country_code,
		asset_base_url: m.asset_base_url,
		total_results: sizeOf(rooms),
		currency: m.currency,
		checkin_date: m.checkin_date,
		checkout_date: m.checkout_date,
		noOfadults: requested.noOfadults default m.noOfadults,
		noOfchildren: requested.noOfchildren default m.noOfchildren,
		childAges: requested.childAges default [],
		price_includes_tax: m.price_includes_tax
	},
	rooms: rooms,
	excluded: if (isEmpty(excluded)) null else excluded
}
