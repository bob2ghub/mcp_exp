%dw 2.0
// T-04 structuredContent (vars.roomsT04, from dwl/room-rate-details.dwl) + the T-08 request (vars.bookingRequest)
// + the upstream property (vars.roomsSource) -> {problems: [...], response: <create_booking structuredContent>}.
// Response schema: schemas/T08-create-booking.structured-content.schema.json 0.1.0 (the owner's file, 2026-10-28).
//
// One booked room per apartmentList entry i, chosen from T-04's requested_rooms[i].rooms (upstream room{i}: only room
// types with a bookable rate, in ranking order, rate_plans cheapest first; member / ACRS / TEST rates already dropped).
//   roomCode + ratePlanCode given ("selected"): the room whose room_code (else room_category) equals roomCode and its
//     rate whose rate_plan_code equals ratePlanCode, ignoring case. Missing -> problem "not_available" (ER-04).
//   neither ("cheapest", PRD AC-02 / EC-01): the rate with the lowest per-night price INCLUDING tax
//     (per_night_rate + per_night_tax, so tax-exclusive and tax-inclusive rates compare fairly) across all room types;
//     a tie goes to the better-ranked room. Nothing bookable -> problem "no_availability" (ER-02).
// Any problem makes the call an error (the flow raises it); the response is only used when problems is [].
// Add-ons are merged in by the flow (dwl/create-booking-add-ons.dwl), not here.
output application/json skipNullOn="everywhere"

// ---------- PLAYGROUND SHIM (not in the deployed file)
// Copy of dwl/create-booking-response.dwl for https://dataweave.mulesoft.com/learn/playground.
// Input 'payload' = {roomsT04: <room-rate-details.dwl output>, bookingRequest: <vars.bookingRequest>,
//                    roomsSource: <propertyList[0]>} (create-booking-response.playground-input.json)
var ctx = payload
// ---------- END SHIM

var t04 = ctx.roomsT04 default {}
var req = ctx.bookingRequest default {}
var src = ctx.roomsSource default {}

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun upperOf(v) = upper(text(v) default "")
fun money(n) = round(n * 100) / 100
fun allIn(rate) = (rate.per_night_rate default 0) + (rate.per_night_tax default 0)

var m = t04.meta default {}
var specs = objects(req.apartmentList)
var requested = objects(t04.requested_rooms)

fun roomMatches(r, c) = (upperOf(r.room_code) == upper(c)) or (upperOf(r.room_category) == upper(c))
fun rateMatches(rp, c) = upperOf(rp.rate_plan_code) == upper(c)
fun guests(rr) = "$(rr.noOfadults default 1) adult(s), $(rr.noOfchildren default 0) child(ren)"
fun codesOf(rooms) = (rooms map $.room_code) joinBy ", "

var picks = specs map ((spec, i) -> do {
	var rr = requested[i] default {}
	var available = objects(rr.rooms)
	var label = "Room $(i + 1) ($(guests(rr)))"
	var selected = (spec.roomCode != null) and (spec.ratePlanCode != null)
	var candidates = available filter roomMatches($, spec.roomCode default "")
	var hit = if (selected)
			flatten(candidates map ((r) -> (objects(r.rate_plans) filter rateMatches($, spec.ratePlanCode)) map {room: r, rate: $}))[0]
		else
			flatten(available map ((r) -> objects(r.rate_plans) map {room: r, rate: $}))
				reduce ((x, best = null) -> if ((best == null) or (allIn(x.rate) < allIn(best.rate))) x else best)
	---
	{
		index: i,
		selected: selected,
		rr: rr,
		room: hit.room,
		rate: hit.rate,
		problem: if (hit != null) null
			else if (selected) {
				room_index: i + 1,
				reason: "not_available",
				message: label ++ ": room " ++ spec.roomCode ++ " with rate " ++ spec.ratePlanCode ++ " is not available for this stay."
					++ (if (!isEmpty(candidates)) (" Rates available for " ++ spec.roomCode ++ ": " ++ (flatten(candidates map (objects($.rate_plans) map $.rate_plan_code)) joinBy ", ") ++ ".")
						else if (!isEmpty(available)) (" Room types available: " ++ codesOf(available) ++ ".")
						else " Nothing is available for this room.")
			}
			else {
				room_index: i + 1,
				reason: "no_availability",
				message: label ++ ": nothing is available for this stay."
			}
	}
})

var booked = picks filter ($.problem == null)
var rooms = booked map ((p) -> {
	room_index: p.rr.room_index default (p.index + 1),
	noOfadults: p.rr.noOfadults,
	noOfchildren: p.rr.noOfchildren,
	childAges: p.rr.childAges default [],
	room_code: p.room.room_code,
	room_name: p.room.room_name,
	banner_image_url: p.room.banner_image_url,
	rate: p.rate
})
var selectedCount = sizeOf(picks filter $.selected)
var points = sum(rooms map ($.rate.earn_asr_points default 0))
---
{
	problems: (picks filter ($.problem != null)) map $.problem,
	response: {
		meta: {
			property_code: text(req.propertyCode) default m.property_code,
			property_name: m.property_name,
			brand_code: m.brand_code,
			country_code: m.country_code,
			asset_base_url: m.asset_base_url,
			address: text(src.address),
			banner_image_url: text(src.bannerImageMobile),
			checkin_date: m.checkin_date,
			checkout_date: m.checkout_date,
			noOfRooms: sizeOf(rooms),
			noOfadults: sum(rooms map ($.noOfadults default 0)),
			noOfchildren: sum(rooms map ($.noOfchildren default 0)),
			currency: m.currency,
			resolution: if (selectedCount == sizeOf(picks)) "selected" else if (selectedCount == 0) "cheapest" else "mixed",
			// "Rooms total": every room's whole stay including taxes, so the model never adds prices itself.
			total_stay_price: money(sum(rooms map (($.rate.total_stay_rate default 0) + (if ($.rate.is_tax_inclusive default false) 0 else ($.rate.total_tax default 0))))),
			total_earn_asr_points: if (points > 0) points else null,
			voucher_code_valid: m.voucher_code_valid
		},
		rooms: rooms
	}
}
