PRD — MCP Tool Call Specification  │  T-07  │  Compare_rooms_rates	Ascott International  ·  DRAFT

Tool Call Detailing Master Sheet
Product Requirements Document  ·  MCP AI Integration  ·  Ascott International
Document version: 1.0  ·  Date: 08 September 2026  ·  Status: DRAFT FOR REVIEW

TOOL TABLE  —  All Tool Calls in Scope
ID	Tool Call Name	One-Line Purpose	Type
T-01	Find_properties	See multiple property options	Read
T-02	Get_property_details	Get full details for a specific property	Read
T-03	Get_service_offerings	See bookable and orderable services at a property	Read
T-04	Get_room_rate_details	See rooms and rates at a specific property	Read
T-05	Get_promotions	Find applicable promotions for a stay	Read
T-06	Compare_properties	Compare two or more properties side by side	Read
T-07	Compare_rooms_rates	Compare rooms and rates within a property	Read
T-08	Create_booking	Book a selected room and rate	Read

UC-07  │  Compare Two or More Rooms & Rates Within a Property     Tool Call: Compare_rooms_rates  ·  Type: READ  ·  API Coverage: HIGH

1.  INTENT & USER CONTEXT
Overall User Objective	As a user, I want to compare two or more room types within a property side by side — across price, configuration, floor, view, and amenities — together with a single recommended pick and plain-language reasons for it, so that I can select the room that best fits my needs without holding details in memory or navigating between individual room pages.

1.1  VARIATION IN USER OBJECTIVES
User Story	Parameters the LLM passes (see input schema)
By room type, generally
As a user, I want to compare two or more room types I have already identified at a property[LS1.1][RL1.2][1.3], so that I can see them side by side on the same set of attributes.	propertyCode (required)
roomCategoryCodes (required, array, minimum 2, maximum 4)
By dates and number of guests
As a user, I want to compare rooms for a stated date range and guest count, so that the price and availability shown for each room is directly comparable.	propertyCode (required)
roomCategoryCodes (required)
checkinDate (optional — carried from T-04 context if present, else default)
checkoutDate (optional — carried from T-04 context if present, else default)
noOfadults (optional, default 1)
noOfchildren (optional, default 0)
By price
As a user, I want to remove a named room from the comparison if its rate is above my stated ceiling, so that I only compare rooms within my budget.	propertyCode (required)
roomCategoryCodes (required)
currencyCode (optional)
minPrice (optional)
maxPrice (optional)
By configuration (bed type, occupancy, room size)
As a user, I want to compare rooms on their physical configuration, so that I can weigh space and sleeping arrangements alongside price.	propertyCode (required)
roomCategoryCodes (required)
(bed type, occupancy, and room size are always-on comparison fields, not a filter — see Section 2)[LS2.1][RL2.2]
By amenities and inclusions (for example, breakfast, Wi-Fi, bathtub, balcony)
As a user, I want to remove a named room from the comparison if it does not include something I need, so that I only compare rooms that actually meet my needs.	propertyCode (required)
roomCategoryCodes (required)
requiredInclusions (array, optional — API GAP, see Section 5)
By loyalty value (points earn rate, redemption cost)
As a user, I want to compare rooms on ASR points earned or the points needed to redeem them, so that I can factor loyalty value into my choice.	propertyCode (required)
roomCategoryCodes (required)
memberId (optional — auth param, required to show points earn / redeem values)
By specific attributes (floor, view, cancellation policy)
As a user, I want to compare rooms on a stated attribute not already shown by default, so that I can weigh a specific preference that matters to me. No confirmed API accepts these as an input filter — this is a confirmed API GAP, consistent with the pattern already logged in T-04.	propertyCode (required)
roomCategoryCodes (required)
attributeToCompare (free text, optional — API GAP, not passed to any confirmed API)

1.2  KEY FINDINGS FROM USER RESEARCH
Insight	Detail
A single best answer beats a raw comparison	Users want to be told which room is the best fit for their stated need, not left to read every card unaided when evaluating more than two options. A ranked recommendation must sit above the comparison cards, not replace them, consistent with the pattern already established in T-05 (Get_promotions) and T-06 (Compare_properties).
Users need the "why", not just the "what"	Trust in a recommendation depends on visible, specific reasons (for example, the lowest rate, the largest room, or a matching inclusion), grounded in real data returned for that room. A generic "recommended" label with no stated basis is not sufficient.[LS3.1][RL3.2]
Side-by-side room cards reduce memory load	Users want a structured, side-by-side comparison of room types so they do not need to hold configuration and price details in memory while weighing their options.
A comparison table matters when evaluating more than two rooms	When evaluating more than two options, users expressed a preference for a summary table that clearly demonstrates the differences between rooms on key attributes, in addition to the individual cards, consistent with the pattern already established in T-06.
Amenity and inclusion icons carry weight for attributes photos cannot show	For high-importance room attributes that are not visually discernible from images (for example, whether parking is included), users scan the attribute highlight icons directly, rather than the photos, to confirm what is and is not included.
Without this tool call, comparison requires navigating between individual room pages	Users would otherwise need to open each room's own page in turn to compare it against another, and rate differences between room types would not be immediately visible alongside what each room actually includes for the premium paid.
Every card in the comparison must show the same fields	Users notice when one room's card is missing a data point that another card shows. Where a data element cannot be confirmed for a given room, this must be shown consistently as a missing or unavailable state, not silently dropped from that one card.[LS4.1][RL4.2]
Stacked filters can remove a named room entirely	Users may state a filter (for example, a price ceiling or a required inclusion[LS5.1]) that a named room does not meet. Removing that room from the comparison, with a clear stated reason, is an acceptable and expected outcome, not a failure state.
This tool call always operates on two or more already-identified rooms at one already-identified property	A minimum of two room types must be resolved at a single, already-identified property, either carried from an earlier T-04 (Get_room_rate_details) result already in context, or named directly by the user, before this tool call can be invoked. Unlike T-06, which compares across properties, T-07 never compares rooms across more than one property in the same call.[LS6.1][RL6.2]

2.  UI COMPONENT & FRONT END BEHAVIOURS TO SUPPORT
Overview	T-07 renders through a single inline component shown directly in the chat. There is no full screen component for this tool call. The system must return one data packet large enough to populate the recommendation block and every room card in the row, without a second call. Neither user action available within this component opens a deeper T-07-specific view: both the expand icon and the "View available rates" button hand off directly to T-04 (Get_room_rate_details) for that specific room, since T-07 shows only a single starting rate per room and does not itself expose the full rate-plan list. LLM-authored prose appears only around the returned component, never inside it. No user action described in this section triggers a repeat call to T-07.

2.1  INLINE COMPONENT
Element	Detail
Shared header	Source attribution: the asr logo icon and the "ASR" label.
Recommendation block	A star icon with the heading "Our recommendation!". One sentence naming the recommended room and, inline within that sentence, a tag chip stating the traveller need or profile the recommendation is matched to (for example, "Business traveller"), shown only when the LLM can infer one from the user's stated need. A "Why it stands out" subheading, followed by a vertical list of reason lines, each with an icon and a short phrase (for example, "Comfortable king-size bed", "Dedicated workspace", "High-speed Wi-Fi", "More affordable nightly rate"). Each reason line is shown only when its underlying match flag is true; a reason is never shown for a condition that was not actually met.
"How the rooms compare" section heading	A text heading introducing the room card row below.
Room card row	A row of room cards, one per compared room (2 to 4 cards). Unlike T-06, no card carries a "recommended" tag chip; the recommendation is conveyed only through the recommendation block above, not on the card itself. Each card shows: a hero image with an expand icon in the top-right corner and a brand logo watermark centred at the base of the image, a dark footer band containing the room name, a guest-capacity icon and label (for example, "Max 2 pax"), and a room-size icon and label (for example, "17 sqm / 183 sqft"), the starting nightly rate ("from [rate] / night"), and a "View available rates" button.
"Deciding Criteria" block (per card)	Below each card's dark footer band, on the white background: a "Deciding Criteria:" label, followed by a fixed set of comparison rows, each with an icon, a label, and a value — Bed Type, Workspace, Wi-Fi, and Cancellation. The same criteria set appears under every card in the row, so values can be read straight across.
Below the component	LLM-authored prose (for example, a short elaboration on the recommended room, and a follow-up question).

2.2  USER ACTIONS & SYSTEM BEHAVIOUR
User Action	System Response	Tool Call Triggered
Tap the expand icon on a room card	Hands off to T-04 (Get_room_rate_details), with that room pre-selected.	T-04  Get_room_rate_details
Tap "View available rates" on a room card	Hands off to T-04 (Get_room_rate_details), with that room pre-selected, to view the full list of rate plans for that room.	T-04  Get_room_rate_details

Note	There is no "Book" action within T-07. Both available actions hand off to T-04; a room and rate can only be selected and booked from within T-04's own component.

2.3  DATA PACKAGE MENTAL MODEL
Principle	T-07 must return one data packet that is large enough to fully populate the recommendation block and every room card, including its "Deciding Criteria" rows, without a second call. Because only a single starting rate is shown per room, and full rate-plan detail is deferred to T-04, the data packet does not need to carry the multi-rate-plan structure that T-04 itself returns.

Field Group	Fields Required
Search context (once per response)	Resolved property name / property code. Result count (number of rooms compared). Applied filters echoed back (dates, guests, price ceiling, required inclusions). Attribution / source platform label.
Recommendation fields (once per response)	Recommended room identifier. Inferred traveller-need or profile label (for example, "Business traveller"), where the LLM can infer one from the user's stated criteria. Recommendation sentence (generated by a narrow backend explanation service, grounded in the match flags below — see Section 4). Match flags (for example, matchesStatedBedType, hasStatedWorkspace, isLowestRate). Reason line icon / label pairs, one per true match flag.
Per-room card fields	Room ID / code and room name. Hero image, with brand logo watermark. Guest capacity (max pax). Room size (dimension). Starting / lead-in nightly rate, in one response-level currency.
Deciding Criteria fields (per room)[LS7.1][RL7.2]	Selected dynamically every time the tool is invoked. For example: Bed type. Workspace presence (derived from room amenity data). Wi-Fi presence (derived from room amenity data). Cancellation policy, condensed to a short label (for example, "Free cancellation").

Currency parameter note	Every room card in a single response must display the same resolved currency. currencyCode is a first-class optional input parameter; if the user does not state a currency, the system defaults to the currency associated with the user's region, consistent with the T-01 / T-06 currency normalisation principle.

3.  TOOL CALL GUIDELINES
Tool call description	Return a side-by-side comparison of two to four named or previously identified room types at a single, already-identified Ascott property, together with a single ranked recommendation and plain-language reasoning grounded in the user's stated criteria, so the result can be rendered inline without a follow-up call.
When to use	Use when the user has two or more room types at one property already in mind, whether named directly or carried from an earlier T-04 (Get_room_rate_details) result, and wants to weigh them against each other.
When NOT to use	Do not use to discover room options at a property for the first time; refer to T-04 (Get_room_rate_details) first. Do not use to compare across more than one property; refer to T-06 (Compare_properties). Do not use to view the full list of rate plans for a single room, or to complete a booking; refer to T-04 and T-08 (Create_booking) respectively.
LLM instruction note	The LLM must resolve one propertyCode and at least two, and no more than four, roomCategoryCodes before invoking this tool call, either carried from an earlier T-04 result already in context or stated directly by the user. Where the user states a filter that would exclude a named room (price ceiling, required inclusion), the LLM passes all stated filters together in a single call, and the response indicates which named rooms were excluded and why. The LLM must not fabricate a reason line or recommendation sentence beyond what the returned match flags support, consistent with the pattern in T-05 and T-06.

3.1  ADJACENT BEHAVIOURS (AND THE TOOL THEY BELONG TO)
Adjacent behaviour (potential overlapping use case)	Appropriate tool chain
User is still browsing rooms at a property and has not identified two or more rooms to compare yet.	Invoke T-04 (Get_room_rate_details) first. T-07 is not invoked with fewer than two resolved room types.
User compares rooms and then taps the expand icon or "View available rates" on a card.	Invoke T-04 (Get_room_rate_details) for that room, carrying forward any dates and guest count already stated in the T-07 call. This is the only path to viewing that room's full rate-plan list.
User compares rooms and then wants to book a room.	T-07 has no booking action of its own. The user must first hand off to T-04 (via the expand icon or "View available rates"), then invoke T-08 (Create_booking) from within T-04's own "Book" / "Book now" actions once a specific rate plan is selected.
User compares rooms and then wants to compare a different property altogether.	Refer to T-06 (Compare_properties). T-07 never compares rooms across more than one property in the same call.
User asks about promotions or discounts applicable to one of the compared rooms.	Refer to T-05 (Get_promotions), carrying the propertyCode forward. This is a distinct tool call from T-07 and is not triggered automatically by any action within this component.

4.  DATA & API CONTRACTS
Coverage status	HIGH. Per-room card data and the "Deciding Criteria" fields all map to confirmed fields already established for T-04 (apartmentlist, apartmentratedetails – V3). The cross-referencing scoring layer that produces the single ranked recommendation, and its plain-language explanation, is the same new backend capability already logged against T-05 (Get_promotions) and T-06 (Compare_properties).

API no.	API name	Primary role in this tool call
1	apartmentlist	Per-room source for room type name, bed type, maximum occupancy, room size, and a starting rate summary. Called once for the resolved propertyCode, then filtered to the stated roomCategoryCodes.
2	apartmentratedetails – V3	Primary source for the starting nightly rate and currency, per-room amenity data (amenityGroups) used to derive the Workspace and Wi-Fi rows, and the cancellation policy text used to derive the Cancellation row.
3	pricedistribution	Supplemental source, consistent with its confirmed limited role in T-04, for a fully itemised tax / fee breakdown where required to support the starting-rate display.
4	Backend scoring & explanation service — NEW, no confirmed existing API	Computes structured match flags across the resolved rooms against the user's stated criteria, ranks the single best-fit room, and issues a narrow, non-conversational backend LLM call restricted to phrasing the recommendation sentence and reason lines from those match flags only. Same new backend capability logged against T-05 and T-06. See Open Question OQ-01.

5.  INPUT PARAMETERS — LLM-to-API SCHEMA
Input parameter (layman label)	Actual API parameter name	Type	Required / Optional	Assumed value when not provided	Constraints	Example
Property identifier	propertyCode	String	Required	—	Resolved by the LLM from a prior T-04 result already in context, or from a property name stated directly in the user's prompt.	"50926"
Room types to compare	roomCategoryCodes	Array of String	Required	—	Minimum 2, maximum 4. Resolved by the LLM from a prior T-04 result already in context, or from room names stated directly in the user's prompt.	["CUTLER-STUDIO", "COLLYER-1BR"]
Check-in date	checkinDate	String	Optional	Carried from T-04 context if present; otherwise 30 days from current date	Must be today or a future date. Must be before checkoutDate. Applied identically to every room in the comparison.	"2027-05-04"
Check-out date	checkoutDate	String	Optional	Carried from context if present; otherwise 31 days from current date	Must be after checkinDate.	"2027-05-13"
Guest count (adults)	noOfadults	String	Optional	Carried from context if present; otherwise 1	Applied identically to every room in the comparison.	"1"
Guest count (children)	noOfchildren	String	Optional	Carried from context if present; otherwise 0	—	"0"
Currency code	currencyCode	String	Optional	Currency associated with the user's region	Every card in a single response must display this one currency, consistent with T-01 / T-06.	"SGD"
Minimum nightly price	minPrice	String	Optional	—	Confirmed request parameter in apartmentratedetails – V3, consistent with T-04.	"100"
Maximum nightly price	maxPrice	String	Optional	—	Confirmed request parameter in apartmentratedetails – V3. A named room above this ceiling is excluded from the comparison.	"250"
Required inclusions	requiredInclusions — PARAMETER GAP	Array of String	Optional	—	No confirmed request-side parameter accepts a required-inclusions filter. The backend service layer must check the returned amenity list and exclude a named room lacking a stated inclusion. See Open Question OQ-05.	["Breakfast"]
Specific attribute to compare	attributeToCompare — API GAP	String	Optional	—	No confirmed request-side filter exists for attributes such as floor or view, consistent with T-04's OQ-03. The LLM can only note which returned rooms appear, from description or amenity data, to match the stated attribute.	"high floor"
Member ID	memberId	String	Optional (auth param)	—	Required to display member rates and ASR points earn / redeem values where relevant to the comparison.	"M123456"

6.  OUTPUT PARAMETERS — API-to-UI RESPONSE SCHEMA
Note	Lead with the common-sense UI requirements based on the data package mental model in Section 2.3, then map to the correct API response parameter names. Fields marked API GAP or PARAMETER GAP have no existing confirmed API response parameter.

Expected UI element	Actual response parameter name	Type	Assumed API source	Example value
Resolved property, result count, applied filters, attribution	meta (Object)	Object	Backend-composed from the request	"Comparing 2 rooms at Ascott Raffles Place"
Recommended room identifier	recommendedRoomCode	String	Backend scoring service (NEW)	"CUTLER-STUDIO"
Inferred traveller-need label (inline chip)	travellerProfileLabel	String	Backend scoring service (NEW, derived from LLM-passed travellerProfile)	"Business traveller"
Recommendation sentence	recommendationText	String	Backend explanation service (NEW — narrow LLM call, grounded in matchFlags)	"The Cutler Suite Studio is the better choice for a solo Business traveller."
Match flags	matchFlags → matchesStatedBedType, hasStatedWorkspace, hasStatedWifi, isLowestRate	Object	Backend scoring service (NEW)	true, true, true, true
Reason lines ("Why it stands out")	reasonLines[] → icon, label	Array of Object	Backend-composed (templated from matchFlags)	"🛏️", "Comfortable king-size bed"
Room code	apartmentCategoryCode	String	apartmentratedetails – V3, apartmentlist	"CUTLER-STUDIO"
Room name	apartmentName / apartmentType	String	apartmentratedetails – V3, apartmentlist	"Cutler Suite Studio"
Hero image / brand watermark	bannerImageMobile, brandlogo	String (URL)	apartmentratedetails – V3, apartmentlist	[relative paths]
Guest capacity ("Max 2 pax")	maxPersonInRoom	String	apartmentratedetails – V3, apartmentlist	2
Room size ("17 sqm / 183 sqft")	dimension	String	apartmentratedetails – V3	"17 sqm / 183 sqft"
Starting nightly rate	perNightRatePrefCurr	String (Decimal)	apartmentratedetails – V3, apartmentlist	175.00
Currency code	currency	String	apartmentratedetails – V3, apartmentlist	"SGD"
Deciding Criteria — Bed Type	bedType	String	apartmentlist, apartmentratedetails – V3	"Twins or Queen bed"
Deciding Criteria — Workspace	amenityGroups → amenities[] → description (backend-derived presence check)	String (Yes/No or short label)	apartmentratedetails – V3 (derivation logic to confirm — see OQ-02)	"Dedicated desk"
Deciding Criteria — Wi-Fi	amenityGroups → amenities[] → description (backend-derived presence check)	String (Yes/No)	apartmentratedetails – V3 (derivation logic to confirm — see OQ-03)	"Yes"
Deciding Criteria — Cancellation	cancellationDescription, nonRefundable (condensed to a short label)	String	apartmentratedetails – V3 (condensation logic to confirm — see OQ-04)	"Free cancellation"
Recommended flag (for grounding / QA, not rendered as a badge in this tool call's UI)	isRecommended	Bool	Backend-composed (true only for recommendedRoomCode)	true

6.1  ILLUSTRATIVE DATA PACKET — CANONICAL OUTPUT
{
  "meta": {
    "property_code": "50926",
    "property_name": "Ascott Raffles Place",
    "total_results": 2,
    "checkin_date": "2027-05-04",
    "checkout_date": "2027-05-13",
    "noOfadults": 1,
    "noOfchildren": 0,
    "currency": "SGD",
    "attribution": "ASR"
  },
  "recommendation": {
    "recommended_room_code": "CUTLER-STUDIO",
    "traveller_profile_label": "Business traveller",
    "recommendation_text": "The Cutler Suite Studio is the better choice for a solo Business traveller.",
    "match_flags": {
      "matches_stated_bed_type": true,
      "has_stated_workspace": true,
      "has_stated_wifi": true,
      "is_lowest_rate": true
    },
    "reason_lines": [
      { "icon": "🛏️", "label": "Comfortable king-size bed" },
      { "icon": "💻", "label": "Dedicated workspace" },
      { "icon": "📶", "label": "High-speed Wi-Fi" },
      { "icon": "💰", "label": "More affordable nightly rate" }
    ]
  },
  "rooms": [
    {
      "apartment_category_code": "CUTLER-STUDIO",
      "apartment_name": "Cutler Suite Studio",
      "is_recommended": true,
      "banner_image_url": ".../cutler-suite-studio/banner.jpg",
      "brand_logo_url": ".../logo-ascott-en.png",
      "max_person_in_room": 2,
      "dimension": "17 sqm / 183 sqft",
      "per_night_rate_pref_curr": 175.00,
      "currency": "SGD",
      "deciding_criteria": {
        "bed_type": "Twins or Queen bed",
        "workspace": "Dedicated desk",
        "wifi": "Yes",
        "cancellation": "Free cancellation"
      }
    },
    {
      "apartment_category_code": "COLLYER-1BR",
      "apartment_name": "One-Bedroom Collyer Suite",
      "is_recommended": false,
      "banner_image_url": ".../one-bedroom-collyer-suite/banner.jpg",
      "brand_logo_url": ".../logo-ascott-en.png",
      "max_person_in_room": 2,
      "dimension": "17 sqm / 183 sqft",
      "per_night_rate_pref_curr": 175.00,
      "currency": "SGD",
      "deciding_criteria": {
        "bed_type": "Twins or Queen bed",
        "workspace": "Dedicated desk",
        "wifi": "Yes",
        "cancellation": "Free cancellation"
      }
    }
  ]
}

7.  ERROR CONDITIONS & FALLBACK BEHAVIOUR
No.	Error condition	LLM fallback response (illustrative)
ER-01	Fewer than two room types can be resolved at the property.	I need at least two room types to compare. Could you name a second room, or would you like me to show all the rooms available at this property first?
ER-02	The user names more than four room types for comparison.	I can compare up to four rooms at a time. I have compared the first four you named — would you like me to swap in a different one?
ER-03	The API is unavailable or returns a 5xx error.	I am having trouble retrieving room details right now. Could you try again in a moment? You can also compare rooms directly at discoverasr.com.
ER-04	One or more of the user's stated room names cannot be resolved to a valid roomCategoryCode at this property.	I was not able to confirm one of the rooms you named at this property. Could you check the room name, or would you like me to show all the rooms available here?
ER-05	Stated filters (price ceiling, required inclusions) reduce the comparison set below two rooms.	After applying your filters, fewer than two rooms are left to compare at this property. Would you like me to relax one of the filters?
ER-06	Member ID is absent when the user requests member rates or ASR points display.	To show member rates and points, I need you to be signed in to your ASR account. Would you like to sign in, or shall I compare standard rates instead?
ER-07	A room has no available rate for the stated dates.	The room is shown with an "Availability on request" label instead of a starting rate. The LLM does not fabricate a rate.
ER-08	The user asks to book a room directly from the comparison view.	I can't book directly from this comparison — let's pull up the full rates for [room name] first, then I can help you book from there. (The LLM invokes T-04 for that room rather than attempting T-08 directly.)

8.  ACCEPTANCE CRITERIA
AC-01 Happy path	GIVEN a user specifies two to four valid room types at one property, WHEN the Compare_rooms_rates tool call is invoked, THEN the system returns a recommendation and a room card, with Deciding Criteria, for each room, renderable in the inline component.
AC-02 With filters	GIVEN a user specifies one or more optional filters (price, required inclusions), WHEN the tool call is invoked, THEN any named room failing a stated filter is excluded from the comparison, with the reason communicated to the user.
AC-03 Minimum enforced	GIVEN fewer than two room types can be resolved at the property, WHEN the LLM processes the request, THEN the tool call is NOT invoked until a second room is resolved.
AC-04 Maximum enforced	GIVEN a user names more than four room types, WHEN the tool call is invoked, THEN the comparison is limited to four rooms and the user is told which were included.
AC-05 Recommendation grounding	GIVEN the tool call returns a recommendation, WHEN recommendationText and reasonLines are generated, THEN every reason stated is backed by a true value in matchFlags for that room, and no reason is presented for a condition that was not actually met.
AC-06 Single recommended room	GIVEN two or more rooms are returned, WHEN the response is composed, THEN exactly one room is marked isRecommended = true and corresponds to recommendedRoomCode, even though no badge is rendered on the card itself.
AC-07 Currency normalisation	GIVEN a comparison set spanning rooms with different rate currencies, WHEN the response is composed, THEN every room card displays the one resolved currencyCode.
AC-08 Client-side re-render	GIVEN a result set has already been returned, WHEN the user views or scrolls the returned room cards, THEN no additional call to T-07 is made.
AC-09 T-04 handoff (both actions)	GIVEN a user taps the expand icon or "View available rates" on a room card, WHEN the action is triggered, THEN T-04 (Get_room_rate_details) is invoked with the correct propertyCode and roomCategoryCode, and any dates and guest count already stated in the T-07 call are carried forward.
AC-10 No booking action	GIVEN the returned inline component, WHEN rendered, THEN no button or action within it invokes T-08 (Create_booking) directly; a room and rate can only be selected and booked after handing off to T-04.
AC-11 No fabricated data	GIVEN the room data or the recommendation service is unavailable, WHEN Compare_rooms_rates is attempted, THEN the LLM surfaces the applicable error condition and does not return invented room or recommendation data.

9.  SIDE EFFECTS
Tool call type	READ-ONLY. This tool call does not create, update, or delete any data, and does not itself complete a reservation. It is safe to invoke multiple times with the same parameters.
Reversibility	Not applicable. This tool call has no side effects to reverse.
Authentication	Authentication is not required for a basic comparison. When memberId is present, member rates and ASR points relevant to the comparison are reflected in the response.
Performance note	The base orchestration calls apartmentlist and apartmentratedetails – V3 once per compared room (a 2x to 4x fan-out relative to a single-room lookup), followed by the backend scoring service and one narrow backend LLM call to produce the recommendation sentence and reason lines. pricedistribution is called only where a fully itemised tax / fee breakdown is required. This adds latency relative to a single-room lookup and should be measured against the agreed SLA — see Open Question OQ-01.
Limitations	The recommendation and its explanation depend on a new backend capability not present in any existing Ascott API. The derivation logic for the Workspace, Wi-Fi, and Cancellation rows from underlying amenity and policy data requires confirmation (see Open Questions OQ-02 through OQ-04). Required-inclusions filtering and specific-attribute comparisons (floor, view) have no request-side parameter and are confirmed gaps, consistent with T-04.

10.  EDGE CASES
ID	Condition	System response
EC-01	The user names the same room type twice.	The duplicate is removed before invoking the tool call; the comparison proceeds with the remaining distinct rooms.
EC-02	The user names five or more room types.	The tool call compares the first four named rooms. The LLM tells the user which rooms were included and offers to swap one in or out.
EC-03	A named room type does not exist at the resolved property.	That room is excluded from the comparison. The LLM confirms which room names could not be found and offers to show all rooms at the property.
EC-04	Stated filters leave only one comparable room.	The LLM does not render a one-room "comparison". It tells the user only one room meets the stated criteria and hands off to T-04 for that room instead.
EC-05	Two rooms tie on the match flags used for the recommendation.	The backend scoring service applies a defined tie-break (for example, lowest rate, then largest room size) so exactly one room is identified as the recommendation basis, consistent with the tie-break pattern used in T-05 and T-06.
EC-06	A room has no available rate for the stated dates.	The card shows an "Availability on request" label instead of a starting rate. The LLM does not fabricate a rate, consistent with T-04's equivalent handling.
EC-07	A room's rate is returned in a currency other than the response-level currencyCode.	The backend service layer converts the rate field to the one resolved currency before the card is returned.
EC-08	The user states no particular travel need or profile (for example, asks only "compare these two rooms").	The recommendation sentence and inline profile chip are omitted. The reason lines and recommendation are instead grounded in objective match flags (for example, rate, room size) rather than an inferred traveller need.
EC-09	A room's hero image is unavailable.	The card renders with the room name and details but without the hero image. An appropriate placeholder is shown. The LLM does not fabricate an image.
EC-10	A Deciding Criteria value cannot be confirmed for one room (for example, no workspace amenity entry is present in that room's data).	The affected card shows that row as "Not specified" rather than omitting it, so every card keeps the same four-row layout.
EC-11	The user attempts to book a room directly from the comparison view (for example, "book the Cutler Suite Studio").	The LLM does not invoke T-08 directly. It invokes T-04 for that room first, consistent with Section 3.1, and proceeds toward booking from within T-04's own component.

11.  SUCCESS METRICS
ID	Metric	Verification method
SM-01	The tool call is invoked only when one propertyCode and at least two valid roomCategoryCodes are resolved.	QA test: verify the tool call is not fired with fewer than two resolved rooms, or without a resolved property.
SM-02	Exactly one room per response is identified as the recommendation basis, and every stated reason is backed by a true match flag.	Manual review and automated check: assert reasonLines never reference a matchFlag that is false for the recommended room.
SM-03	Every room card in a single response displays one consistent currency.	UI regression test: assert no response contains more than one currency code across its rooms.
SM-04	Rooms failing a stated filter are correctly excluded, with a reason communicated to the user.	Integration test: compare filter inputs against the returned and excluded room sets across a representative test set.
SM-05	Both the expand icon and "View available rates" correctly fire T-04 with the right propertyCode, roomCategoryCode, and carried-forward stay context.	Integration test: verify T-04 receives the correct identifiers and stay context from the active T-07 packet, not re-resolved values.
SM-06	No T-08 (Create_booking) call ever originates directly from T-07.	Code review and integration test: confirm no code path in the T-07 component invokes T-08 without first passing through T-04.
SM-07	Error conditions ER-01 through ER-08 produce the correct fallback response and no fabricated data.	Test suite: simulate each error condition and assert the correct fallback message.
SM-08	The backend scoring and explanation service does not push end-to-end response time beyond the agreed SLA.	Performance test: measure response time for the scoring step and the explanation LLM call separately, and combined, across a 2-room and a 4-room comparison.

12.  OPEN QUESTIONS
ID	Question	Owner	Status
OQ-01	What is the confirmed architecture, ownership, and latency budget for the backend scoring and explanation service at the room level, and how is the LLM-derived travellerProfile weighted into the match-flag scoring? Same governance question already logged against T-05 and T-06.	Integration Architect / Product	Open — new backend capability, scope and performance risk
OQ-02	What is the confirmed source and keyword/taxonomy logic for deriving the "Workspace" Deciding Criteria row from amenityGroups? Which facility description(s) count as a qualifying workspace entry?	API Owner	Open — confirmed field-derivation gap
OQ-03	What is the confirmed source and keyword/taxonomy logic for deriving the "Wi-Fi" Yes/No Deciding Criteria row from amenityGroups?	API Owner	Open — confirmed field-derivation gap
OQ-04	What is the confirmed condensation logic for the "Cancellation" Deciding Criteria row — what short labels (for example, "Free cancellation", "Non-refundable") map to which combinations of cancellationDescription and nonRefundable?	API Owner / Product	Open — confirmed field-derivation gap
OQ-05	Is there a confirmed request-side parameter for requiredInclusions, or must this remain backend-side filtering against the amenity list, consistent with T-04's own confirmed PARAMETER GAPs for room attribute and rate-plan-type filters?	Integration Architect	Open — confirmed parameter gap
OQ-06	Is the "Deciding Criteria" set (Bed Type, Workspace, Wi-Fi, Cancellation) a fixed, product-defined default, or can it be extended per the user's stated attributeToCompare (for example, floor, view)? If extendable, how is the extra criterion added consistently to every card in the row?	Product	Open
OQ-07	What is the confirmed tie-break rule when two or more rooms score equally on the match flags used for the recommendation? See Edge Case EC-05.	Product	Open
OQ-08	The shared header in this tool call's mockup reads "ASR", while T-01, T-02, T-03, T-05, and T-06 use the fuller "discoverasr.com" label. Is this an intentional distinct treatment for room-level comparisons, or should the label be aligned across all inline tool call components for consistency?	Product / Design	Open — consistency check
OQ-09	What is the confirmed base URL for image assets in production and UAT? Consistent with the same open item logged in T-01, T-02, and T-06.	API Owner	Partially confirmed — validate prod vs UAT
