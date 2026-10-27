%dw 2.0
// T-04 structuredContent (payload, from dwl/room-rate-details.dwl) + the requested room codes (ctx.roomCodesRequest)
// + the upstream property (ctx.roomsSource) -> compare_rooms_rates (T-07) structuredContent,
// schemas/T07-compare-rooms-rates.structured-content.schema.json 0.1.0 (draft).
//
// T-07 only gathers the rooms (owner decision 2026-10-26): no recommendation, ranking or filtering beyond the codes.
// The shape is T-04's, so the same widget can draw it, with three additions:
//   meta.room_codes          the codes searched for (absent when the caller sent none: every room is returned)
//   meta.dropped_room_codes  codes past t07.maxRoomCodes, not searched
//   excluded[]               {room_code, reason} per requested code that has no room in the response:
//                            "not_found" (no such room at the property) or "no_available_rate" (the room exists but
//                            has no bookable rate for this stay). Always present; [] when nothing was excluded.
// With codes, each requested room keeps only the matching room types, in the order the codes were given.
// Without codes it is the T-04 answer unchanged (every room with a bookable rate, in ranking order).
output application/json skipNullOn="everywhere"

// ---------- PLAYGROUND SHIM (not in the deployed file)
// Copy of dwl/compare-rooms-response.dwl for https://dataweave.mulesoft.com/learn/playground.
// Input 'payload' = {t04: <room-rate-details.dwl output>, roomCodesRequest: <ctx.roomCodesRequest>,
//                    roomsSource: <propertyList[0]>} (compare-rooms-response.playground-input.json)
var ctx = payload
// ---------- END SHIM

var t04 = ctx.t04 default {}
var codes = ctx.roomCodesRequest.roomCodes default []
var dropped = ctx.roomCodesRequest.droppedRoomCodes default []
var src = ctx.roomsSource default {}

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun upperOf(v) = upper(text(v) default "")

// A room type answers a code by apartmentType (room_code) or by apartmentCategoryCode (room_category).
fun matches(r, c) = (upperOf(r.room_code) == c) or (upperOf(r.room_category) == c)
fun codeIndex(r) = ((codes map ((c, i) -> if (matches(r, c)) i else null)) filter ($ != null))[0] default 999999

var requestedRooms = objects(t04.requested_rooms) map ((rr) -> do {
	var all = objects(rr.rooms)
	var kept = if (isEmpty(codes)) all else ((all filter ((r) -> codeIndex(r) != 999999)) orderBy codeIndex($))
	---
	(rr - "total_results" - "rooms") ++ {total_results: sizeOf(kept), rooms: kept}
})

// Every room type upstream sent, whatever its room{i} key and whether or not it has a bookable rate.
var upstreamRooms = flatten(objects(src.apartments) map ((e) -> flatten((e pluck $) map ((v) -> objects(v)))))
fun atProperty(c) = !isEmpty(upstreamRooms filter ((a) -> (upperOf(a.apartmentType) == c) or (upperOf(a.apartmentCategoryCode) == c)))
fun returned(c) = !isEmpty(flatten(requestedRooms map ((rr) -> rr.rooms)) filter ((r) -> matches(r, c)))
---
{
	meta: (t04.meta default {}) ++ {
		room_codes: if (isEmpty(codes)) null else codes,
		dropped_room_codes: if (isEmpty(dropped)) null else dropped
	},
	requested_rooms: requestedRooms,
	excluded: (codes filter ((c) -> !returned(c))) map ((c) -> {
		room_code: c,
		reason: if (atProperty(c)) "no_available_rate" else "not_found"
	})
}
