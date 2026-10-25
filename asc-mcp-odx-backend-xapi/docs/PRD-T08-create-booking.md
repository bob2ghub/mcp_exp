| PRD — MCP Tool Call Specification │ T-08 │ Create_booking | Ascott International · DRAFT |

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

| UC-08 │ Create a Bookable Checkout Handoff for a Stay Tool Call: Create_booking · Type: READ · API Coverage: HIGH |

1.  INTENT & USER CONTEXT
| Overall User Objective | As a user, I want to confirm the stay I have decided on — property, room, rate, dates, and guest count — and move straight to a pre-filled checkout on the Ascott booking website, so that I do not have to re-enter details I have already worked out in conversation. |

1.1  VARIATION IN USER OBJECTIVES
| User Story | Parameters the LLM passes (see input schema) |
| By a fully resolved room and rate (downstream invocation) As a user, I want to say “book this” or “book for me” after selecting a room and rate from T-04 or T-07, so that I move straight to a checkout summary reflecting my exact selection. | propertyCode (required — carried from T-04/T-07) apartmentCategoryCode (required — carried from T-04/T-07) ratePlanCode (required — carried from T-04/T-07) checkinDate / checkoutDate (required — carried from context) noOfadults / noOfchildren (required — carried from context) |
| By a named property, with no room or rate yet selected (cold invocation) As a user, I want to say “book me a room at Ascott Raffles Place” without first browsing rooms, so that I can get straight to a bookable checkout summary without extra steps. The LLM resolves the property, then silently runs an internal room-and-rate lookup and selects the cheapest available room and rate for the stated or default dates and guest count. | propertyCode (required — resolved by the LLM from the stated property name) checkinDate / checkoutDate (optional, default: 30/31 days from current date) noOfadults / noOfchildren (optional, default 1/0) |

1.2  KEY FINDINGS FROM USER RESEARCH
| Insight | Detail |
| Checkout must complete off-platform, without friction | Users are willing to finish payment on the Ascott website, but only if their stay details carry over completely. Re-entering dates, guests, room, or rate at checkout is an unacceptable outcome. |
| The conversational mental model does not expect a transaction inside the LLM | Users associate discovery and planning with the AI environment, and the transaction itself with a familiar OTA or hotel-site experience. This tool call must reinforce that boundary, not blur it. |
| Confirmation and comms should come from the brand, not the LLM provider | Users are comfortable completing a booking in-line within the LLM (assuming their preferred payment method is supported), but expect confirmation and invoice to be sent by Ascott through its own channels (for example, email), not by the LLM provider. |
| Saved payment shortcuts are a desired future state | Users expressed a desire for the LLM to access or shortcut a saved payment method on file, so the checkout step is faster. This is out of scope for this version and is logged for a future iteration. |
| A booking summary is the trust-building step before handoff | Users want to see a clear, correct summary — property, room, dates, guests, and total — before they are asked to leave the conversation to complete anything. This is the primary function of the inline component. |
| Booking outcome is invisible once the user leaves for checkout | There is no confirmed return channel from the Ascott checkout website back into the conversation. The LLM must not claim to know whether a booking succeeded, and does not re-invoke this tool call to check status. |

2.  UI COMPONENT & FRONT END BEHAVIOURS TO SUPPORT
| Overview | T-08 renders through a single inline component shown directly in the chat. There is no full screen component for this tool call, consistent with T-05 (Get_promotions) and T-06 (Compare_properties). The system must return one data packet large enough to fully populate the booking summary card and construct the external checkout link, without a second call, except where the user changes dates or guest count (see Section 2.3), which re-invokes this tool call with the updated parameters. |

2.1  INLINE COMPONENT
| Element | Detail |
| Header | “Ready to book your stay?” heading. Explanatory copy stating that the selected stay details will carry over, so the user can review and complete the booking on the ASR website. |
| Property summary block | Hero image with a brand logo watermark (for example, the Ascott logo centred on the room photo). Property name. Location line with a pin icon (address). |
| Stay detail rows | Date range with a calendar icon (for example, “4 May - 13 May”). Guest count with a guest icon (for example, “1 Adult, 1 Child”). Room name with a room icon (for example, “Cutler Suite Studio”). Rate plan name with a rate icon (for example, “First-Stay Member Special”). |
| Total and policy block | Total stay price with currency (for example, “SGD 1,750”) and a “Taxes and fees included” note. A free-cancellation deadline line (for example, “Free cancellation until 6:00 PM on 18 September 2026”), shown only when the resolved rate plan is cancellable. |
| ASR points-earn callout | A star-icon badge stating the ASR points-earn estimate for the stay (for example, “Members can earn up to 6,500 Pts for this stay!”). |
| ASR enrolment checkbox | “” checkbox, with explanatory copy that the user's details will be used to set up an account, reviewed and confirmed on the ASR website. When checked, this is reflected as enrollAsrOnCheckout in the external checkout link. |
| External checkout CTA | “Book now on website” full-width button with an outbound-link icon. Tapping opens the external checkout link, carrying every resolved stay detail, in a new browser tab. |
| Below the component | LLM-authored prose (for example, confirming the details shown, or inviting the user to change dates or guests before proceeding). |

2.2  FULL SCREEN COMPONENT
Not applicable. T-08 has no full screen component. The single inline booking summary card, described in Section 2.1, is the only surface this tool call renders, consistent with the pattern already established in T-05 (Get_promotions) and T-06 (Compare_properties).
2.3  USER ACTIONS & SYSTEM BEHAVIOUR
| User Action | Surface | System Response | Tool Call Triggered |
| Tap the “Join ASR and enjoy member benefits!” checkbox | Inline | Toggles enrollAsrOnCheckout for the current summary. The external checkout link is updated to carry the new value. Whether this is a client-side link update or requires this tool call to be silently re-invoked to regenerate the link is unconfirmed. See Open Question OQ-05. | None (assumed) — see OQ-05 |
| State new or changed dates or guest count | Inline | Re-invokes Create_booking with the updated checkinDate, checkoutDate, noOfadults, and noOfchildren. The underlying room-and-rate availability check described in Section 3 is re-run before an updated summary card is returned. | T-08 (re-invoked) |
| Tap “Book now on ASR website” | Inline | Opens the external checkout link in a new browser tab, carrying forward every resolved stay detail (property, room, rate, dates, guests, currency, voucher/promotion code, and ASR enrolment flag) so the user does not need to re-enter them. | None |

2.4  DATA PACKAGE MENTAL MODEL
| Principle | T-08 must return one data packet, built from a validated room-and-rate lookup, that is large enough to fully populate the booking summary card and construct the external checkout link, without a second call other than an explicit date or guest change. Because the transaction itself completes off-platform, the data packet carries a single external checkout URL with every resolved parameter embedded, rather than any in-conversation payment mechanism. |

| Field Group | Fields Required |
| Search context (once per response) | Resolved propertyCode. Resolved room and rate (apartmentCategoryCode, ratePlanCode). Resolution method (explicitly selected via T-04/T-07, or cheapest-available cold pick). Dates, guest count, and currency code used across the response. |
| Property summary fields | Property name. Hero image. Brand logo. Address. |
| Stay and rate fields | Date range display. Guest count display. Room name. Rate plan name. Total stay price and currency. Tax-inclusive flag. Free-cancellation deadline text (where applicable). ASR points-earn estimate. |
| Checkout handoff fields | Cart reference (cartId) and availability confirmation flag (isAvailable), where returned by bookingcart. External checkout URL. Every carried parameter echoed for traceability: propertyCode, apartmentCategoryCode, ratePlanCode, checkinDate, checkoutDate, noOfadults, noOfchildren, currencyCode, voucherCode / promotionCode, enrollAsrOnCheckout, and memberId when present. |

3.  TOOL CALL GUIDELINES
| Tool call description | Validate that a specific room and rate at an Ascott property is still bookable for the stated dates and guest count — either a room and rate already selected via T-04 or T-07, or the cheapest available room and rate at a named property when none has been selected — and return a booking summary together with a single external checkout link carrying every resolved parameter, so the user can complete payment on the Ascott booking website without re-entering any detail already established in conversation. |
| When to use | Use when the user confirms they want to book a specific room and rate already surfaced by T-04 or T-07, or when the user expresses direct booking intent at a named property with no room or rate yet selected. |
| When NOT to use | Do not use to browse rooms or rates; refer to T-04 (Get_room_rate_details). Do not use to compare rooms; refer to T-07 (Compare_rooms_rates). Do not use to complete payment or write a reservation to the Ascott system; this tool call never performs a write and never collects guest personal or payment details — refer the user to the external ASR checkout website for that step. |
| LLM instruction note | When a room and rate are already resolved from a prior T-04 or T-07 call in the same conversation, the LLM carries propertyCode, apartmentCategoryCode, ratePlanCode, dates, and guest count forward without re-asking. When no room or rate is resolved, the LLM resolves the property, then silently runs the same room-and-rate lookup used by T-04, and selects the room and rate with the lowest per-night rate for the stated or default dates and guest count, without presenting this intermediate step to the user. Where a voucher or promotion code is present from an earlier T-05 result or stated directly, the LLM passes it through. Where the user states an intent to join ASR as part of this booking, the LLM sets enrollAsrOnCheckout. If the resolved room and rate return no availability at the time of invocation, the LLM does not construct a checkout link for unavailable inventory (see ER-04). |

3.1  ADJACENT BEHAVIOURS (AND THE TOOL THEY BELONG TO)
| Adjacent behaviour (potential overlapping use case) | Appropriate tool chain |
| User selects a room and rate on T-04 or T-07 and taps “Book” or “Book now”. | Invoke T-08 with propertyCode, apartmentCategoryCode, ratePlanCode, dates, and guest count carried directly from the active T-04/T-07 packet. No re-resolution is needed. |
| User asks to book a named property with no prior room or rate search. | Invoke T-08 directly. The LLM resolves the property, then runs an internal room-and-rate lookup (the same orchestration as T-04) and selects the cheapest available option, consistent with the cold-invocation pattern in Section 1.1. |
| User changes dates or guest count after seeing the booking summary. | Re-invoke T-08 with the updated parameters. The underlying room-and-rate lookup is re-run to confirm availability at the new dates and guest count before a new summary is shown, consistent with Section 2.3. |
| User wants to apply a promotion found earlier in the conversation. | Carry the voucherCode / promotionCode from the earlier T-05 (Get_promotions) result into this T-08 call. T-08 itself does not retrieve or validate promotions; refer to T-05 for that. |
| User wants to change the room or rate itself, not just dates or guests. | Do not re-invoke T-08 directly for this. Refer back to T-04 or T-07 so the user can select a different room and rate. T-08 is invoked again once a new selection is made. |
| User asks whether their booking was successful after leaving for the external website. | Do not invoke T-08, or any tool call, to check. Booking confirmation happens off-platform through Ascott's own channels; the LLM does not claim knowledge of a booking's outcome once the user has left for checkout, consistent with Section 9. |

4.  DATA & API CONTRACTS
| Coverage status | HIGH for the validate-and-handoff experience this version of T-08 is scoped to. apartmentlist and apartmentratedetails – V3 (the same orchestration used in T-04) confirm the room and rate are still bookable and source the summary card fields. bookingcart is a confirmed API that assembles a priced, validated cart representation (cartId, isAvailable, totalChargesIncludingTaxes) and is used to compose the external checkout link. The native-app write chain that completes an actual reservation — reservationV3 (v2 / v3-initiatereservation) and mobilev1/v2/confirmreservation — requires guest personal details (guestInformation) and payment or card details that this tool call intentionally does not collect, consistent with the stay-details-only decision in Section 1. This version of T-08 does not invoke these write APIs; it stops at constructing the external checkout link. See Open Question OQ-01. |

| API no. | API name | Primary role in this tool call |
| 1 | apartmentlist / apartmentratedetails – V3 | Confirms the selected room and rate (or, for a cold invocation, every candidate room and rate) is still bookable for the stated dates and guest count, and sources the room name, rate plan name, per-night and total stay rate, currency, and ASR points-earn estimate shown on the summary card. Same orchestration as T-04. |
| 2 | bookingcart | Assembles a priced, validated cart line for the resolved room and rate (roomTypeCode, ratePlanCode, checkinDate, checkoutDate, noOfadults, noOfchildren, currencyCode, voucherCode, promotionCode) and returns a cartId, an isAvailable flag, and totalChargesIncludingTaxes. Confirmed source for the total price shown on the summary card and, where supported, a reference carried into the external checkout link. See Open Question OQ-02. |
| 3 | reservationV3 (v2-initiatereservation / v3-initiatereservation) | Confirmed native-app API that initiates an actual reservation and returns a paymentURL, but requires guestInformation and cardDetails this tool call does not collect. Not invoked by this version of T-08. Its confirmed joinAndBook boolean parameter is the closest existing concept to ASR enrolment intent, but only within a full reservation-initiation call this tool call does not make. See Open Question OQ-03. |
| 4 | mobilev1/v2/confirmreservation | Confirmed native-app API that finalises a reservation already initiated via reservationV3. Not invoked by this version of T-08, for the same reason as above. |
| 5 | API GAP — EXTERNAL CHECKOUT DEEP LINK CONSTRUCTION | No confirmed API returns a ready-made, parameter-carrying URL to the ASR checkout website (discoverasr.com). Composing a URL, or equivalent handoff mechanism, that pre-fills propertyCode, apartmentCategoryCode, ratePlanCode, dates, guest count, currency, voucherCode / promotionCode, and enrollAsrOnCheckout on the receiving website is a genuine build item. See Open Question OQ-04. |

5.  INPUT PARAMETERS — LLM-to-API SCHEMA
| Input parameter (layman label) | Actual API parameter name | Type | Required / Optional | Assumed value when not provided | Constraints | Example |
| Property identifier | propertyCode | String | Required | — | Resolved by the LLM from a prior T-04/T-07 result, or from a stated property name for a cold invocation. | "50926" |
| Room identifier | apartmentCategoryCode | String | Optional | Resolved internally to the room with the lowest per-night rate, for a cold invocation | Carried from a prior T-04/T-07 result when a room has already been selected. | "CUTLER-STUDIO" |
| Rate plan identifier | ratePlanCode | String | Optional | Resolved internally alongside apartmentCategoryCode, for a cold invocation | Carried from a prior T-04/T-07 result when a rate has already been selected. | "FSMS" |
| Check-in date | checkinDate | String | Required | 30 days from current date, if not carried from context | Must be today or a future date. Must be before checkoutDate. Format: YYYY-MM-DD. | "2026-05-04" |
| Check-out date | checkoutDate | String | Required | 31 days from current date, if not carried from context | Must be after checkinDate. | "2026-05-13" |
| Guest count (adults) | noOfadults | String | Required | 1, if not carried from context | Carried from T-01/T-02/T-04/T-07 context where present. | "1" |
| Guest count (children) | noOfchildren | String | Required | 0, if not carried from context | — | "1" |
| Currency code | currencyCode | String | Optional | Currency associated with the user's region | Every value on the summary card and in the checkout link uses this one currency, consistent with T-01. | "SGD" |
| Voucher or promotion code | voucherCode / promotionCode | String | Optional | — | Carried from a prior T-05 result, or stated directly. Passed through to bookingcart and the external checkout link. | "PROMO2026" |
| ASR enrolment intent | enrollAsrOnCheckout — PARAMETER GAP | Boolean | Optional | false | Derived by the LLM from the user's stated intent, including ticking the inline checkbox. Passed as a parameter on the external checkout link. Whether the ASR website reads this into its own confirmed joinAndBook flag is unconfirmed. See Open Question OQ-03. | true |
| Member ID | memberId | String | Optional (auth param) | — | Required to reflect member rates and ASR points-earn accurately. Supplied via authentication context, not entered by the user. | "M123456" |

6.  OUTPUT PARAMETERS — API-to-UI RESPONSE SCHEMA
| Note | Lead with the common-sense UI requirements based on the data package mental model in Section 2.4, then map to the correct API response parameter names. Fields marked API GAP or PARAMETER GAP have no existing confirmed API response parameter. |

| Expected UI element | Actual response parameter name | Type | Assumed API source | Example value |
| Header copy and resolution context | Backend-composed meta object | Object | Assembled by the backend service layer | "Ready to book your stay?" |
| Property name | propertyName | String | apartmentratedetails – V3, bookingcart (echo) | "Ascott Raffles Place" |
| Hero image | bannerImageMobile | String (URL) | apartmentratedetails – V3 | [relative path] |
| Brand logo (watermark) | brandlogo | String (URL) | apartmentratedetails – V3 | [relative path] |
| Address | address | String | apartmentratedetails – V3 (echoed property fields) | "2 Finlayson Green, Singapore 049247" |
| Check-in / check-out dates | checkinDate, checkoutDate | String | bookingcart (echo) | "2026-05-04", "2026-05-13" |
| Guest count | noOfadults, noOfchildren | Integer | bookingcart (echo) | 1, 1 |
| Room name | apartmentName | String | apartmentratedetails – V3, bookingcart (echo) | "Cutler Suite Studio" |
| Rate plan name | ratePlanName | String | apartmentratedetails – V3, bookingcart (echo) | "First-Stay Member Special" |
| Total stay price | totalChargesIncludingTaxes | String (Decimal) | bookingcart | 1750.00 |
| Currency code | currencyCode | String | bookingcart, apartmentratedetails – V3 | "SGD" |
| Tax-inclusive note | isTaxInclusive | Boolean | apartmentratedetails – V3 | true |
| Free-cancellation deadline | cancellationDescription (parsed to a deadline display) | String | apartmentratedetails – V3 | "Free cancellation until 6:00 PM on 18 September 2026" |
| ASR points-earn estimate | earnASRpoints | String | apartmentratedetails – V3 | 6500 |
| Cart reference | cartId | String | bookingcart | 43064 |
| Availability confirmation flag | isAvailable | Boolean | bookingcart | true |
| ASR enrolment flag (carried into link) | enrollAsrOnCheckout | Boolean | LLM-derived (see Section 5) | true |
| External checkout URL | externalCheckoutUrl — API GAP, backend-composed | String (URL) | API GAP – backend service layer must construct | "https://www.discoverasr.com/checkout?..." |

6.1  ILLUSTRATIVE DATA PACKET — CANONICAL OUTPUT
| { "meta": { "property_code": "50926", "resolution_method": "selected", "checkin_date": "2026-05-04", "checkout_date": "2026-05-13", "noOfadults": 1, "noOfchildren": 1, "currency": "SGD" }, "property": { "property_name": "Ascott Raffles Place", "brand_logo_url": ".../logo-ascott-en.png", "banner_image_url": ".../ascott-raffles-place/banner.jpg", "address": "2 Finlayson Green, Singapore 049247" }, "room_and_rate": { "apartment_category_code": "CUTLER-STUDIO", "apartment_name": "Cutler Suite Studio", "rate_plan_code": "FSMS", "rate_plan_name": "First-Stay Member Special", "is_tax_inclusive": true, "cancellation_description": "Free cancellation until 6:00 PM on 18 September 2026", "earn_asr_points": 6500 }, "cart": { "cart_id": "43064", "is_available": true, "total_charges_including_taxes": 1750.00, "voucher_code": null, "promotion_code": null }, "enrollment": { "enroll_asr_on_checkout": false }, "checkout": { "external_checkout_url": "[pending] https://www.discoverasr.com/checkout?propertyCode=50926&apartmentCategoryCode=CUTLER-STUDIO&ratePlanCode=FSMS&checkin=2026-05-04&checkout=2026-05-13&adults=1&children=1&currency=SGD" } } |

7.  ERROR CONDITIONS & FALLBACK BEHAVIOUR
| No. | Error condition | LLM fallback response (illustrative) |
| ER-01 | The propertyCode cannot be resolved from the user's request or from context. | I need to know which property you would like to book. Could you name the property, or would you like me to help you find one first? |
| ER-02 | A cold invocation's internal room-and-rate lookup returns zero bookable rooms for the stated or default dates and guest count. | I could not find an available room at [property] for [date range]. Would you like to try different dates, or see the available rooms directly? |
| ER-03 | The API is unavailable or returns a 5xx error. | I am having trouble confirming this booking right now. Could you try again in a moment? You can also book directly at discoverasr.com. |
| ER-04 | The room and rate carried from an earlier T-04 or T-07 call are no longer available at the time T-08 is invoked (isAvailable is false). | That room and rate are no longer available for those dates. |
| ER-05 | The user states a check-in date in the past. | That check-in date has already passed. Could you provide a current or future date so I can confirm availability? |
|  |
| ER-07 | A stated voucher or promotion code is invalid, expired, or not applicable to this room and rate. | That code does not appear to apply to this booking. Would you like me to proceed without it, or check a different code? |
| ER-08 | The external checkout link cannot be constructed. | I was able to confirm this room and rate, but I could not generate a direct checkout link. You can complete this booking at [property name] for [date range] directly at discoverasr.com. |
| ER-09 | The user asks whether their booking succeeded after leaving for the external website. | I am not able to confirm the outcome of a booking once you have left for the ASR website. You should receive a confirmation email from Ascott, or you can check your booking in your ASR account. |

8.  ACCEPTANCE CRITERIA
| ID | Criteria |
| AC-01 Happy path, resolved room and rate | GIVEN a room and rate are already resolved from T-04 or T-07, WHEN the Create_booking tool call is invoked, THEN the system confirms availability and returns a booking summary and an external checkout link carrying the exact resolved room, rate, dates, and guest count. |
| AC-02 Cold invocation | GIVEN a user names a property with no room or rate yet selected, WHEN the tool call is invoked, THEN the LLM resolves the property, silently selects the cheapest available room and rate for the stated or default dates and guest count, and returns a booking summary on that basis. |
| AC-03 Availability re-check | GIVEN a room and rate were resolved in an earlier tool call, WHEN Create_booking is invoked, THEN the system re-confirms availability for that room and rate at the current dates and guest count before returning a summary, rather than assuming the earlier result still holds. |
| AC-04 No available room | GIVEN a cold invocation's internal lookup returns no bookable room, WHEN the tool call is invoked, THEN the LLM surfaces ER-02 and does not fabricate a room, rate, or checkout link. |
| AC-05 Voucher carry-forward | GIVEN a voucherCode or promotionCode is present from an earlier T-05 result or stated directly, WHEN the tool call is invoked, THEN the code is passed through to bookingcart and reflected in the total price and the external checkout link. |
| AC-06 ASR enrolment flag | GIVEN the user states an intent to join ASR as part of this booking, WHEN the booking summary is generated, THEN enrollAsrOnCheckout is set to true and carried into the external checkout link. |
| AC-07 Currency consistency | GIVEN a response is composed, WHEN the summary card renders, THEN every price field (total, and any rate context) displays the one resolved currencyCode, consistent with T-01. |
| AC-08 No write performed | GIVEN the tool call is invoked with any combination of inputs, WHEN it completes, THEN no reservation, cart hold, or payment is created or committed in the Ascott system; a checkout summary and external link are the only outputs. |
| AC-09 Re-invocation on date or guest change | GIVEN a booking summary has already been returned, WHEN the user states new dates or a new guest count, THEN the tool call is re-invoked with the updated values and a fresh availability check is run before a new summary is shown. |
| AC-10 External handoff | GIVEN the user taps “Book now on ASR website”, WHEN the action is triggered, THEN an external link opens carrying the resolved propertyCode, apartmentCategoryCode, ratePlanCode, dates, guest count, currency, voucher/promotion code, and ASR enrolment flag, so none of these must be re-entered. |
| AC-11 API unavailable | GIVEN the underlying API is unavailable, WHEN Create_booking is attempted, THEN the LLM surfaces ER-03 and does not return an invented summary or checkout link. |

9.  SIDE EFFECTS
| Tool call type | READ-ONLY. This version of Create_booking does not create, hold, or commit a reservation, a cart, or a payment in the Ascott system. It validates availability and constructs an external checkout link only. It is safe to invoke multiple times with the same parameters. |
| Reversibility | Not applicable. This tool call has no side effects to reverse. |
| Authentication | Authentication is not required for a standard availability check and checkout link. When memberId is present, member rates and an accurate ASR points-earn estimate are reflected in the summary. |
| Performance note | The base orchestration calls apartmentlist and apartmentratedetails – V3 (as in T-04) to confirm availability, followed by bookingcart to obtain a priced, validated cart line. For a cold invocation, the room-and-rate lookup runs across every candidate room at the property before the cheapest bookable option is selected, which adds latency relative to a downstream invocation with an already-resolved room and rate. |
| Limitations | This tool call does not collect guest personal details or payment information, and does not invoke reservationV3 or confirmreservation. Booking completion, and its outcome, happen entirely on the external ASR checkout website and are not visible to this tool call or the conversation. Multi-room bookings are out of scope for this version; each room is booked through a separate Create_booking handoff. Saved-payment shortcutting is out of scope and logged for a future iteration. |

10.  EDGE CASES
| ID | Condition | System response |
| EC-01 | A cold invocation resolves a property with more than one room at the same lowest per-night rate. | The LLM selects the first such room by ranking (consistent with T-04's ranking field) and proceeds. This is not surfaced to the user as a choice unless they ask to see other rooms. |
| EC-02 | The room and rate carried from T-04 or T-07 belong to a property that no longer matches the stated dates or guest count (for example, the user changed dates earlier in the conversation without revisiting T-04). | The tool call re-confirms availability at the current dates and guest count. If unavailable, ER-04 is surfaced rather than assuming the earlier context still applies. |
| EC-03 | The user ticks the ASR enrolment checkbox after a summary has already been shown. | The external checkout link is updated to carry enrollAsrOnCheckout = true, per the mechanism confirmed in Open Question OQ-05. |
| EC-04 | A voucher or promotion code reduces the total to a value bookingcart cannot validate (for example, an expired code). | The code is not applied. The LLM surfaces ER-07 and shows the standard total instead of a fabricated discounted total. |
| EC-05 | The property's cancellation policy has no free-cancellation window (fully non-refundable rate). | The free-cancellation deadline line is omitted rather than shown as blank or fabricated. The LLM does not imply a cancellation window that does not exist. |
| EC-06 | The user asks to book more than one room in the same request. | This tool call books a single room and rate per invocation. The LLM informs the user that each room requires its own Create_booking handoff, consistent with the single-room scope logged in Section 9. |
| EC-07 | The hero image or brand logo is unavailable for the resolved property. | The summary card renders without the affected image. A placeholder is shown. The LLM does not fabricate or source an image from outside the API. |
| EC-08 | The user taps “Book now on ASR website” more than once in quick succession. | Each tap opens the same external checkout link. No duplicate reservation, cart, or charge is created by this tool call, since no write action originates here. |

11.  SUCCESS METRICS
| ID | Metric | Verification method |
| SM-01 | The tool call is invoked only when a valid propertyCode is resolved, whether carried from context or from a direct user request. | QA test: verify the tool call is not fired without a resolved propertyCode. |
| SM-02 | A cold invocation correctly selects the room and rate with the lowest per-night rate for the stated or default dates and guest count. | Integration test: compare the selected room and rate against the full candidate set returned by the underlying room-and-rate lookup. |
| SM-03 | Availability is re-confirmed at the time of invocation, even when a room and rate were resolved earlier in the conversation. | Integration test: simulate a room and rate becoming unavailable between an earlier T-04 call and the T-08 call, and verify ER-04 fires rather than a stale summary being shown. |
| SM-04 | The external checkout link carries every resolved parameter (property, room, rate, dates, guest count, currency, voucher/promotion code, and ASR enrolment flag) without omission. | Integration test: parse the generated link and confirm each expected parameter is present and correctly valued. |
| SM-05 | No reservation, cart hold, or payment is committed in the Ascott system as a result of this tool call alone. | Manual review and system audit: confirm no write-side API (reservationV3, confirmreservation) is called by this tool call in any test scenario. |
| SM-06 | Every price shown in the summary displays the one resolved currency. | UI regression test: assert no summary contains more than one currency code. |
| SM-07 | Error conditions ER-01 through ER-09 produce the correct fallback response and no fabricated data. | Test suite: simulate each error condition and assert the correct fallback message. |
| SM-08 | A stated date or guest-count change correctly re-invokes the tool call and produces an updated, re-validated summary. | Integration test: change dates after an initial summary and confirm a fresh availability check runs before the new summary is shown. |

12.  OPEN QUESTIONS
| ID | Question | Owner | Status |
| OQ-01 | Is a future, write-capable version of Create_booking in scope, where reservationV3 (initiatereservation) and mobilev1/v2/confirmreservation are invoked directly with guest and payment details collected in-conversation? This version intentionally stops short of that. See Section 4 and Section 9. | Product | Open — for future roadmap |
| OQ-02 | Does bookingcart's cartId persist long enough, and is it accepted as a reference parameter, by the external ASR checkout website (discoverasr.com), or does the checkout page re-derive its own cart from the URL parameters independently? | Integration Architect / API Owner | Open |
| OQ-03 | Can the ASR enrolment intent (enrollAsrOnCheckout) be passed as a link parameter that the ASR checkout website reads into its own confirmed joinAndBook flag on v2/v3-initiatereservation, or does the website require the user to tick its own equivalent checkbox regardless of what this tool call passes? | API Owner / Product | Open — confirmed parameter gap |
| OQ-04 | What is the confirmed URL structure, domain path, and parameter-encoding scheme for the external checkout deep link to discoverasr.com? No confirmed API currently returns a ready-made link. | Integration Architect / API Owner | Open — confirmed API gap, build required |
| OQ-05 | When the user ticks the ASR enrolment checkbox after the summary card has already rendered, can the checkout link be recomputed client-side from already-returned data, or does this require a silent re-invocation of Create_booking to regenerate a signed or backend-composed link? | Integration Architect | Open |
| OQ-06 | Is there a confirmed mechanism for the ASR checkout website to notify the conversation, or the wider Claude/MCP session, that a booking was completed (for example, a return deep link or webhook), or is booking outcome permanently invisible to this system as assumed in Section 9? | Product / API Owner | Open — for future roadmap |
| OQ-07 | Does apartmentratedetails – V3's cancellationDescription field reliably parse into a single free-cancellation deadline line (date and time), or does the backend service layer need additional logic to extract this from free-text policy content? | API Owner | Open |
| OQ-08 | Is a multi-room Create_booking handoff (bundling more than one room from a single T-04 multi-room result into one checkout link) planned for a future version, consistent with the single-room scope decision logged in Section 9? | Product | Open — for future roadmap |

