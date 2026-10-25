| PRD — MCP Tool Call Specification  │  T-05  │  Get_promotions | Ascott International  ·  DRAFT |

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

| UC-05  │  Find Applicable Promotions for a Stay     Tool Call: Get_promotions  ·  Type: READ  ·  API Coverage: MEDIUM |

| 1.  INTENT & USER CONTEXT |
| Overall User Objective | As a user, I want to see promotions, discounts, and offers relevant to my stay — whether tied to a property I have already identified or to a stated destination — so that I can find the best available saving before I book, and understand in plain language why a recommended offer is the best fit. |

| 1.1  VARIATION IN USER OBJECTIVES |
| User Story | Parameters the LLM passes (see input schema) |
| By location, generally  As a user, I want to see offers available in a stated country or city so that I can find a saving even before I pick a property. | countryCode (required) city (optional) |
| By property already identified  As a user, I want to see offers that apply to a property I have already found, so that I only see savings I can actually use. The LLM carries the property forward from an earlier T-01, T-02, or T-03 result, or resolves it from a property name stated directly. | propertyCode (optional) countryCode (required — resolved from the property if not separately stated) city (optional) |
| By dates or travel window  As a user, I want to filter offers by my travel dates, including qualitative language such as "this September" or "next month", so that I only see offers valid for when I am actually travelling. | countryCode (required) city (optional) checkinDate (optional) checkoutDate (optional) |
| By offer category  As a user, I want to filter offers by category (for example, dining, spa and wellness, room, retail) so that I only see savings relevant to what I am looking for. | countryCode (required) city (optional) voucherCategory (optional) |
| By type of experience As a user, I want to see if there are specific types of experiences offered that can combine well with my stay. | ? |
| By keyword or offer name  As a user, I want to search for a specific offer by name or keyword so that I can find a match even when I do not know its category. | countryCode (required) city (optional) voucherName (free text, optional) |
| By price or redemption value  As a user, I want to set a maximum price or points cost so that I only see offers within my budget, and see member-eligible pricing where it applies. | countryCode (required) city (optional) currencyCode (optional) maxPrice (optional) memberId (optional — auth param, required for member-eligible pricing and points display) |

| 1.2  KEY FINDINGS FROM USER RESEARCH |
| Insight | Detail |
| A single best answer beats a raw list | Users want to be told which offer is best, not left to compare a long list unaided. A ranked recommendation must sit above the general list, not replace it. |
| Users need the "why", not just the "what" | Trust in a recommendation depends on visible, specific reasons (for example, matches the stated property, matches the stated dates, gives the largest saving), not a generic "recommended" label with no basis shown. |
| Two different offer shapes must feel like one experience | A purchasable or redeemable voucher (with its own image, category, and expiry) and an automatically-applied rate-level discount on a stay search are structurally different, but the user does not distinguish between them when asking "any offers?". Both must render through the same card. |
| Urgency and exclusivity drive attention | Badges such as "Ending soon" and "Best match" are how users triage before reading full offer text, and must be visible on the card itself, not only in supporting prose. |
| Scope must be visible on every card | Some offers are valid at one or several named properties; others apply broadly (for example, "Worldwide"). The user must not be misled about where an offer can be used. |
| Redemption always finishes off-platform | The LLM confirms an offer's fit and value; it never completes a purchase, reservation, or code application inside the conversation. Applying a promotion to an active booking is handled by T-08 (Create_booking), not by this tool call. |
| Stacked filters can return zero results | Users may state more than one filter in a single request (for example, category and dates together). A zero-result outcome is an acceptable and expected response, not a failure state, consistent with T-01 and T-03. |

| 2.  UI COMPONENT & FRONT END BEHAVIOURS TO SUPPORT |
| Overview | T-05 renders through a single inline component shown directly in the chat. There is no full screen component for this tool call. The system must return one data packet large enough to populate the recommendation block and every offer card in the row, without a second call. LLM-authored prose appears only around the returned component — for example a follow-up question — never inside it. Scrolling the offer card row is a client-side re-render of already-returned data; no user action described in this section triggers a repeat call to T-05. |

| 2.1  INLINE COMPONENT |
| Element | Detail |
| Shared header | Source attribution: the asr logo icon and the "discoverasr.com" label. |
| Recommendation block | A star icon with the heading "Our recommendation!". One sentence naming the specific recommended offer and, where relevant, the property (for example, "The Citadines North Shinjuku Tokyo Grand Opening offer is the best match for your stay."). A "Why it's the best fit" subheading, followed by a row of reason chips, each with an icon and a short phrase (for example, "Valid at your selected property", "Save up to 30% on your stay", "Available for your travel dates", "Gives you the lowest eligible rate"). Each reason chip is shown only when its underlying match flag is true; a chip is never shown for a condition that was not actually met. |
| "Other offers available" section heading | A text heading introducing the card row below. |
| Offer card row | A horizontally scrollable row of offer cards. Each card shows: a status tag chip in the top-left corner (for example, "Best match!" or "Ending soon!"), a hero image, the offer title, a location-pin icon with a scope label (for example, a named list of cities, or "Worldwide"), a calendar icon with an offer end date ("Offer ends: [date]"), and a "View details" link carrying an outbound-link icon. |
| Below the component | LLM-authored prose (for example, additional context or a follow-up question). |

| 2.2  USER ACTIONS & SYSTEM BEHAVIOUR |
| User Action | System Response | Tool Call Triggered |
| Tap "View details" on a card | Opens an external link to the offer's page on the Ascott booking website (discoverasr.com). The exact destination varies by promotion type — see Open Question OQ-05. | None |
| Scroll the offer card row | Reveals additional cards from the already-returned result set. | None |

| 2.3  DATA PACKAGE MENTAL MODEL |
| Principle | T-05 must return one data packet that is large enough to fully populate the recommendation block and every offer card, without a second call. Because redemption completes off-platform, the data packet carries an external details link per offer rather than any in-conversation purchase or booking mechanism. The fields below are grouped by where they are consumed. |
| Field Group | Fields Required |
| Search context (once per response) | Resolved location label. Resolved property (if any). Applied filters echoed back (category, keyword, dates, price). Result count. Attribution / source platform label (asr / discoverasr.com). |
| Recommendation fields (once per response) | Recommended offer identifier. Recommendation sentence (generated by a narrow backend explanation service, grounded in the match flags below — see Section 4). Match flags: matchesProperty, discountPercentage, matchesDates, isLowestEligibleRate. Reason chip icon / label pairs, one per true match flag. |
| Per-offer card fields | Offer ID / code. Promotion type (voucher / rate_discount). Offer title. Hero image. Status badge flags: isBestMatch, isEndingSoon. Scope (array of applicable property codes, or a worldwide flag). Offer end / expiry date. Discount value (percentage or amount). External details URL. |
| Voucher-type-only fields | Category. Price and points cost. Currency. |
| Rate-discount-type-only fields | Applicable property code. Applicable dates. Strikethrough rate. Resulting per-night rate. |
| Currency parameter note | Every offer in a single response must display the same resolved currency, consistent with the T-01 currency normalisation principle. currencyCode is a first-class optional input parameter; if the user does not state a currency, the system defaults to the currency associated with the user's region. |

| 3.  TOOL CALL GUIDELINES |
| Tool call description | Return a list of promotions — purchasable vouchers and automatically-applied rate discounts — relevant to the user's stated destination and, where resolved, a specific property, together with a single ranked recommendation and plain-language reasoning, so the result can be rendered inline without a follow-up call. |
| When to use | Use when the user asks about discounts, offers, deals, promotions, or savings for a stay, whether or not a specific property has been identified. |
| When NOT to use | Do not use to apply a promo or voucher code to an active booking; refer to T-08 (Create_booking). Do not use to retrieve room-level rates on their own with no promotion context; refer to T-04 (Get_room_rate_details). |
| LLM instruction note | The LLM must resolve a countryCode (and city, where stated) before invoking this tool call, in the same way as T-01. propertyCode is optional: where it is carried from an earlier T-01, T-02, or T-03 result already in context, or stated directly by the user, the LLM passes it through. Where the user states more than one filter (category, keyword, dates, price), the LLM passes all stated filters together in a single call rather than issuing separate calls per filter. The LLM must not fabricate a reason chip or recommendation sentence beyond what the returned match flags support. |

| 3.1  ADJACENT BEHAVIOURS (AND THE TOOL THEY BELONG TO) |
| Adjacent behaviour (potential overlapping use case) | Appropriate tool chain |
| User browses properties and then asks about deals for one of them. | Invoke T-01 (Find_properties) or T-02 (Get_property_details) first to resolve the property. Once resolved, invoke T-05 with the propertyCode carried forward. |
| User finds a promotion in the T-05 result and wants to book with it. | Invoke T-05 to confirm the offer's fit and value. When the user proceeds to book, the LLM carries the offer's voucherCode / promotionCode forward to T-08 (Create_booking). Applying a code to a booking is a write action and is never performed by T-05 itself. |
| User asks generally, "any offers?", with no property or location stated. | The LLM must resolve at least a countryCode (and city, where stated) before invoking T-05, in the same way as T-01. T-05 is not invoked without a resolved location. |
| User asks about the full terms and conditions of a specific listed offer. | No confirmed tool call currently returns full terms-and-conditions detail beyond the card fields T-05 provides. The user is directed to the external details link. See Open Question OQ-04. |

| 4.  DATA & API CONTRACTS |
| Coverage status | MEDIUM. Core voucher inventory and rate-level discount data exist in confirmed Ascott APIs. The cross-referencing scoring layer that produces the single ranked recommendation, and the plain-language explanation of that recommendation, are new backend capabilities with no existing API equivalent, noted against API 5 below and logged in Section 12. |
| API no. | API name | Primary role in this tool call |
| 1 | searchvoucher (odx/mobilev1/v1/searchvoucher) | Primary source for purchasable / redeemable voucher-type promotions: voucherTitle / voucherEnTitle, category, imageThumbnail, propertyCode scope, country, expiryDate, basePrice / promoPrice, preferredCurrencyPromoPrice, promoPercentage, points, isEndingSoon, and voucherUrl. |
| 2 | getvoucherdetail (odx/mobilev1/v1/getvoucherdetail) | Supplemental source for a single voucher's fuller detail (participatingProperties, termsAndConditions, voucherTabs) where a card field requires it beyond what searchvoucher returns. Whether this call is required at the T-05 level, or only by a future single-offer detail tool call, requires confirmation. See Open Question OQ-04. |
| 3 | bookingsearch (v2-bookingsearch / BookingSearchV2 API) | Source for rate-level discount data when a propertyCode and dates are resolved: strikethroughRate, perNightRatePrefCurr, currency, and the isPromoCodeApplied / isVoucherCodeApplied flags used to detect an automatically-applied discount distinct from a purchasable voucher. |
| 4 | filtercountrycache / filtercitycache | Returns valid location filter values for countryCode / city, used to validate LLM-resolved location values before they are passed to searchvoucher and bookingsearch, consistent with the pattern used in T-01. |
| 5 | Backend scoring & explanation service — NEW, no confirmed existing API | Computes structured match flags across all candidate voucher-type and rate-discount-type offers, ranks the single best offer, and issues a narrow, non-conversational backend LLM call that is restricted to phrasing the recommendation sentence from those match flags only — it may not introduce a reason the flags do not support. This is a new backend capability, not sourced from any existing Ascott API. See Open Question OQ-01. |

| 5.  INPUT PARAMETERS — LLM-to-API SCHEMA |
| Input parameter (layman label) | Actual API parameter name | Type | Required / Optional | Assumed value when not provided | Constraints | Example |
| Location (country) | countryCode | String | Required | — | Free-text resolved by the LLM to a valid country code before invoking this tool call. | "Japan" |
| Location (city) | city | String | Optional | Omit — falls back to country-level search | City name resolved by the LLM. Paired with filtercitycache for city-level filter enumeration. | "Tokyo" |
| Property identifier | propertyCode | String | Optional | — | Carried from an earlier T-01, T-02, or T-03 result already in context, or resolved by the LLM from a stated property name. When present, results are filtered and weighted to promotions valid at this property. | "50926" |
| Check-in date | checkinDate | String | Optional | Current date | Must be today or a future date. The LLM must resolve qualitative language (for example, "this September") to an explicit date. Format: YYYY-MM-DD. | "2026-09-01" |
| Check-out date | checkoutDate | String | Optional | End of the resolved travel window | Must be after checkinDate. Format: YYYY-MM-DD. | "2026-09-30" |
| Guest count | noOfadults / noOfchildren | String | Optional | noOfadults = 1, noOfchildren = 0 | Two separate parameters, carried from upstream context if present. | "2 adults" |
| Offer / voucher category | voucherCategory | Array of String | Optional — API GAP | Omit — returns offers across all categories | No confirmed enum source at present. Proposed values include dining, spa and wellness, room, retail, concierge. See Open Question OQ-02. | ["Room"] |
| Keyword or offer name | voucherName | String | Optional | Omit | Free-text term matched against voucher title. | "Grand Opening" |
| Currency code | currencyCode | String | Optional | Currency associated with the user's region | Every offer in a single response must display this one currency — see Section 2.3. | "JPY" |
| Maximum price / redemption ceiling | maxPrice — PARAMETER GAP | String | Optional | — | No request-side parameter accepts a price ceiling in searchvoucher. The backend service layer must filter the retrieved result set before returning it. See Open Question OQ-03. | "50" |
| Member ID | memberId | String | Optional (auth param) | — | Marked mandatory in the current consumer app's searchvoucher integration; treated as an optional authentication passthrough for this tool call, needed to determine member-eligible pricing, points, and exclusive-deal eligibility. See Open Question OQ-07. | "M123456" |

| 6.  OUTPUT PARAMETERS — API-to-UI RESPONSE SCHEMA |
| Note | Lead with the common-sense UI requirements based on the data package mental model in Section 2.3, then map to the correct API response parameter names. Fields marked API GAP or PARAMETER GAP have no existing confirmed API response parameter. |
| Expected UI element | Actual response parameter name | Type | Assumed API source | Example value |
| Result count, resolved location, resolved property, applied filters, attribution | meta (Object) | Object | Backend-composed from the request | "3 offers available for Tokyo, September 2026" |
| Recommended offer identifier | recommendedOfferId | String | Backend scoring service (NEW) | "VOU-CITADINES-SHINJUKU-30" |
| Recommendation sentence | recommendationText | String | Backend explanation service (NEW — narrow LLM call, grounded in matchFlags) | "The Citadines North Shinjuku Tokyo Grand Opening offer is the best match for your stay." |
| Match flags | matchFlags → matchesProperty, discountPercentage, matchesDates, isLowestEligibleRate | Object | Backend scoring service (NEW) | true, 30, true, true |
| Reason chips | reasonChips[] → icon, label | Array of Object | Backend-composed (templated from matchFlags) | "📍", "Valid at your selected property" |
| Offer ID / code | offerId (voucherProgrammeCode) | String | searchvoucher | "VOU-CITADINES-SHINJUKU-30" |
| Promotion type | promotionType | String | Backend-composed ("voucher" / "rate_discount") | "voucher" |
| Offer title | offerTitle (voucherTitle / voucherEnTitle) | String | searchvoucher | "Celebrate Citadines North Shinjuku Tokyo Grand Opening – Save Up to 30%" |
| Hero image | imageThumbnail | String (URL path) | searchvoucher | [relative path] |
| Status badges | isBestMatch (backend-composed), isEndingSoon | Bool | Backend scoring service / searchvoucher | true, true |
| Scope | propertyCode[] / scopeLabel | Array of String / String | searchvoucher (propertyCode, country) | ["Osaka", "Tokyo", "Yokohama"] or "Worldwide" |
| Offer end date | expiryDate | Datetime | searchvoucher | "2026-09-30" |
| Discount value | promoPercentage | Number (Decimal) | searchvoucher | 30 |
| Price / points (voucher type only) | promoPrice, preferredCurrencyPromoPrice, points | Decimal / Integer | searchvoucher | 45.00, 18000 |
| Strikethrough / current rate (rate-discount type only) | strikethroughRate, perNightRatePrefCurr | Decimal | bookingsearch | 200, 175 |
| Currency | currency / currencyCode | String | searchvoucher, bookingsearch | "JPY" |
| External details link | externalOfferUrl — destination varies by promotionType | String (URL) | searchvoucher (voucherUrl) / bookingsearch (PARTIAL). See Open Question OQ-05. | "https://www.discoverasr.com/..." |

| 6.1  ILLUSTRATIVE DATA PACKET — CANONICAL OUTPUT |
| {   "meta": {     "location_query": "Tokyo, Japan",     "resolved_property_code": null,     "total_results": 3,     "applied_filters": { "checkin_date": "2026-09-01", "checkout_date": "2026-09-30" },     "attribution": "discoverasr.com"   },   "recommendation": {     "recommended_offer_id": "VOU-CITADINES-SHINJUKU-30",     "recommendation_text": "The Citadines North Shinjuku Tokyo Grand Opening offer is the best match for your stay.",     "match_flags": {       "matches_property": true,       "discount_percentage": 30,       "matches_dates": true,       "is_lowest_eligible_rate": true     },     "reason_chips": [       { "icon": "📍", "label": "Valid at your selected property" },       { "icon": "💰", "label": "Save up to 30% on your stay" },       { "icon": "📅", "label": "Available for your travel dates" },       { "icon": "✅", "label": "Gives you the lowest eligible rate" }     ]   },   "offers": [     {       "offer_id": "VOU-CITADINES-SHINJUKU-30",       "promotion_type": "voucher",       "offer_title": "Celebrate Citadines North Shinjuku Tokyo Grand Opening – Save Up to 30%",       "image_thumbnail": ".../citadines-shinjuku-promo.jpg",       "is_best_match": true,       "is_ending_soon": false,       "scope": { "property_codes": ["61023", "61024"], "scope_label": "Osaka, Tokyo, Yokohama" },       "expiry_date": "2026-09-30",       "discount": { "promo_percentage": 30 },       "pricing": { "promo_price": null, "points": null, "currency": "JPY" },       "external_offer_url": "https://www.discoverasr.com/offers/citadines-shinjuku-grand-opening"     },     {       "offer_id": "VOU-ASR-MIDYEAR",       "promotion_type": "voucher",       "offer_title": "ASR mid-year sale",       "image_thumbnail": ".../asr-midyear-sale.jpg",       "is_best_match": false,       "is_ending_soon": true,       "scope": { "property_codes": [], "scope_label": "Worldwide" },       "expiry_date": "2026-09-30",       "discount": { "promo_percentage": 20 },       "pricing": { "promo_price": null, "points": null, "currency": "JPY" },       "external_offer_url": "https://www.discoverasr.com/offers/asr-midyear-sale"     }   ] } |

| 7.  ERROR CONDITIONS & FALLBACK BEHAVIOUR |
| No. | Error condition | LLM fallback response (illustrative) |
| ER-01 | The API returns zero offers for the specified location, property, and filters, including when several filters are stacked together. | I was not able to find any current offers matching your criteria. Would you like me to broaden the search, for example by removing one of the filters or expanding the area? |
| ER-02 | Required parameter (location) is absent from the user request and cannot be resolved from context. | I would be happy to check for offers. Could you let me know which city or country you have in mind? |
| ER-03 | The API is unavailable or returns a 5xx error. | I am having trouble retrieving current offers right now. Could you try again in a moment? You can also browse offers directly at discoverasr.com. |
| ER-04 | The propertyCode carried from an earlier tool call is no longer resolvable at the time T-05 is invoked. | I could not confirm the property from your earlier search. Could you tell me the property name again so I can check for applicable offers? |
| ER-05 | An exclusive, member-eligible offer is present in the result set but memberId is absent. | Some of these offers include member-exclusive pricing. Would you like to sign in to your ASR account to see if you qualify? |
| ER-06 | The user states an offer category with no confirmed enumeration match. | I could not confirm "[value]" as an offer category. Would you like me to show the full range of current offers instead? |
| ER-07 | An external details link cannot be generated for a selected offer. | I could not open the details page for that offer. You can view current offers directly at discoverasr.com. |
| ER-08 | Check-in or check-out dates carried from an earlier tool call have since passed. | The dates from your earlier search have passed. I will show offers based on your stated destination only. Would you like to set new travel dates? |

| 8.  ACCEPTANCE CRITERIA |
| ID | Criteria |
| AC-01 Happy path | GIVEN a user specifies a valid location, WHEN the Get_promotions tool call is invoked, THEN the system returns a ranked recommendation and a list of applicable offers, each with the mandatory card fields from Section 2.3, renderable in the inline component. |
| AC-02 With property | GIVEN a propertyCode is resolved (stated directly or carried from T-01, T-02, or T-03), WHEN the tool call is invoked, THEN only offers valid at that property, or valid worldwide, are returned, and the property match is reflected in matchFlags.matchesProperty for every returned offer. |
| AC-03 With filters | GIVEN a user specifies one or more optional filters (category, keyword, dates, price), WHEN the tool call is invoked with the applicable parameters, THEN only offers matching all stated filters are returned, and a zero-result outcome is treated as a valid response, not an error. |
| AC-04 Recommendation grounding | GIVEN the tool call returns a recommendation, WHEN recommendationText and reasonChips are generated, THEN every reason stated is backed by a true value in matchFlags for that offer, and no reason is presented for a condition that was not actually met. |
| AC-05 Single best offer | GIVEN more than one offer is returned, WHEN the response is composed, THEN exactly one offer is marked isBestMatch = true, and it corresponds to recommendedOfferId. |
| AC-06 Currency normalisation | GIVEN a result set spanning offers with different local currencies, WHEN the response is composed, THEN every offer in the response displays the one resolved currencyCode, not each offer's own local currency. |
| AC-07 Client-side re-render | GIVEN a result set has already been returned, WHEN the user scrolls the offer card row, THEN the surface re-renders using the existing data packet, and T-05 is not re-invoked. |
| AC-08 No fabricated data | GIVEN the promotions API is unavailable, WHEN Get_promotions is attempted, THEN the LLM surfaces ER-03 and does not return invented offer data. |
| AC-09 Missing location | GIVEN a user expresses intent to find offers but does not specify a location and none can be resolved from context, WHEN the LLM processes the request, THEN the tool call is NOT invoked until a valid location is resolved. |

| 9.  SIDE EFFECTS |
| Tool call type | READ-ONLY. This tool call does not create, update, or delete any data, and does not itself apply a code or complete a redemption. It is safe to invoke multiple times with the same parameters. |
| Reversibility | Not applicable. This tool call has no side effects to reverse. |
| Authentication | Authentication is not required for basic offer browsing. When memberId is present, the response can reflect member-eligible pricing, points cost, and exclusive-deal eligibility. |
| Performance note | The base orchestration calls searchvoucher, and bookingsearch when a propertyCode and dates are resolved, followed by the backend scoring service and one narrow backend LLM call to produce the recommendation sentence. This adds latency relative to a simple list call and should be measured against the agreed SLA — see Open Question OQ-01. |
| Limitations | Without an authenticated session, member-eligible pricing and points display are unavailable. Price and redemption-ceiling filtering has no request-side parameter and must be applied by the backend service layer after retrieval, which may affect result completeness at scale. The recommendation and its explanation depend on a new backend capability not present in any existing Ascott API. |

| 10.  EDGE CASES |
| ID | Condition | System response |
| EC-01 | No offers are currently active for the resolved location or property. | The tool call returns an empty result set. The LLM communicates that no current offers are available and suggests checking back later or removing a filter. |
| EC-02 | Only one offer is returned. | The single offer is shown as the recommendation. The "Other offers available" row is omitted rather than shown empty. |
| EC-03 | An offer is valid at more than one property. | The scope label lists the applicable cities or properties (for example, "Osaka, Tokyo, Yokohama") rather than a single property name. |
| EC-04 | The user's stated dates fall outside every returned offer's validity window. | Offers are still returned, but matchFlags.matchesDates is false for each, and no offer is marked isBestMatch on the basis of date fit alone. Show offers within one month of the stay date, but make it clear to the user they can not apply these to the stay they’re currently looking at. |
| EC-05 | A member-exclusive offer is present but memberId is absent. | The offer is still shown with standard pricing where available. Member-eligible pricing and points are omitted rather than shown as zero. See ER-05. |
| EC-06 | An offer's native currency differs from the response-level currencyCode. | The backend service layer converts the price and discount fields to the one resolved currency before the card is returned, consistent with the pattern used in T-01. |
| EC-07 | Two offers appear equally strong against the stated criteria. | The backend scoring service applies a defined tie-break (for example, largest discount, then soonest expiry) so exactly one offer is marked isBestMatch. See Open Question OQ-01. |
| EC-08 | The offer's image is unavailable. | The card renders with the offer title and details but without the hero image. An appropriate placeholder is shown. The LLM does not fabricate an image. |
| EC-09 | A propertyCode carried from an earlier tool call no longer resolves to a valid property at the time T-05 is invoked. | The LLM surfaces ER-04 and asks the user to reconfirm the property before retrying. |

| 11.  SUCCESS METRICS |
| ID | Metric | Verification method |
| SM-01 | The tool call is invoked only when a valid location is present in the user's request or resolvable from context. | QA test: verify the tool call is not fired without a resolved countryCode or city parameter. |
| SM-02 | Offers returned match all applied filter parameters, including stacked filters. | Integration test: compare filter inputs against returned offer attributes across a representative test set. |
| SM-03 | Exactly one offer per response is marked as the recommendation, and every stated reason is backed by a true match flag. | Manual review and automated check: assert reasonChips never reference a matchFlag that is false for the recommended offer. |
| SM-04 | Every offer in a single response displays one consistent currency. | UI regression test: assert no response contains more than one currency code across its offers. |
| SM-05 | The offer card row supports scrolling from a single returned data packet, with no repeat API call. | UI test: verify scroll interaction re-renders from cached data and no new network call is issued. |
| SM-06 | Error conditions ER-01 through ER-08 produce the correct fallback response and no fabricated data. | Test suite: simulate each error condition and assert the correct fallback message. |
| SM-07 | The backend scoring and explanation service does not push end-to-end response time beyond the agreed SLA. | Performance test: measure response time for the scoring step and the explanation LLM call separately, and combined. |

| 12.  OPEN QUESTIONS |
| ID | Question | Owner | Status |
| OQ-01 | What is the confirmed architecture, ownership, and latency budget for the backend scoring and explanation service? What guardrail prevents the narrow explanation LLM call from introducing a reason not supported by matchFlags? | Integration Architect / Product | Open — new backend capability, scope and performance risk |
| OQ-02 | What is the confirmed enum source for offer / voucher category values (for example, dining, spa and wellness, room, retail, concierge)? | Integration Architect / Product | Open |
| OQ-03 | Since no request-side parameter accepts a price or points ceiling in searchvoucher, what is the agreed approach for backend-side filtering, and what is its impact on result completeness at scale? | Integration Architect | Open — confirmed parameter gap |
| OQ-04 | Is a getvoucherdetail call required at the T-05 level for any card field, or is searchvoucher alone sufficient, with fuller detail (terms and conditions, participating properties) deferred to a future single-offer detail tool call? | API Owner / Product | Open |
| OQ-05 | How is the external details link constructed for each promotion type? Does a voucher-type offer always resolve to a discoverasr.com voucher page, and a rate-discount-type offer to a rate or booking page, or is there a single unified destination pattern? | Integration Architect | Open |
| OQ-06 | Can bookingsearch reliably surface an automatically-applied rate-level discount (strikethroughRate) without a specific voucherCode already being tested against it, or must T-05 attempt candidate codes to discover a rate-discount-type offer? | API Owner | Open |
| OQ-07 | searchvoucher marks memberId as a mandatory request parameter in the current consumer app. Confirm the accepted unauthenticated behaviour for this tool call, and whether standard (non-member) pricing is reliably returned when memberId is absent. | API Owner | Open — requirement conflict to resolve |
| OQ-08 | What is the confirmed base URL for voucher image assets in production and UAT? | API Owner | Partially confirmed — validate prod vs UAT, consistent with T-01 and T-02 |
| OQ-09 | When both a voucher-type offer and a rate-discount-type offer are candidates for the same request, how are they compared on a common scale (percentage discount vs. an absolute rate reduction) to select the single recommendation? | Product / Integration Architect | Open |
