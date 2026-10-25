| PRD — MCP Tool Call Specification  │  T-06  │  Compare_properties | Ascott International  ·  DRAFT |

Tool Call Detailing Master Sheet
Product Requirements Document  ·  MCP AI Integration  ·  Ascott International
Document version: 1.0  ·  Date: 08 September 2026  ·  Status: DRAFT FOR REVIEW
TOOL TABLE  —  All Tool Calls in Scope
| ID | Tool Call Name | One-Line Purpose | Type |
| T-01 | Find_properties | See multiple property options | Read |
| T-02 | Get_property_details | Get full details for a specific property | Read |
| T-03 | Get_service_offerings | See bookable and orderable services at a property | Read |
| T-04 | Get_room_rate_details | See rooms and rates at a specific property | Read |
| T-05 | Get_promotions | Find applicable promotions for a stay | Read |
| T-06 | Compare_properties | Compare two or more properties side by side | Read |
| T-07 | Compare_rooms_rates | Compare rooms and rates within a property | Read |
| T-08 | Create_booking | Book a selected room and rate | Read |

| UC-06  │  Compare Two or More Properties Side by Side     Tool Call: Compare_properties  ·  Type: READ  ·  API Coverage: MEDIUM |

| 1.  INTENT & USER CONTEXT |
| Overall User Objective | As a user, I want to compare two or more Ascott properties side by side, together with a single recommended pick and plain-language reasons for it, so that I can make a confident shortlist decision without holding property details in memory or moving between separate property pages. |

| 1.1  VARIATION IN USER OBJECTIVES |
| User Story | Parameters the LLM passes (see input schema) |
| By property, generally As a user, I want to compare two or more properties I have already identified, so that I can see them side by side on the same set of attributes. | propertyCodes (required, array, minimum 2, maximum 4) |
| By dates and number of guests As a user, I want to compare properties for a stated date range and guest count, so that the price and availability shown for each property is directly comparable. | propertyCodes (required) checkinDate (optional) checkoutDate (optional) noOfadults (optional, default 1) noOfchildren (optional, default 0) |
| By rate or redemption value As a user, I want to remove a named property from the comparison if its rate is above my stated ceiling, so that I only compare properties within my budget. | propertyCodes (required) currencyCode (optional) maxRate (optional) |
| By amenities As a user, I want to remove a named property from the comparison if it does not have the amenities I need, so that I only compare properties with the facilities that matter to my stay. | propertyCodes (required) facilities (array, optional) |
| By room type availability As a user, I want to remove a named property from the comparison if it does not have inventory of the room type I need, so that I only compare properties that can actually serve my stay. | propertyCodes (required) roomType (optional — API GAP, same room-type pre-check pattern as T-01) |
| By location or proximity to POIs As a user, I want to compare properties by how close each one is to a place I care about, so that I can weigh location alongside the other attributes. | propertyCodes (required) poi (free text, optional — API GAP, same pattern as T-01) |
| By service offerings As a user, I want to know whether a service category I care about (for example, spa or dining) is present at each compared property, so that I can factor this into my decision. | propertyCodes (required) serviceCategory (optional — deferred; see Section 3.1 and Section 12. T-03's own service-offerings data source is a confirmed API gap, so this dimension cannot be reliably compared today) |
| By Nearby POIs As a user, I want to know which property has more interesting nearby POIs | propertyCodes (required) poi (free text, optional — API GAP, same pattern as T-01) |

| 1.2  KEY FINDINGS FROM USER RESEARCH |
| Insight | Detail |
| A single best answer beats a raw comparison | Users want to be told which property is the best fit for their stated need, not left to read every card unaided when evaluating more than two options. A ranked recommendation must sit above the comparison cards, not replace them, consistent with the pattern already established in T-05 (Get_promotions). |
| Users need the "why", not just the "what" | Trust in a recommendation depends on visible, specific reasons (for example, closer to a stated place, the largest saving, or a matching amenity), grounded in real data returned for that property. A generic "recommended" label with no stated basis is not sufficient. |
| Side-by-side cards reduce cognitive load | Users want compact property cards, showing some combination of core property elements  (image, name, rating, location, occupancy, room types, amenity highlights, and price) placed directly next to each other, so they do not need to hold details in memory or switch between separate property pages. |
| A summary table matters when comparing more than two | When evaluating more than two options, users expressed a preference for a summary table that clearly demonstrates the differences between properties on key attributes, in addition to the individual cards. |
| Every card in the comparison must show the same fields | Users notice when one property's card is missing a data point that another card shows. Where a data element cannot be confirmed for a given property, this must be shown consistently as a missing or unavailable state, not silently dropped from that one card. |
| Stacked filters can remove a named property entirely | Users may state a filter (for example, a price ceiling or a required amenity) that a named property does not meet. Removing that property from the comparison, with a clear stated reason, is an acceptable and expected outcome, not a failure state. |
| This tool call always operates on two or more already-identified properties | A minimum of two properties must be resolved, either carried from an earlier T-01 (Find_properties) result already in context, or named directly by the user, before this tool call can be invoked. It is never used to browse properties in a location; that is T-01's role. |

| 2.  UI COMPONENT & FRONT END BEHAVIOURS TO SUPPORT |
| Overview | T-06 renders through a single inline component shown directly in the chat. There is no full screen component for this tool call, consistent with T-05 (Get_promotions). The system must return one data packet large enough to populate the recommendation block and every property card in the row, without a second call. LLM-authored prose appears only around the returned component, never inside it. Scrolling the property card row is a client-side re-render of already-returned data; no user action described in this section triggers a repeat call to T-06. |

| 2.1  INLINE COMPONENT |
| Element | Detail |
| Shared header | Source attribution: the asr logo icon and the "discoverasr.com" label. |
| Recommendation block | A star icon with the heading "Our recommendation!". One sentence naming the recommended property and, inline within that sentence, a tag chip stating the traveller need or profile the recommendation is matched to (for example, "Business traveller"), shown only when the LLM can infer one from the user's stated need. A "Why it's a good fit" subheading, followed by a vertical list of reason lines, each with an icon and a short phrase (for example, "Convenient access to City Hall", "5-minute walk to Raffles Place MRT", "Meeting rooms available", "Reliable high-speed Wi-Fi"). Each reason line is shown only when its underlying match flag is true; a reason is never shown for a condition that was not actually met. |
| "How the properties compare" section heading | A text heading introducing the property card row below. |
| Property card row | A horizontally scrollable row of property cards, one per compared property (2 to 4 cards). Only the recommended card carries a "RECOMMENDED" tag chip, in the top-left corner of its hero image. Each card shows: a hero image with a brand logo watermark, the property name and a short location line overlaid at the base of the image, a "Reviews" row (numeric score and a 5-dot rating visual), a "Location" row (neighbourhood and district/area, on two lines), an "Occupancy" row (maximum guest count), a "Room types" row (chips, for example "Studio", "1-bedroom"), an "Amenity highlights" row (icon chips), a price block ("from [strikethrough rate]" then the current per-night rate), and a "See room and rates" button. |
| Below the component | LLM-authored prose (for example, a short elaboration on the recommended property's amenities, and a follow-up question). |

| 2.2  USER ACTIONS & SYSTEM BEHAVIOUR |
| User Action | System Response | Tool Call Triggered |
| Scroll the property card row | Reveals additional cards from the already-returned result set. | None |
| Tap "See rooms and rates" on a card | Replaces the inline component with the room-and-rate component for that property. | T-04  Get_room_rate_details (see LLM instruction note in Section 3 and Open Question OQ-05) |

| 2.3  DATA PACKAGE MENTAL MODEL |
| Principle | T-06 must return one data packet that is large enough to fully populate the recommendation block and every property card, without a second call. The fields below are grouped by where they are consumed. |

| Field Group | Fields Required |
| Search context (once per response) | Result count (number of properties compared). Applied filters echoed back (dates, guests, price ceiling, amenities, room type). Attribution / source platform label (asr / discoverasr.com). |
| Recommendation fields (once per response) | Recommended property identifier. Inferred traveller-need or profile label (for example, "Business traveller"), where the LLM can infer one from the user's stated criteria. Recommendation sentence (generated by a narrow backend explanation service, grounded in the match flags below — see Section 4). Match flags (for example, matchesStatedPOI, hasStatedAmenity, isLowestRate, matchesRoomType). Reason line icon / label pairs, one per true match flag. |
| Per-property card fields | Property ID / code. Property name. Brand logo. Hero image. Short location line (for card overlay). Star rating visual and numeric average rating. Neighbourhood / area and district. Maximum guest capacity. Room type chips available at the property. Amenity highlight icon chips. Starting nightly rate and strikethrough reference rate, in one response-level currency. A "recommended" flag, true only for the one recommended property. |

| Currency parameter note | Every property card in a single response must display the same resolved currency. currencyCode is a first-class optional input parameter; if the user does not state a currency, the system defaults to the currency associated with the user's region, consistent with the T-01 currency normalisation principle. |

| 3.  TOOL CALL GUIDELINES |
| Tool call description | Return a side-by-side comparison of two to four named or previously identified Ascott properties, together with a single ranked recommendation and plain-language reasoning grounded in the user's stated criteria, so the result can be rendered inline without a follow-up call. |
| When to use | Use when the user has two or more properties already in mind, whether named directly or carried from an earlier T-01 (Find_properties) result, and wants to weigh them against each other. |
| When NOT to use | Do not use to discover new candidate properties; refer to T-01 (Find_properties) first. Do not use to compare rooms and rates within a single property; refer to T-07 (Compare_rooms_rates). Do not use to retrieve full detail for a single property; refer to T-02 (Get_property_details). |
| LLM instruction note | The LLM must resolve at least two, and no more than four, propertyCode values before invoking this tool call, either carried from an earlier T-01 result already in context or stated directly by the user. Where the user states a filter that would exclude a named property (price ceiling, amenity, room type), the LLM passes all stated filters together in a single call rather than issuing separate calls per filter, and the response indicates which named properties were excluded and why. The LLM must not fabricate a reason line or recommendation sentence beyond what the returned match flags support, consistent with the pattern in T-05. |

| 3.1  ADJACENT BEHAVIOURS (AND THE TOOL THEY BELONG TO) |
| Adjacent behaviour (potential overlapping use case) | Appropriate tool chain |
| User is still browsing and has not identified two or more properties yet. | Invoke T-01 (Find_properties) first to establish candidates. T-06 is not invoked with fewer than two resolved properties. |
| User compares properties and then taps "See room and rates" on a card. | Invoke T-04 (Get_room_rate_details) for that property, carrying forward any dates and guest count already stated in the T-06 call. NOTE: the front-end button reads "See room and rates", which matches T-04's stated purpose ("See rooms and rates at a specific property"). This PRD assumes the handoff target is T-04, not T-05 (Get_promotions), on that basis. This assumption requires confirmation — see Open Question OQ-05. |
| User compares properties and then wants full detail on one of them (amenities, policies, reviews). | Invoke T-02 (Get_property_details) for that property. T-06 is not used for single-property depth. |
| User compares properties and then wants to compare rooms and rates within one property. | Invoke T-07 (Compare_rooms_rates) for that property, once selected. |
| User asks about promotions or discounts applicable to one of the compared properties. | Refer to T-05 (Get_promotions), carrying the propertyCode forward. This is a distinct tool call from T-06 and is not triggered automatically by any action within this component. |

| 4.  DATA & API CONTRACTS |
| Coverage status | MEDIUM. Per-property card data mirrors the confirmed T-01 / T-02 property fields (bookingpropertylist, bookingsearchresultv2, v1/propertyreviews, apartmentlist), each called once per compared property. The cross-referencing scoring layer that produces the single ranked recommendation, and its plain-language explanation, is a new backend capability with no existing API equivalent, consistent with the pattern already logged against T-05 (Get_promotions). |

| API no. | API name | Primary role in this tool call |
| 1 | bookingpropertylist | Per-property source for name, brand, thumbnail, property type, and starting rate. Called once per propertyCode in the comparison set. |
| 2 | bookingsearchresultv2 | Per-property source for hero image, gallery, facilities / amenities, coordinates, and city / country context, used for the card's location line and amenity highlight chips. |
| 3 | v1/propertyreviews | Returns guest review data (averageRatings, totalNumberOfReviews) per property, called once per propertyCode. |
| 4 | apartmentlist | Supplemental source for the room type chips (for example, "Studio", "1-bedroom") and the maximum occupancy value shown on the card. |
| 5 | getpropertyinfo | Supplemental source for localised address / area labelling where bookingsearchresultv2 is insufficient, consistent with its role in T-01 / T-02. |
| 6 | Backend scoring & explanation service — NEW, no confirmed existing API | Computes structured match flags across the resolved properties against the user's stated criteria, ranks the single best-fit property, and issues a narrow, non-conversational backend LLM call restricted to phrasing the recommendation sentence and reason lines from those match flags only. This is the same new backend capability logged against T-05 (Get_promotions). See Open Question OQ-01. |
| 7 | API GAP — POI API PENDING | No confirmed API returns a proximity statement (for example, "Convenient access to City Hall") for an arbitrary user-stated place. Same gap as T-01 / T-02. See Open Question OQ-02. |

| 5.  INPUT PARAMETERS — LLM-to-API SCHEMA |
| Input parameter (layman label) | Actual API parameter name | Type | Required / Optional | Assumed value when not provided | Constraints | Example |
| Properties to compare | propertyCodes | Array of String | Required | — | Minimum 2, maximum 4. Resolved by the LLM from a prior T-01 result already in context, or from property names stated directly in the user's prompt. | ["50926", "51002"] |
| Check-in date | checkinDate | String | Optional | 30 days from current date | Must be today or a future date. Must be before checkoutDate. Applied identically to every property in the comparison. Format YYYY-MM-DD. | "2026-10-07" |
| Check-out date | checkoutDate | String | Optional | 31 days from current date | Must be after checkinDate. | "2026-10-08" |
| Guest count (adults) | noOfadults | String | Optional | 1 | Applied identically to every property in the comparison. | "1" |
| Guest count (children) | noOfchildren | String | Optional | 0 | — | "0" |
| Currency code | currencyCode | String | Optional | Currency associated with the user's region | Every card in a single response must display this one currency, consistent with T-01. | "SGD" |
| Maximum rate / redemption ceiling | maxRate — PARAMETER GAP | String | Optional | — | No request-side parameter accepts a price ceiling in bookingpropertylist. The backend service layer must filter the retrieved result set, excluding any named property above the ceiling. See Open Question OQ-03. | "200" |
| Desired amenities | facilities | Array of String | Optional | — | Validated against filtercountrycache / filtercitycache enumeration, consistent with T-01. A property missing a stated amenity is excluded from the result set with a stated reason. | ["Swimming pool"] |
| Room type | roomType — API GAP | String | Optional | — | No confirmed enum source at the T-06 stage. When stated, the LLM passes the free-text value through to the room-type pre-check fan-out, consistent with T-01's OQ-02. | "Suite" |
| Point of interest | poi — API GAP | String | Optional | — | No proximity parameter exists in any T-06 API. Logged as a proposed workaround consistent with T-01's OQ-06. | "near City Hall" |
| Traveller need / profile | travellerProfile (LLM-derived, not a confirmed API parameter) | String | Optional (derived) | — | Free text inferred by the LLM from the user's stated context (for example, "solo business traveller"). Passed to the backend scoring service to weight match flags and generate the inline profile chip. See Open Question OQ-01. | "solo business traveller" |
| Service category | serviceCategory — API GAP, deferred | String | Optional | — | No confirmed data source exists at the T-06 stage; see Section 3.1 and Section 1.1. Not passed to any confirmed API today. | "Spa" |
| Member ID | memberId | String | Optional (auth param) | — | Required to reflect member rates in the per-property price block. Supplied via authentication context, not entered by the user. | "M123456" |

| 6.  OUTPUT PARAMETERS — API-to-UI RESPONSE SCHEMA |
| Note | Lead with the common-sense UI requirements based on the data package mental model in Section 2.3, then map to the correct API response parameter names. Fields marked API GAP or PARAMETER GAP have no existing confirmed API response parameter. |

| Expected UI element | Actual response parameter name | Type | Assumed API source | Example value |
| Result count, applied filters, attribution | meta (Object) | Object | Backend-composed from the request | "Comparing 3 properties in Central Singapore" |
| Recommended property identifier | recommendedPropertyCode | String | Backend scoring service (NEW) | "50926" |
| Inferred traveller-need label (inline chip) | travellerProfileLabel | String | Backend scoring service (NEW, derived from LLM-passed travellerProfile) | "Business traveller" |
| Recommendation sentence | recommendationText | String | Backend explanation service (NEW — narrow LLM call, grounded in matchFlags) | "Ascott Raffles Place is the best fit for a solo Business traveller." |
| Match flags | matchFlags → matchesStatedPOI, hasStatedAmenity, isLowestRate, matchesRoomType | Object | Backend scoring service (NEW) | true, true, false, true |
| Reason lines ("Why it's a good fit") | reasonLines[] → icon, label | Array of Object | Backend-composed (templated from matchFlags) | "📍", "Convenient access to City Hall" |
| Property code | propertyCode | String | bookingpropertylist, bookingsearchresultv2 | "50926" |
| Property name | propertyName | String | bookingpropertylist, bookingsearchresultv2 | "Ascott Raffles Place" |
| Brand logo | brandlogo | String (URL) | bookingpropertylist, bookingsearchresultv2 | [relative path] |
| Hero image | bannerImageMobile | String (URL) | bookingsearchresultv2, bookingpropertylist | [relative path] |
| Card location line | city, area/district (backend-composed) | String | bookingsearchresultv2, getpropertyinfo | "Central Singapore: 2 mins walk from Raffles Place MRT" |
| Guest review score | averageRatings | Number (Decimal) | v1/propertyreviews | 4.6 |
| Review count (supports rating visual) | totalNumberOfReviews | Integer | v1/propertyreviews | 3265 |
| Neighbourhood / district (Location row) | city, areaLabel | String | bookingsearchresultv2, getpropertyinfo | "Raffles Place", "Central business district" |
| Maximum occupancy | maxPersonInRoom | String | apartmentlist | 2 |
| Room type chips | apartmentType[] (distinct room types at the property) | Array of String | apartmentlist | ["Studio", "1-bedroom"] |
| Amenity highlight chips | facilityGroup → facilities[] → imagePath, description | Array of Object | bookingsearchresultv2 | "Gym & Pool", "Spa" |
| Starting nightly rate | perNightRatePrefCurr | String (Decimal) | bookingpropertylist, bookingsearchresultv2 | 175 |
| Strikethrough / reference rate | strikethroughRate | String (Decimal) | bookingsearchresultv2 | 200 |
| Currency code | currency | String | bookingpropertylist, bookingsearchresultv2 | "SGD" |
| Recommended flag | isRecommended | Bool | Backend-composed (true only for recommendedPropertyCode) | true |
| Participating in ASR | isASR | Bool | ? | ? |

| 6.1  ILLUSTRATIVE DATA PACKET — CANONICAL OUTPUT |
| { "meta": { "total_results": 3, "location_query": "Central Singapore", "currency": "SGD", "checkin_date": "2026-10-07", "checkout_date": "2026-10-08", "noOfadults": 1, "noOfchildren": 0, "attribution": "discoverasr.com" }, "recommendation": { "recommended_property_code": "50926", "traveller_profile_label": "Business traveller", "recommendation_text": "Ascott Raffles Place is the best fit for a solo Business traveller.", "match_flags": { "matches_stated_poi": true, "has_meeting_rooms": true, "has_reliable_wifi": true, "is_lowest_rate": false }, "reason_lines": [ { "icon": "📍", "label": "Convenient access to City Hall" }, { "icon": "🚆", "label": "5-minute walk to Raffles Place MRT" }, { "icon": "💼", "label": "Meeting rooms available" }, { "icon": "📶", "label": "Reliable high-speed Wi-Fi" } ] }, "properties": [ { "property_code": "50926", "property_name": "Ascott Raffles Place", "is_recommended": true, "brand_logo_url": ".../logo-ascott-en.png", "banner_image_url": ".../ascott-raffles-place/banner.jpg", "card_location_line": "Central Singapore: 2 mins walk from Raffles Place MRT", "rating": { "average_ratings": 4.6, "total_number_of_reviews": 3265 }, "location": { "area_label": "Raffles Place", "district_label": "Central business district" }, "max_person_in_room": 2, "room_types": ["Studio", "1-bedroom"], "amenity_highlights": ["Gym & Pool", "Spa"], "pricing": { "per_night_rate_pref_curr": 175.00, "strikethrough_rate": 175.00, "currency": "SGD" } }, { "property_code": "51002", "property_name": "Oakwood Premier Raffles Place", "is_recommended": false, "brand_logo_url": ".../logo-oakwood-en.png", "banner_image_url": ".../oakwood-premier-raffles-place/banner.jpg", "card_location_line": "Central Singapore: 2 mins walk from Raffles Place MRT", "rating": { "average_ratings": 4.6, "total_number_of_reviews": 2980 }, "location": { "area_label": "Raffles Place", "district_label": "Central business district" }, "max_person_in_room": 2, "room_types": ["Studio", "1-bedroom"], "amenity_highlights": ["Gym & Pool", "Spa"], "pricing": { "per_night_rate_pref_curr": 175.00, "strikethrough_rate": 175.00, "currency": "SGD" } } ] } |

| 7.  ERROR CONDITIONS & FALLBACK BEHAVIOUR |
| No. | Error condition | LLM fallback response (illustrative) |
| ER-01 | Fewer than two properties can be resolved from the user's request or from context. | I need at least two properties to compare. Could you name a second property, or would you like me to help you find one first? |
| ER-02 | The user names more than four properties for comparison. | I can compare up to four properties at a time. I have compared the first four you named — would you like me to swap in a different one? |
| ER-03 | The API is unavailable or returns a 5xx error. | I am having trouble retrieving property details right now. Could you try again in a moment? You can also compare properties directly at ascott.com. |
| ER-04 | One or more of the user's stated property names cannot be resolved to a valid propertyCode. | I was not able to confirm one of the properties you named. Could you give me the full property name or the city it is in? |
| ER-05 | Stated filters (price ceiling, amenity, room type) reduce the comparison set below two properties. | After applying your filters, fewer than two properties are left to compare. Would you like me to relax one of the filters? I can provide recommendations on the next suitable properties for your stay. |
| ER-06 | The user names a property that is not a confirmed Ascott property. | I can only compare Ascott properties. Please provide me a property name from Ascott, otherwise I can help you find them. |
| ER-07 | Member ID is absent when the user requests ASR member rates. | To show member rates and points, I need you to be signed in to your ASR account. Would you like to sign in, or shall I compare standard rates instead? |
| ER-08 | A property has no available rate for the stated dates. | The property is shown with an "Availability on request" label instead of a price. The LLM does not fabricate a rate. Show next available date and price |

| 8.  ACCEPTANCE CRITERIA |
| AC-01 Happy path | GIVEN a user specifies two to four valid properties, WHEN the Compare_properties tool call is invoked, THEN the system returns a recommendation and a property card for each, renderable in the inline component. |
| AC-02 With filters | GIVEN a user specifies one or more optional filters (price, amenities, room type), WHEN the tool call is invoked, THEN any named property failing a stated filter is excluded from the comparison, with the reason communicated to the user. |
| AC-03 Minimum enforced | GIVEN fewer than two properties can be resolved, WHEN the LLM processes the request, THEN the tool call is NOT invoked until a second property is resolved. |
| AC-04 Maximum enforced | GIVEN a user names more than four properties, WHEN the tool call is invoked, THEN the comparison is limited to four properties and the user is told which were included. |
| AC-05 Recommendation grounding | GIVEN the tool call returns a recommendation, WHEN recommendationText and reasonLines are generated, THEN every reason stated is backed by a true value in matchFlags for that property, and no reason is presented for a condition that was not actually met. |
| AC-06 Single recommended property | GIVEN two or more properties are returned, WHEN the response is composed, THEN exactly one property is marked isRecommended = true, and it corresponds to recommendedPropertyCode. |
| AC-07 Currency normalisation | GIVEN a comparison set spanning properties with different local currencies, WHEN the response is composed, THEN every property card displays the one resolved currencyCode, not each property's own local currency. |
| AC-08 Client-side re-render | GIVEN a result set has already been returned, WHEN the user scrolls the property card row, THEN the surface re-renders using the existing data packet, and T-06 is not re-invoked. |
| AC-09 T-04 handoff | GIVEN a user taps "See room and rates" on a card, WHEN the action is triggered, THEN T-04 (Get_room_rate_details) is invoked with the correct propertyCode, and any dates and guest count already stated in the T-06 call are carried forward. This criterion is subject to confirmation of Open Question OQ-05. |
| AC-10 No fabricated data | GIVEN the property data or the recommendation service is unavailable, WHEN Compare_properties is attempted, THEN the LLM surfaces the applicable error condition and does not return invented property or recommendation data. |

| 9.  SIDE EFFECTS |
| Tool call type | READ-ONLY. This tool call does not create, update, or delete any data. It is safe to invoke multiple times with the same parameters. |
| Reversibility | Not applicable. This tool call has no side effects to reverse. |
| Authentication | Authentication is not required for a basic comparison. When memberId is present, member rates are reflected in each property's price block. |
| Performance note | The base orchestration calls bookingpropertylist, bookingsearchresultv2, v1/propertyreviews, and apartmentlist once per compared property (a 2x to 4x fan-out relative to a single-property call), followed by the backend scoring service and one narrow backend LLM call to produce the recommendation sentence and reason lines. This adds latency relative to a single-property lookup and should be measured against the agreed SLA — see Open Question OQ-01. |
| Limitations | The recommendation and its explanation depend on a new backend capability not present in any existing Ascott API. Points-of-interest proximity is a confirmed API gap. Price-ceiling filtering has no request-side parameter and must be applied by the backend service layer after retrieval. Service-offerings comparison is deferred pending resolution of the API gap already logged against T-03. |

| 10.  EDGE CASES |
| ID | Condition | System response |
| EC-01 | The user names the same property twice. | The duplicate is removed before invoking the tool call; the comparison proceeds with the remaining distinct properties. |
| EC-02 | The user names five or more properties. | The tool call compares the first four named properties. The LLM tells the user which properties were included and offers to swap one in or out. |
| EC-03 | A named property is not a confirmed Ascott property. | That property is excluded from the comparison. The LLM confirms it can only compare Ascott properties. |
| EC-04 | Stated filters leave only one comparable property. | The LLM does not render a one-property "comparison". It tells the user only one property meets the stated criteria and offers T-02 (Get_property_details) for that property instead. |
| EC-05 | Two properties tie on the match flags used for the recommendation. | The backend scoring service applies a defined tie-break (for example, highest guest rating, then lowest rate) so exactly one property is marked isRecommended, consistent with the tie-break pattern used in T-05. |
| EC-06 | A property has no available rate for the stated dates. | The card shows an "Availability on request" label instead of a price. The LLM does not fabricate a rate. |
| EC-07 | A property's native currency differs from the response-level currencyCode. | The backend service layer converts the rate fields using the property's preferred-currency conversion rate before the card is returned, so every card displays the one resolved currency. |
| EC-08 | The user states no particular travel need or profile (for example, asks only "compare these two properties"). | The recommendation sentence and inline profile chip are omitted. The reason lines and recommendation are instead grounded in objective match flags (for example, rating, price, stated filters) rather than an inferred traveller need. |
| EC-09 | A property's hero image is unavailable. | The card renders with the property name and details but without the hero image. An appropriate placeholder is shown. The LLM does not fabricate an image. |
| EC-10 | A data point is available for one compared property but not another (for example, one property has no confirmed room type chips). | The affected card shows that field as unavailable rather than omitting the row entirely, so every card in the row keeps the same field layout. |

| 11.  SUCCESS METRICS |
| ID | Metric | Verification method |
| SM-01 | The tool call is invoked only when at least two valid propertyCode values are resolved. | QA test: verify the tool call is not fired with fewer than two resolved properties. |
| SM-02 | Exactly one property per response is marked as the recommendation, and every stated reason is backed by a true match flag. | Manual review and automated check: assert reasonLines never reference a matchFlag that is false for the recommended property. |
| SM-03 | Every property card in a single response displays one consistent currency. | UI regression test: assert no response contains more than one currency code across its properties. |
| SM-04 | Properties failing a stated filter are correctly excluded, with a reason communicated to the user. | Integration test: compare filter inputs against the returned and excluded property sets across a representative test set. |
| SM-05 | The property card row supports scrolling from a single returned data packet, with no repeat API call. | UI test: verify scroll interaction re-renders from cached data and no new network call is issued. |
| SM-06 | The "See room and rates" action fires T-04 with the correct propertyCode, and carries forward dates and guest count. | Integration test: verify T-04 receives the propertyCode and stay context from the active T-06 packet, not re-resolved values. |
| SM-07 | Error conditions ER-01 through ER-08 produce the correct fallback response and no fabricated data. | Test suite: simulate each error condition and assert the correct fallback message. |
| SM-08 | The backend scoring and explanation service does not push end-to-end response time beyond the agreed SLA. | Performance test: measure response time for the scoring step and the explanation LLM call separately, and combined, across a 2-property and a 4-property comparison. |

| 12.  OPEN QUESTIONS |
| ID | Question | Owner | Status |
| OQ-01 | What is the confirmed architecture, ownership, and latency budget for the backend scoring and explanation service, and how is the LLM-derived travellerProfile weighted into the match-flag scoring? What guardrail prevents the narrow explanation LLM call from introducing a reason not supported by matchFlags? | Integration Architect / Product | Open — new backend capability, scope and performance risk |
| OQ-02 | What is the confirmed name and contract for the points-of-interest API needed to ground proximity-based reason lines (for example, "Convenient access to City Hall")? Same gap as T-01 and T-02. | Product / API Owner | Open — confirmed API gap, API pending |
| OQ-03 | Since no request-side parameter accepts a price ceiling in bookingpropertylist, what is the agreed approach for backend-side filtering, and how are excluded properties communicated back to the user? | Integration Architect | Open — confirmed parameter gap |
| OQ-04 | Is there a confirmed enum source for room-type values at the T-06 stage, consistent with the gap already logged as OQ-02 in T-01? | Integration Architect / Product | Open — confirmed parameter gap |
| OQ-05 | Does tapping "See room and rates" on a comparison card fire T-04 (Get_room_rate_details), as this PRD assumes from the button label, or T-05 (Get_promotions), as stated in the original brief for this interaction? The button copy matches T-04's purpose ("See rooms and rates at a specific property"); this needs explicit confirmation before build. | Product | Open — naming conflict to resolve |
| OQ-06 | What is the confirmed source and extraction logic for the room type chips shown on the card (for example, "Studio", "1-bedroom")? Is this the full distinct list of apartmentlist categories at the property, or a curated subset? | API Owner | Open |
| OQ-07 | What is the confirmed data source for comparing properties by service category (for example, spa, dining)? This is currently deferred, as T-03 (Get_service_offerings) itself has no confirmed backend API. See Section 1.1 and Section 3.1. | Product / API Owner | Open — for future roadmap, tied to T-03 |
| OQ-08 | What is the confirmed tie-break rule when two or more properties score equally on the match flags used for the recommendation? See Edge Case EC-05. | Product | Open |
| OQ-09 | What is the confirmed base URL for image assets in production and UAT? Consistent with the same open item logged in T-01 and T-02. | API Owner | Partially confirmed — validate prod vs UAT |

| VALIDATION AGAINST UI MOCKUPS |
| Validation note | Every data element visible in the provided screenshot is present in Section 6 and Section 6.1: the source attribution (meta.attribution), the recommendation heading, sentence, and inline traveller-profile chip (recommendation.recommendation_text, recommendation.traveller_profile_label), the "Why it's a good fit" reason lines (recommendation.reason_lines, each grounded in match_flags), the "How the properties compare" card row with the "RECOMMENDED" tag (is_recommended), hero image and brand watermark, property name and location line, star rating and numeric score, Location / Occupancy / Room types / Amenity highlights rows, the strikethrough and current per-night rate, and the "See room and rates" button. The one element with no confirmed existing API source — the recommendation logic itself, spanning both the match-flag scoring and the plain-language explanation — is explicitly marked as a new backend capability in Section 4 and logged as Open Question OQ-01, consistent with the screenshot being treated as the source of truth for required output fields. |

As discussed on 14 September, the OpenAI response should always align with the output returned by the tool call across all use cases, and not only recommendation-related scenarios.
In general, whenever a tool call returns a result, the OpenAI response displayed below the tool call box should provide the supporting rationale, context, or explanation that is consistent with the tool output.
For example, if the tool call recommends ARPS as the most suitable property for a business traveller, the OpenAI response should explain why ARPS is the best match based on the traveller's requirements. Similarly, for any other use case, the OpenAI response should complement the tool output by explaining the reasoning behind the result rather than presenting information that is disconnected from or contradictory to the tool call response.