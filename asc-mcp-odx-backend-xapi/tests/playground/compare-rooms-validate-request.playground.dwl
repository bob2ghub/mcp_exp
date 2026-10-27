%dw 2.0
// compare_rooms_rates (T-07) room codes: the request body (payload) -> {errors: [String], roomCodes: [String],
// droppedRoomCodes: [String]}.
//
// Only the room codes are read here. The stay, guests, currency and language are validated by the T-04 validator
// (dwl/rooms-validate-request.dwl, through multi-rooms-validate-request), which ignores roomCodes.
//
// roomCodes (or the PRD name roomCategoryCodes) is optional: absent, null or [] means every room at the property.
// Codes are matched against upstream apartmentType (T-04 room_code), else apartmentCategoryCode, ignoring case, so
// they are upper-cased here. Duplicates are removed in order; codes past t07.maxRoomCodes (default 4, PRD ER-02)
// are dropped and echoed in meta.dropped_room_codes.
output application/json

// ---------- PLAYGROUND SHIM (not in the deployed file)
// Copy of dwl/compare-rooms-validate-request.dwl for https://dataweave.mulesoft.com/learn/playground.
// Input 'payload' = the T-07 request body (compare-rooms-validate-request.playground-input.json).
fun p(key: String) = {"t07.maxRoomCodes": 4}[key]
// ---------- END SHIM

var body = if (payload is Object) payload else {}
var maxCodes = (p('t07.maxRoomCodes') default 4) as Number
var codesIn = if (body.roomCodes != null) body.roomCodes else body.roomCategoryCodes

fun code(v) = if (v is String) (if (isBlank(v)) null else upper(trim(v))) else null

var listed = if (codesIn is Array) (codesIn map code($)) else []
var distinctCodes = (listed filter ($ != null)) distinctBy $
var kept = if (sizeOf(distinctCodes) > maxCodes) distinctCodes[0 to (maxCodes - 1)] else distinctCodes
var dropped = if (sizeOf(distinctCodes) > maxCodes) distinctCodes[maxCodes to -1] else []
---
{
	errors: [
		if ((codesIn != null) and !(codesIn is Array)) "roomCodes must be an array of room codes, for example [\"0BRCT\", \"1DLXT\"]." else null,
		if ((codesIn is Array) and ((listed filter ($ == null)) != [])) "roomCodes must contain only non-blank strings." else null,
		if ((distinctCodes filter ((c) -> !(c matches /^[A-Z0-9_-]{1,40}$/))) != []) "Each room code must be 1 to 40 letters, digits, hyphens or underscores." else null
	] filter ($ != null),
	roomCodes: kept,
	droppedRoomCodes: dropped
}
