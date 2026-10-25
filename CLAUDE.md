# asc-mcp-odx-backend-xapi: working context

Read this before changing anything in this repo. It is the agreed context for the Ascott MCP experience API.

## Source of truth

- **Base code: `asc-mcp-odx-backend-xapi/`.** It holds the files the owner sent from the deployed app (2026-10-25). Fix and extend only these files.
- `ascott.mcp.get-property-details.xapi/` is the older reference project that the base grew out of. Use it only to look up the DataWeave files the base still needs (see "Not yet in the base"). Do not edit it for new work.
- Branch `claude/property-details-xapi-v3` / PR #1 is a separate project from another session. It is not this app.
- The owner edits in Anypoint Studio and deploys by hand. Their copy can be ahead of this repo. When a log disagrees with the repo, ask for the deployed file instead of assuming.
- `global-config.xml` here has its two truststore passwords and the secure-properties key replaced with `REDACTED`. The real values live only in the owner's project. Never commit secrets: no client IDs, client secrets, passwords or keys from `uat.yaml`.

## Runtime

| Item | Value |
|---|---|
| CloudHub app | `asc-mcp-odx-backend-xapi-1`, region ap-southeast-1, Mule 4.13.1, Java 17 |
| Earlier app name | `loldging-odx-mcp-xapi-1` (typo; old logs use it) |
| Listener | `common_HTTP_Listener_Config`, host `0.0.0.0`, port `${http.port}` (CloudHub sets 8081) |
| Properties | `uat.yaml` via `configuration-properties`, `mule-env` = `uat`; secure properties `config-secured-${mule-env}.yaml` |
| Network | Upstream hosts are `mule-worker-internal-*.sg-s1.cloudhub.io:8093`: reachable only inside the CloudHub VPC, not from a laptop or this sandbox |
| Auth | None on the listener: non-logged-in journey, no user or member data |

## Endpoints (all POST, JSON)

| Tool | Path | Flow file | Response schema |
|---|---|---|---|
| T-02 `get_property_details` | `/api/v1/property-details` | `get-property-details.xml` | `schemas/T02-get-property-details.structured-content.schema.json` (0.5.0) |
| T-03 `get_service_offerings` | `${t03.http.path}` (`/api/v1/service-offerings`) | `get-service-offerings.xml` | `schemas/T03-get-service-offerings.structured-content.schema.json` (0.1.0) |
| T-04 `get_room_rate_details` | `/api/v1/room-details` | `get-room-rates.xml` | `schemas/T04-get-room-rate-details.structured-content.schema.json` (0.1.0) |

Every response body is the tool's `structuredContent`, exactly as its schema defines it. Errors are `{success: false, correlationId, error: {category, code, message, retryable}}`. The caller's `X-Correlation-ID` (`^[A-Za-z0-9_-]{1,80}$`) is reused as `vars.traceId` and returned as a header.

## Files in the base and what they define

| File | Defines | Notes |
|---|---|---|
| `global-config.xml` | `common_HTTP_Listener_Config`; `HTTP_Request_Bookingsearch_config` (`https.bookingsearchprocessapi.*`, TLS insecure, config-level validator `${validation.successcodes}`); `Property_POI_HTTP` and `HTTP_Request_POI_System_config` (`poisystem.*`); `HTTP_Request_configuration_InternalCommonServices`; plus AEM configs `HTTP_Request_configuration1` / `HTTPS_Request_configuration-dynamic`, the caching strategy and the object store. | The AEM configs, the commonservices config, the caching strategy and the object store are not used by T-02/03/04. |
| `validate-request.xml` | `common-validate-request`: runs `dwl/validate-request.dwl` and sets `vars.validation` and **`vars.request`**; raises `APP:BAD_REQUEST`. | It catches every `MULE:EXPRESSION` error as "Request body must be valid JSON.", which hides missing-property errors. The real reason is in the ERROR log line `validate-request.dwl failed: …`. |
| `get-common-details.xml` | `get-property-common-info`: builds the body from `dwl/property-info-request.dwl` (reads **`vars.request`**), logs `xapi.bookingsearch.request`, POSTs booking search, 404 → `APP:NOT_FOUND`, `dwl/unwrap-property.dwl` → **`vars.property`** (the `propertyList[0]` object), logs `xapi.property.response` (field names only). It raises `APP:NOT_FOUND` when the response has no code or name. | This is the shared booking search call. |
| `get-poi-details.xml` | `get-property-pois`: only when `vars.request.maxPois > 0`; `dwl/poi-request.dwl`, POST `${poisystem.path}` via `Property_POI_HTTP` → `vars.pois`. Any error → `vars.pois = null`, logged as `xapi.poi.unavailable`. | Optional: never fails the call. |
| `get-property-details.xml` | Flow `get-property-details` (T-02): `common-validate-request` → `get-property-info` → `vars.propertyCode` → `get-property-pois` → `dwl/map-structured-content.dwl` → `xapi.success`; error handler `property-details-error-handler`. Sub-flow `get-property-info` = `get-property-common-info`, then unwraps, logs and checks again. | Its old `validate-request` and `get-property-pois` copies are commented out (moved to `validate-request.xml` / `get-poi-details.xml`). |
| `get-service-offerings.xml` | Flow `get-service-offerings` (T-03; sets `vars.toolName`): `services-validate-request` (parses the body first, so only bad JSON gives "invalid JSON"; requires a digits-only `propertyCode`; adds a default stay from `default.*`) → **`vars.servicesRequest`**. Then `services-get-facilities` copies it into `vars.request`, calls booking search **itself** (not via `get-property-common-info`) and selects the `propertyList` entry → **`vars.servicesSource`**. Then `services-map-response` (inline DataWeave, `t03.assetbaseurl`) → `{meta, services[]}`. Error handler `property-details-error-handler`. | Its header comment is out of date (it names `Property_Info_HTTP` and `property.*`; the flow uses `HTTP_Request_Bookingsearch_config` and `https.bookingsearchprocessapi.*`). |
| `get-room-rates.xml` | Flow `get-room-details`; sub-flows `rooms-get-rates`, `rooms-map-response`; `rooms-error-handler`; `rooms-format-and-log-error`. | See the known issues below. |

## Booking search contract (confirmed against UAT)

`POST /v3/checkpropertyavailability` (**PUT returns 405**). Headers: `client_id` / `client_secret` from `https.bookingsearchprocessapi.clientid` / `clientsecret`, `messageId` = `vars.traceId`, `country` = `default.userCountry` (else "SG"). The body is the format of the reference caller `ODX_Booking_Search_Result_Apartment_Rate_Details_V3.xml` (repo root):

```
messageId, memberId "", language, currencyCode, promoCorpCode "", propertyListing false, isModifyJourney false,
propertyCode ["<code>"], checkinDate, checkoutDate (yyyy-MM-dd), voucherCode "", noOfRooms 1,
noOfadults "n", noOfchildren "n", minPrice "", maxPrice "", perNightRate true,
apartmentList [{childAges [], noOfadults, noOfchildren}], userCountry, isExcludePriceStartFrom false, channel "mobile"
```

What UAT showed:

| Request | Result |
|---|---|
| No `userCountry` | **500** (its minBaseRate crashes) |
| Old field names (`checkin`, `adults`, …) or an empty body | 400 `{"message": "Bad request"}` |
| Wrong credentials, or the AEM host instead of booking search | 401 |
| `channel` "mcp" | matches no rate plans; rates are tagged MOBILE / WEB |

Response: `{messageId, propertyList: [ {…} ]}`. One property has `propertyCode, propertyName, brandName, brandlogo, countryCode, countryName, city, cityName, propertyType, checkInTime, checkOutTime, currency, perNightRate…, apartments, facilities, gallery, location, staffLanguages, …`, as logged by `xapi.property.response`.

- **T-03** reads `facilities.facilityDetails[]` (`title, location, operatingHours, description, thumbnailImage, facilityUrl`).
- **T-04** reads `apartments[].room0[]`:
  - room fields: `apartmentType, apartmentName, apartmentCategoryCode, ranking, roomInformation, bedType, maxPersonInRoom, maxOccupancy, dimension, noOfUnitRemaining, thumbnailImage, bannerImageMobile, floorPlanPath, imageGalleryItems[]{path, galleryImage, galleryType}, amenityGroups[]{refAmenityGroup, amenities[]{description|name}}`;
  - rate fields `ratePlan[]`: `ratePlanCode, ratePlanName, ratePlanDescription, ratePlanTemplate, ratePlanTemplateName, ratePlanChannel, totalStayRatePrefCurr, totalTaxPrefCurrency, strikethroughRatePrefCurr, savePercentage, earnASRpoints, nonRefundable, cancellationDescription, nightly_rate[]`.

## Mapping rules that are settled

- **T-04 prices include tax:** `total_stay_rate` = `totalStayRatePrefCurr` + `totalTaxPrefCurrency`, and `per_night_rate` = that ÷ nights. This equals upstream `nightly_rate.price_with_tax_and_fee`.
- **T-04 strikethrough:** upstream `strikethroughRatePrefCurr` is for the **whole stay** before tax, so per night = strike × (total ÷ stay) ÷ nights. It is kept only when above `per_night_rate`.
- **T-04 bookable rates:** drop template `AOA` or "…Member…" rates (need a login) and names containing "ACRS Compare". Sort cheapest first, sort rooms by `ranking`, drop rooms with no rates. `noOfRooms` is always 1.
- **T-04 `meta.currency`** = the request currency, else `property.currency`.
- **T-03:** one service per `facilityDetails` item in upstream order, `title` → `service_name`, empty fields left out. `services: []` is valid.
- **All tools:** leave out null and blank optional fields (`skipNullOn="everywhere"`). Pass upstream text through verbatim, HTML included. Convert numeric strings to numbers where the schema says number.
- The reference implementation of these rules is `ascott.mcp.get-property-details.xapi/src/main/resources/dwl/room-rate-details.dwl` (T-04). Expected outputs that validate against the schemas are in `ascott.mcp.get-property-details.xapi/examples/` (`room-rate-details-*.sample.json`, `service-offerings-response.sample.json`). `tests/check_contracts.py` there checks them.

## Properties the flows read

- Booking search: `https.bookingsearchprocessapi.{host, port, basepath, path, keystorepwd, clientid, clientsecret, responsetimeout}`, `validation.successcodes`.
- POI: `poisystem.{host, port, protocol, basepath, path, clientid, clientsecret, responsetimeout, reconnection.*}`. The keys are **lower case**.
- Request defaults: `default.{language, currency, adults, children, checkinOffsetDays, nights, userCountry}`, `request.{maxAdults, maxChildren, maxNights}`, `app.{version, channel}`, `rooms.maxRooms`, `property.currency`, `asset.baseUrl`, `t03.*`.
- A missing key read with `p()` gives null, and `null as Number` fails the request. `uat.yaml` has `startdate: 7`, `enddate: 8`, `noofadults: 2`, the defaults other booking search callers use. A check-in of tomorrow in UTC can already be "today" in Singapore.

## Known issues in the base (2026-10-25)

`get-room-rates.xml`:
1. It validates with `common-validate-request`, which sets `vars.request` without `nights` or `rooms`. Its own `rooms-validate-request` is commented out, so **`vars.roomsRequest` is never set**. `rooms-get-rates` (roomsSource selection) and `rooms-map-response` read `vars.roomsRequest`, so dates and nights come out null.
2. `rooms-map-response` is still the **old flat mapping** (`apartments[]`, `apartment_count`), not the T-04 schema. Replace its body with `<ee:set-payload resource="dwl/room-rate-details.dwl"/>`, which needs `vars.roomsSource` and `vars.roomsRequest` (with `nights`).
3. The `T04.success` logger reads `payload.property_code` / `payload.apartment_count`; for T-04 use `payload.meta.*`.
4. No `vars.toolName`, so shared loggers label T-04 lines `get_property_details`.
5. `rooms-error-handler` has no `HTTP:BAD_REQUEST` branch (a 400 shows as `DOWNSTREAM_UNAVAILABLE`) and doesn't log the downstream body.
6. Duplicate request-building: `rooms-get-rates` repeats the booking search call that `get-property-common-info` already makes.

`get-property-details.xml` (T-02, working in UAT):
7. `get-property-info` repeats what `get-property-common-info` already does (unwrap into `vars.property`, the `xapi.property.response` log and the not-found check), so each call logs `xapi.property.response` twice. Harmless; drop the repeat when convenient.

`get-service-offerings.xml` (T-03):
8. It has its own copy of the booking search request. That makes three copies (T-02 via `get-property-common-info`, T-03 and T-04), all of which must stay identical; a fix to one must go to all three, or T-03/T-04 should call `get-property-common-info`.
9. Its stay is always the default (today + `default.checkinOffsetDays`, `default.nights` nights, `default.adults` adults). If booking search has no availability for that stay, there is no `propertyList` and the call returns 404, even though facilities don't depend on dates.

`global-config.xml`: every truststore is `insecure="true"`; the secure-properties key and two truststore passwords are hardcoded (REDACTED here); `uat.yaml` is loaded twice (`uat.yaml` and `${mule-env}.yaml`). There are also two POI request configs.

POI: the Anypoint mock (`/mocking/api/v1/links/7f9e4e4b-…/getpropertypois`) answers 400 for real property codes, so `nearby[]` is always omitted for now.

## Not yet in the base (ask for these before relying on them)

- The error-handler file that defines `property-details-error-handler`, which T-02 and T-03 reference.
- `src/main/resources/dwl/*`: `validate-request.dwl`, `property-info-request.dwl`, `unwrap-property.dwl`, `poi-request.dwl`, `map-structured-content.dwl` (T-02) and `room-rate-details.dwl` (T-04). Until the deployed versions arrive, assume the versions in `ascott.mcp.get-property-details.xapi/src/main/resources/dwl/` at commit `76aa457`.
- `uat.yaml` (share without secrets) and `pom.xml`.

## Product specs (PRDs) for tools not yet built

Full text: `asc-mcp-odx-backend-xapi/docs/PRD-T05-get-promotions.md` and `PRD-T06-compare-properties.md`. Read the full PRD before you build either tool. No flow or schema exists for T-05 or T-06 yet. Build one only when asked.

Tool map from the PRDs:

| Tool | Name | Status in this app |
|---|---|---|
| T-01 | Search properties | not in this app |
| T-02 | Get_property_details | built |
| T-03 | Get_service_offerings | built |
| T-04 | Get_room_rate_details | built (issues 1–6) |
| T-05 | Get_promotions | PRD only |
| T-06 | Compare_properties | PRD only |
| T-07 | Compare_rooms_rates | not specified here |
| T-08 | Create_booking | not specified here |

Rules for both tools:

- Read only. One inline component per response, built from one data packet: `meta`, `recommendation` and a list.
- The xAPI must not let an LLM invent facts. A new backend scoring and explanation service computes boolean `match_flags`. That service has no API yet. Reasons or chips are shown only for flags that are `true`.
- One resolved currency for every card in a response.
- 14 Sept note: the OpenAI prose must always agree with, and explain, the tool output.

### T-05 Get_promotions

**Inputs:**

- `countryCode` (required), `city`, `propertyCode`.
- `checkinDate` (default today), `checkoutDate`.
- `noOfadults` (default 1), `noOfchildren` (default 0), `currencyCode`.
- `voucherName`.
- `voucherCategory[]`: API GAP, no enum source.
- `maxPrice`: PARAMETER GAP, filter after retrieval.
- `memberId`: optional here, although the consumer app treats it as mandatory (OQ-07).

**Upstream APIs:**

- `searchvoucher` (`odx/mobilev1/v1/searchvoucher`), the main source. Fields: `voucherTitle`/`voucherEnTitle`, `category`, `imageThumbnail`, `propertyCode`, `country`, `expiryDate`, `basePrice`/`promoPrice`, `preferredCurrencyPromoPrice`, `promoPercentage`, `points`, `isEndingSoon`, `voucherUrl`.
- `getvoucherdetail`: optional extra detail (OQ-04).
- Booking search, for rate discounts, when a property and dates are resolved. Fields: `strikethroughRate`, `perNightRatePrefCurr`, `isPromoCodeApplied`/`isVoucherCodeApplied`. This is the same `/v3/checkpropertyavailability` call T-02/T-03/T-04 make. Reuse `get-property-common-info`.
- `filtercountrycache` / `filtercitycache`.
- The scoring service.

**Output packet:**

- `meta {location_query, resolved_property_code, total_results, applied_filters, attribution}`.
- `recommendation {recommended_offer_id, recommendation_text, match_flags {matches_property, discount_percentage, matches_dates, is_lowest_eligible_rate}, reason_chips[{icon, label}]}`.
- `offers[] {offer_id, promotion_type ("voucher" | "rate_discount"), offer_title, image_thumbnail, is_best_match, is_ending_soon, scope {property_codes[], scope_label}, expiry_date, discount {promo_percentage}, pricing {promo_price, points, currency}, external_offer_url}`.

**Key checks:**

- Exactly one offer has `is_best_match`. Zero results is a valid response, not an error.
- Ties are broken by a defined rule (EC-07).
- Voucher and rate-discount offers need a common scale for comparison (OQ-09).
- How `external_offer_url` is built for each promotion type is open (OQ-05).

### T-06 Compare_properties

**Inputs:**

- `propertyCodes[]`: 2–4, required.
- `checkinDate` (default today + 30), `checkoutDate` (default today + 31).
- `noOfadults` (default 1), `noOfchildren` (default 0), `currencyCode`.
- `facilities[]`.
- `maxRate`: PARAMETER GAP.
- `roomType`: API GAP.
- `poi`: API GAP, no POI proximity API. Note that our `get-property-pois` mock only lists POIs.
- `travellerProfile`: derived by the LLM.
- `serviceCategory`: deferred (OQ-07; T-03 data could fill it).
- `memberId`.

**Upstream APIs:**

- `bookingpropertylist`.
- `bookingsearchresultv2`.
- `v1/propertyreviews`.
- `apartmentlist`.
- `getpropertyinfo`.
- The scoring service.
- POI API: not yet available.

**Mapping into this app:** the booking search data T-02/T-04 already map covers most of each card. T-04 supplies rates and rooms; T-02 supplies name, images, location and amenities. Call it once per property.

**Output packet:**

- `meta {total_results, location_query, currency, checkin_date, checkout_date, noOfadults, noOfchildren, attribution}`.
- `recommendation {recommended_property_code, traveller_profile_label, recommendation_text, match_flags, reason_lines[{icon, label}]}`.
- `properties[] {property_code, property_name, is_recommended, brand_logo_url, banner_image_url, card_location_line, rating {average_ratings, total_number_of_reviews}, location {area_label, district_label}, max_person_in_room, room_types[], amenity_highlights[], pricing {per_night_rate_pref_curr, strikethrough_rate, currency}}`.
- The source of `isASR` is unknown.

**Key checks:**

- Every card has the same fields. Use an explicit "unavailable" state; never leave a field out.
- A property with no rate shows "Availability on request" and the next available date.
- An excluded property must carry a stated reason.
- "See room and rates" hands off to T-04 with the same dates and guests (AC-09, OQ-05).
- Ties are broken by a defined rule (EC-05, OQ-08).

## How to work on it

- Diagnose from the audit log lines: `xapi.start` / `T04.start`, `xapi.bookingsearch.request` (exact body sent), `xapi.property.response` (upstream field names), `xapi.downstream.error` (upstream status and body), `xapi.poi.unavailable`, `xapi.failure`.
- Check any response change against the tool's schema, using a sample built from real upstream data where possible.
- Hand back complete, drop-in files with the owner's config names (`common_HTTP_Listener_Config`, `HTTP_Request_Bookingsearch_config`, `Property_POI_HTTP`) and key names (`https.*`, `poisystem.*`, `t03.*`).
- Commit to branch `claude/get-property-details-xapi`.
