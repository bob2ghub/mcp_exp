%dw 2.0
// compare_rooms_rates (T-07) room codes: the request body (payload) -> {errors: [String], roomCodes: [String]}.
//
// Only the room codes are read here. The stay, guests, currency and language are validated by the T-04 validator
// (dwl/rooms-validate-request.dwl, through multi-rooms-validate-request), which ignores roomCodes.
//
// roomCodes (or the PRD name roomCategoryCodes) is optional: absent, null or [] means the property's first four room
// types (schema 0.4.0, decision 8). When sent it must name 2 to 4 distinct room types (schema: 2 to 4 rooms; PRD ER-01,
// ER-02). Codes are kept as the caller wrote them (trimmed), since excluded[].room_code echoes them "as requested";
// duplicates are removed ignoring case. They are matched against upstream apartmentType (T-04 room_code), else
// apartmentCategoryCode, ignoring case, in dwl/compare-rooms-response.dwl.
output application/java

var body = if (payload is Object) payload else {}
var codesIn = if (body.roomCodes != null) body.roomCodes else body.roomCategoryCodes

fun code(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else null

var listed = if (codesIn is Array) (codesIn map code($)) else []
var distinctCodes = (listed filter ($ != null)) distinctBy upper($)
---
{
	errors: [
		if ((codesIn != null) and !(codesIn is Array)) "roomCodes must be an array of room codes, for example [\"0BRCT\", \"1DLXT\"]." else null,
		if ((codesIn is Array) and ((listed filter ($ == null)) != [])) "roomCodes must contain only non-blank strings." else null,
		if ((distinctCodes filter ((c) -> !(c matches /^[A-Za-z0-9_-]{1,40}$/))) != []) "Each room code must be 1 to 40 letters, digits, hyphens or underscores." else null,
		if (isEmpty(distinctCodes) or (sizeOf(distinctCodes) >= 2 and sizeOf(distinctCodes) <= 4)) null
			else "roomCodes must name 2 to 4 different room types (it names $(sizeOf(distinctCodes))); omit it to compare the property's first four."
	] filter ($ != null),
	roomCodes: distinctCodes
}
