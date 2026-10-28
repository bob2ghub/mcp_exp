# asc-mcp-odx-backend-xapi: working context

Read this before changing anything in this repo. It is the agreed context for the Ascott MCP experience API.

## Source of truth

- **Base code: `asc-mcp-odx-backend-xapi/`.** It holds the files the owner sent from the deployed app (2026-10-25). Fix and extend only these files.
- `ascott.mcp.get-property-details.xapi/` is the older reference project that the base grew out of. Use it only to look up the DataWeave files the base still needs (see "Not yet in the base"). Do not edit it for new work.
- **Second app: `asc-mcp-server/`.** The MCP tool-call server the owner sent on 2026-10-26. It is a *different* Mule app from the xAPI: it hosts the MCP server and the ChatGPT widget, and calls a backend over HTTP. See "The MCP server app" below. Only three of its files are here; do not assume anything else about it.
- **Third app: `lodging-odx-bookingsearch-xapi/`.** The booking search experience API the owner sent on 2026-10-26, the one our xAPI calls. Three files: `global.xml`, `bookingsearch-xapi.xml`, `papi-client.xml`. See "The booking search xAPI" below. Its commented-out secure-properties key is `REDACTED` here.
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
| T-02 `get_property_details` | `/api/v1/property-details` | `get-property-details.xml` | `schemas/T02-get-property-details.structured-content.schema.json` (**0.6.0**, owner's file 2026-10-26); input `schemas/T02-get-property-details.input.schema.json` (**0.2.0**, owner's file 2026-10-28) |
| T-03 `get_service_offerings` | `${t03.http.path}` (`/api/v1/service-offerings`) | `get-service-offerings.xml` | `schemas/T03-get-service-offerings.structured-content.schema.json` (0.1.0) |
| T-04 `get_room_rate_details`, one or several rooms | `/api/v1/multi-room-details` (`?format=raw` returns the unmapped property) | `get-multi-room-rates.xml` | `schemas/T04-get-room-rate-details.structured-content.schema.json` (**0.3.0**, owner's file 2026-10-26) |
| T-05 `get_promotions` (vouchers only) | `/api/v1/promotions` | `t05-get-promotions.xml` | `schemas/T05-get-promotions.structured-content.schema.json` (**0.2.0**, owner's file 2026-10-28); input `schemas/T05-get-promotions.input.schema.json` (0.1.0) |
| T-07 `compare_rooms_rates` | `/api/v1/compare-rooms` | `t07-compare-rooms.xml` | `schemas/T07-compare-rooms-rates.structured-content.schema.json` (**0.4.0**, owner's file 2026-10-28) |
| T-08 `create_booking` | `/api/v1/create-booking` | `t08-create-booking.xml` | `schemas/T08-create-booking.structured-content.schema.json` (**0.1.0**, owner's file 2026-10-28); input `schemas/T08-create-booking.input.schema.json` (0.1.0) |

`/api/v1/room-details` (the old single-room T-04) **no longer exists** once `t07-compare-rooms.xml` replaces `get-room-rates.xml`.
| T-06 `compare_properties` | `${t06.http.path}` (`/api/v1/compare-properties`) | `compare-properties.xml` | `schemas/T06-compare-properties.structured-content.schema.json` (**0.1.0**, owner's file 2026-10-27) |

Every response body is the tool's `structuredContent`, exactly as its schema defines it. **Every listener now forces the body to JSON** (`<http:body>#[output application/json --- payload]</http:body>` plus a `Content-Type: application/json` header, on both `http:response` and `http:error-response`, added 2026-10-27): without it a payload that is still a Java object is written to the wire as Java serialization bytes (`java.util.LinkedHashMap…`), which is what UAT returned for T-02 on 2026-10-27. Errors are `{success: false, correlationId, error: {category, code, message, retryable}}`. The caller's `X-Correlation-ID` (`^[A-Za-z0-9_-]{1,80}$`) is reused as `vars.traceId` and returned as a header.

## Files in the base and what they define

| File | Defines | Notes |
|---|---|---|
| `global-config.xml` | `common_HTTP_Listener_Config`; `HTTP_Request_Bookingsearch_config` (`https.bookingsearchprocessapi.*`, TLS insecure, config-level validator `${validation.successcodes}`); `Property_POI_HTTP` and `HTTP_Request_POI_System_config` (`poisystem.*`); `HTTP_Request_configuration_InternalCommonServices`; plus AEM configs `HTTP_Request_configuration1` / `HTTPS_Request_configuration-dynamic`, the caching strategy and the object store. | The AEM configs, the commonservices config, the caching strategy and the object store are not used by T-02/03/04. |
| `validate-request.xml` | `common-validate-request`: runs `dwl/validate-request.dwl` and sets `vars.validation` and **`vars.request`**; raises `APP:BAD_REQUEST`. | It catches every `MULE:EXPRESSION` error as "Request body must be valid JSON.", which hides missing-property errors. The real reason is in the ERROR log line `validate-request.dwl failed: …`. |
| `get-common-details.xml` | `get-property-common-info`: builds the body from `dwl/property-info-request.dwl` (reads **`vars.request`**) **unless `vars.bookingSearchBody` is already set** (added 2026-10-27 for the multi-room flow; then that body is sent as is), logs `xapi.bookingsearch.request`, POSTs booking search, 404 → `APP:NOT_FOUND`, `dwl/unwrap-property.dwl` → **`vars.property`** (the `propertyList[0]` object), logs `xapi.property.response` (field names only). It raises `APP:NOT_FOUND` when the response has no code or name. | This is the shared booking search call. |
| `get-poi-details.xml` | `get-property-pois`: only when `vars.request.maxPois > 0`; `dwl/poi-request.dwl`, POST `${poisystem.path}` via `Property_POI_HTTP` → `vars.pois`. Nothing to fetch (`maxPois` 0), no POIs, a body that is not a JSON object / array, or **any** error in the sub-flow (request build, call, 4xx/5xx, timeout, unreadable body) → **`vars.pois = []`** (owner, 2026-10-28), so the response is still built, with `nearby: []`. The body is parsed inside the `try`, so bad JSON cannot fail the mapping later. Errors are logged at **ERROR** as `xapi.poi.unavailable` (status, error type, detail, first 1000 characters of the body); that logger has its own `try`, so logging cannot fail the call either. Success logs `xapi.poi.response`. | Optional: never fails the call. |
| `get-property-details.xml` | Flow `get-property-details` (T-02): `common-validate-request` → `get-property-info` → `vars.propertyCode` → `get-property-pois` → `dwl/map-structured-content.dwl` → `xapi.success`; error handler `property-details-error-handler`. Sub-flow `get-property-info` = `get-property-common-info`, then unwraps, logs and checks again. | Its old `validate-request` and `get-property-pois` copies are commented out (moved to `validate-request.xml` / `get-poi-details.xml`). |
| `get-service-offerings.xml` | Flow `get-service-offerings` (T-03; sets `vars.toolName`): `services-validate-request` (parses the body first, so only bad JSON gives "invalid JSON"; requires a digits-only `propertyCode`; adds a default stay from `default.*`) → **`vars.servicesRequest`**. Then `services-get-facilities` copies it into `vars.request`, calls booking search **itself** (not via `get-property-common-info`) and selects the `propertyList` entry → **`vars.servicesSource`**. Then `services-map-response` → `{meta, services[]}`; **changed by us 2026-10-26** from inline DataWeave to `<ee:set-payload resource="dwl/service-offerings.dwl"/>` (see "T-03 mapping"). Error handler `property-details-error-handler`. | Its header comment is out of date (it names `Property_Info_HTTP` and `property.*`; the flow uses `HTTP_Request_Bookingsearch_config` and `https.bookingsearchprocessapi.*`). |
| `t07-compare-rooms.xml` (**T-07, not yet deployed**; renamed 2026-10-28 from `get-room-rates.xml`, which was T-04 `/api/v1/room-details`: **delete `get-room-rates.xml` from the project**, since both define the same flow names) | Flow `compare-rooms-rates` (`vars.toolName` = `compare_rooms_rates`): `compare-rooms-validate-request` (`dwl/compare-rooms-validate-request.dwl` → **`vars.roomCodesRequest`**, then `multi-rooms-validate-request` → `vars.roomsRequest`) plus a one-room check → `multi-rooms-get-rates` → `compare-rooms-map-response` (`dwl/room-rate-details.dwl` → `vars.roomsT04`, then `dwl/compare-rooms-response.dwl`, then the two-room check) → `T07.success`. Own `compare-rooms-error-handler` / `compare-rooms-log-downstream` / `compare-rooms-format-and-log-error`. | **Depends on `get-multi-room-rates.xml`** (reuses its validate and get-rates sub-flows); deploy both. See "T-07 in this app" below. |
| `t08-create-booking.xml` (**added by us 2026-10-28, not yet deployed**) | Flow `t08-create-booking` (`vars.toolName` = `create_booking`): `create-booking-validate-request` (`dwl/create-booking-validate-request.dwl` → **`vars.bookingRequest`**) → `create-booking-get-rates` (inline body → `vars.bookingSearchBody`, then the shared `get-property-common-info` → `vars.roomsSource`) → `create-booking-resolve` (`dwl/room-rate-details.dwl` → `vars.roomsT04`, `dwl/create-booking-response.dwl` → `vars.bookingResult {problems, response}`) → `create-booking-add-ons` (optional) → `T08.success`. Also defines **`HTTP_Request_Bookings_config`** (`https.bookingsprocessapi.*`). Own `create-booking-error-handler` / `-log-downstream` / `-format-and-log-error`. | See "T-08 in this app" below. Needs the `https.bookingsprocessapi.*` keys even with add-ons off. |
| `get-multi-room-rates.xml` (**added by us 2026-10-27, not yet deployed**) | Flow `get-multi-room-details` (`vars.toolName` = `get_multi_room_rate_details`): `multi-rooms-validate-request` (the T-04 validator `dwl/rooms-validate-request.dwl`, plus a `noOfRooms` = `apartmentList` check) → `multi-rooms-get-rates` (inline DataWeave → `vars.bookingSearchBody`, then the shared `get-property-common-info`) → `multi-rooms-map-response`, or the raw property with `?format=raw`. Own `multi-rooms-error-handler` / `multi-rooms-log-downstream` / `multi-rooms-format-and-log-error` (since 2026-10-27, so `get-room-rates.xml` can be reworked for T-07). | Serves one room as well as several. See "T-04 multi-room" below. |
| `compare-properties.xml` (added by us 2026-10-25, not yet deployed) | Flow `compare-properties` (T-06; `vars.toolName` = `compare_properties`): `compare-validate-request` (`dwl/compare-validate-request.dwl`) → **`vars.compareRequest`** → `compare-get-properties` → **`vars.lookups`** → `compare-check-lookups` → `dwl/compare-properties-response.dwl`. Own `compare-error-handler` / `compare-format-and-log-error`. | See "T-06 in this app" below. |

## The booking search xAPI (`lodging-odx-bookingsearch-xapi/`, owner's files, 2026-10-26)

**A 1:1 pass-through proxy to the process API. It maps nothing.** This is the app our `HTTP_Request_Bookingsearch_config` talks to. Three files were shared; the RAML and the `dwl/` files were not.

| File | Defines |
|---|---|
| `global.xml` | `mule-env` = `uat`; `configuration-properties file="${mule-env}.yaml"` (loaded **once**, unlike our app); listener `XAPI_HTTP_Listener_config` (`0.0.0.0:${http.port}`); **`HTTP_Request_Bookingsearch_config`** — the same config name our app uses — HTTPS to `${https.bookingsearchprocessapi.host}:${port}` with `basePath=${…basepath}`, TLSv1.2, trust store `insecure="true"`, validator `${validation.successcodes}`; `apikit:config` for `api/bookingsearch-xapi.raml`. Secure properties are commented out. |
| `bookingsearch-xapi.xml` | Flow `bookingsearch-xapi-main`: listener on **`/api/*`** → `vars.messageId` = the inbound **`messageId` header**, else `uuid()` → APIkit router → `global-error-handler`. Then one flow per resource, each just `flow-ref call-papi`: **`post:\v1\checkpropertyavailability`**, **`post:\v1\apartmentratedetails`**, **`post:\v1\searchpropertyrate`**, **`post:\v3\checkpropertyavailability`**, **`post:\v3\acrsInvalidateCache`**, plus `get:\health`. |
| `papi-client.xml` | `call-papi`: `papiPath` = `attributes.maskedRequestPath` (so `/api/v1/x` → `/v1/x`, appended to the config's basePath), POSTs **with no `http:body` element, so the APIkit-validated payload goes through byte for byte**, forwards `attributes.queryParams`, accepts `100..599` and passes the status through, and turns a non-JSON 5xx into `{messageId, error: "PAPI:INTERNAL_ERROR", message}`. Headers to the PAPI: `Content-Type`, `client_id`, `client_secret`, `messageId` (= `vars.messageId`) and `userToken` when the caller sent one. Also `check-papi-health` (GET `/console/`, UP when the status is < 500 and not 401/403). |

**What this means:**

- **The RAML is the only gate.** Nothing in these files inspects or rewrites a request body, so whether a payload is accepted depends entirely on `api/bookingsearch-xapi.raml`. APIkit rejects a bad body with 400 before `call-papi` runs. **Ask for the RAML (and any schemas it references) before answering a question about what a given payload does.**
- **It forwards no `country` header,** so a caller that needs `userCountry` must put it in the body. (Our own `property-info-request.dwl` always sends `userCountry`, so T-02/03/04/06 are fine.)
- **`messageId` has two separate paths:** the header the PAPI sees comes from the inbound `messageId` header (else a fresh uuid), not from the body. A body `messageId` is simply passed through in the body.
- **`apartmentratedetails` is v1 only;** there is no `v3` version of it and no resource called `apartmentdetails`.
- **Path check for our app:** this listener is `/api/*`, so through this xAPI the full path for booking search is `/api/v3/checkpropertyavailability`, while our flows send `path="/v3/checkpropertyavailability"`. That works only if our `https.bookingsearchprocessapi.basepath` is `/api` (or if our app calls the PAPI directly). Confirm which, since the owner's `uat.yaml` is not in this repo.
- Do not confuse this app with `ODX_Booking_Search_Result_Apartment_Rate_Details_V3.xml` in the repo root. That file is an MCP-adapted *caller* which does map the body (it hardcodes `noOfRooms: 1`, takes the top-level guest counts from `apartmentList[0]` only when there is exactly one entry, and derives `userCountry` from a `country` header). None of that happens in this proxy.

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

- **T-04 prices (schema 0.3.0, 2026-10-26): passed through as upstream gives them.** `per_night_rate` = `perNightRatePrefCurr`, `total_stay_rate` = `totalStayRatePrefCurr`, on the basis `is_tax_inclusive` states, with the tax beside them: `per_night_tax` = Σ `taxes[].taxAmountPrefCurrPerNight`, `total_tax` = `totalTaxPrefCurrency` (both 0 on a tax-inclusive rate). `per_night_rate` + `per_night_tax` equals upstream `nightlyRate[].priceWithTaxAndFee`. **Earlier versions added the tax in; 0.3.0 does not.**
- **T-04 has no strikethrough** in 0.3.0 (no UI shows one), so `strikethrough_rate` and `save_percentage` are gone.
- **T-04 bookable rates:** drop template `AOA` or "…Member…" rates (need a login), names containing "ACRS Compare" and names with a `TEST` token (schema 0.3.0: "no test rates"; 51052 has 6 of them). Sort cheapest first, sort rooms by `ranking`, drop rooms with no rates.
- **T-04 `meta.currency`** = the request currency, else the property's `currency`, else a rate plan's `currency`, else `property.currency`, else `SGD`.
- **T-03:** one service per `facilityDetails` item in upstream order, `title` → `service_name`, empty fields left out. `services: []` is valid.
- **All tools:** leave out null and blank optional fields (`skipNullOn="everywhere"`). Pass upstream text through verbatim, HTML included. Convert numeric strings to numbers where the schema says number.
- The reference implementation of these rules is `ascott.mcp.get-property-details.xapi/src/main/resources/dwl/room-rate-details.dwl` (T-04). Expected outputs that validate against the schemas are in `ascott.mcp.get-property-details.xapi/examples/` (`room-rate-details-*.sample.json`, `service-offerings-response.sample.json`). `tests/check_contracts.py` there checks them.

## Properties the flows read

- Booking search: `https.bookingsearchprocessapi.{host, port, basepath, path, keystorepwd, clientid, clientsecret, responsetimeout}`, `validation.successcodes`.
- POI: `poisystem.{host, port, protocol, basepath, path, clientid, clientsecret, responsetimeout, reconnection.*}`. The keys are **lower case**.
- Request defaults: `default.{language, currency, adults, children, checkinOffsetDays, nights, userCountry}`, `request.{maxAdults, maxChildren, maxNights}`, `app.{version, channel}`, `rooms.maxRooms`, `property.currency`, `asset.baseUrl`, `t03.*`.
- T-08: optional `t08.{checkinOffsetDays (30), nights (1), addons.enabled ("false")}`; **required** `https.bookingsprocessapi.{host, port, basepath, responsetimeout, clientid, clientsecret}` (`src/main/resources/create-booking.yaml`).
- T-05: **required** `https.cprvprocessapi.{host, port, basepath, responsetimeout, clientid, clientsecret}`; optional `t05.detailsFallbackPath` (`src/main/resources/get-promotions.yaml`).
- T-06: `t06.{http.path, minProperties, maxProperties, checkinOffsetDays, nights, adults, children, batchLookup, batchSize, maxConcurrency, maxAmenityHighlights, maxRoomTypes}`, in `src/main/resources/compare-properties.yaml` (to append to `uat.yaml`).
- A missing key read with `p()` gives null, and `null as Number` fails the request. `uat.yaml` has `startdate: 7`, `enddate: 8`, `noofadults: 2`, the defaults other booking search callers use. A check-in of tomorrow in UTC can already be "today" in Singapore.

## Known issues in the base (2026-10-25)

`get-room-rates.xml` (as T-04; the file is T-07 since 2026-10-27, so these are history): **issues 1–6 were all fixed in our rewrite of 2026-10-26**. They were:
1. ~~It validated with `common-validate-request`, so `vars.roomsRequest` was never set and dates and nights came out null.~~ Fixed: its own `rooms-validate-request` runs `dwl/rooms-validate-request.dwl`.
2. ~~`rooms-map-response` held the old flat mapping (`apartments[]`, `apartment_count`).~~ Fixed: `<ee:set-payload resource="dwl/room-rate-details.dwl"/>` (schema 0.3.0).
3. ~~The `T04.success` logger read `payload.property_code` / `payload.apartment_count`.~~ Fixed: it reads `payload.meta.*` and sums `requested_rooms[].total_results`.
4. ~~No `vars.toolName`.~~ Fixed.
5. ~~`rooms-error-handler` had no `HTTP:BAD_REQUEST` branch and did not log the downstream body.~~ Fixed: a `DOWNSTREAM_REJECTED` (502) branch, and `rooms-log-downstream` logs `xapi.downstream.error` with the upstream status and the first 1000 characters of its body.
6. ~~`rooms-get-rates` repeated the booking search call.~~ Fixed: it calls `get-property-common-info`, so there are now three copies of that call, not four (see issue 8).

`get-property-details.xml` (T-02, working in UAT):
7. `get-property-info` repeats what `get-property-common-info` already does (unwrap into `vars.property`, the `xapi.property.response` log and the not-found check), so each call logs `xapi.property.response` twice. Harmless; drop the repeat when convenient.

`get-service-offerings.xml` (T-03):
8. It has its own copy of the booking search request. That makes three copies (T-02 and now T-04 via `get-property-common-info`, T-03, and T-06's `compare-batch-lookup`), all of which must stay identical; a fix to one must go to all three, or T-03 should call `get-property-common-info` as T-04 now does.
9. Its stay is always the default (today + `default.checkinOffsetDays`, `default.nights` nights, `default.adults` adults). If booking search has no availability for that stay, there is no `propertyList` and the call returns 404, even though facilities don't depend on dates.

`global-config.xml`: every truststore is `insecure="true"`; the secure-properties key and two truststore passwords are hardcoded (REDACTED here); `uat.yaml` is loaded twice (`uat.yaml` and `${mule-env}.yaml`). There are also two POI request configs.

POI: the Anypoint mock (`/mocking/api/v1/links/7f9e4e4b-…/getpropertypois`) answers 400 for real property codes, so `nearby[]` is always omitted for now.

## Not yet in the base (ask for these before relying on them)

- The error-handler file that defines `property-details-error-handler`, which T-02 and T-03 reference.
- `src/main/resources/dwl/*`: `property-info-request.dwl`, `unwrap-property.dwl` and `poi-request.dwl`. Until the deployed versions arrive, assume the versions in `ascott.mcp.get-property-details.xapi/src/main/resources/dwl/` at commit `76aa457`. (`map-structured-content.dwl` and `validate-request.dwl` for T-02 are now in the base: see "T-02 mapping" and "T-02 request" below.)
- **`property-info-request.dwl` sends `apartmentList[0].childAges: []`** even though T-02 now validates `childAges`: change it to `childAges: vars.request.childAges default []` in the owner's copy (T-03 / T-06 set no `childAges`, so they are unaffected).
- `uat.yaml` (share without secrets) and `pom.xml`.

## T-02 mapping (`dwl/map-structured-content.dwl`, written by us 2026-10-26, not yet deployed)

Maps `vars.property` (one `propertyList[]` entry; when that variable is not set, the payload itself: the booking search response or one property object, so it also works in a plain Transform Message, 2026-10-28) + `vars.pois` + `vars.request` to T-02 schema **0.6.0**. Same file name and inputs as the version the T-02 flow already references, so it is a drop-in replacement.

- **Checked against the real 51052 (Ascott Raffles Place) booking search response**, stored at `examples/upstream-property-details-51052.json`. `tests/check_t02.py` is a function-for-function Python copy that writes `examples/property-details-51052-response.sample.json` and runs 23 checks (that sample, no stay in the request, `childAges`, no rate, POIs, the best-rate text, a bare property); all validate against 0.6.0. Keep the two in step. The DataWeave itself has not been run here: a downloaded runtime may not be executed in this session. `tests/playground/map-structured-content.playground.dwl` + `-input.json` run it in the DataWeave Playground.
- **Rules worth knowing:**
  - `brand_code`: upstream `brand`, else slug of `brandName` ("Ascott The Residence" → `ascott-the-residence`). The 51052 response has no `brand` field.
  - `thumbnail_url` (required): `newPropertyThumbnail` → `bannerImageMobile` → first gallery image → first room's `thumbnailImage` / `bannerImageMobile` → `location.mapImage`.
  - **`pricing.currency`** = the request's currency (the `…PrefCurr` prices are in the currency booking search was asked for), else upstream `currency` (the property's own), else `default.currency`. **Fixed 2026-10-28:** it used upstream `currency` first, so a USD request was labelled SGD.
  - `pricing`: property-level `perNightRatePrefCurr` / `totalStayRatePrefCurr` (**ex-tax, as upstream gives them**; unlike T-04, which adds tax). `strikethrough_rate` comes from the rate plan whose per-night rate equals the lead-in (51052: `ASRAPPFX` 211.50 → 940.00), kept only when higher. No rate → `on_request`.
  - `based_on`: the request's stay; when the request has none, the first and last+1 `nightlyRate` dates (`MM/dd/yyyy`). `adults` ≥ 1 (default 1), `children` default 0. `child_ages` from `vars.request.childAges`, which `validate-request.dwl` sets since 2026-10-28.
  - `hotel_information.check_in_time` / `check_out_time`: upstream "03:00 PM" → "15:00" (schema is 24-hour).
  - `location`: coordinates are converted to numbers; `gettingToProperty` / `publicTransport` titles have upstream's `{0}` replaced with the property name.
  - `amenities.facility_groups` from `facilities.facilityGroup`: label = `description`, else `name` (e.g. "Residents' lounge" has a null description); rows without label or icon dropped; **de-duplicated within and across groups** (schema: "De-duplicated by the server"), so groups left empty disappear (51052: "Business Matters").
  - `reviews`: booking search has none → `{average_ratings: 0, total_number_of_reviews: 0}`, kept as an empty shell.
  - `nearby`: from `vars.pois`, max 5, POIs missing any required field dropped; `[]` when none (the POI mock answers 400 today).
  - `accessibility_note`: the `tag[].susstainable.allItems[]` item whose `identityName` is "Accessibility" (title = its label, body = its tooltip with HTML stripped). Absent when upstream has no such item.
  - `best_rate_guaranteed`: upstream only has the `isBestRateGuaranteeEnabled` flag, so the sentence is the optional key `t02.bestrateguaranteedtext` (`src/main/resources/property-details.yaml`). Not set → no cell.
  - `awards` from `listOfAwards` (image + title), `gallery` titles fall back to the property name (upstream sends "").
- **Required in the schema with no fallback:** `location.address` and `location.coordinates`. Both are present in the booking search response; a property without them would not validate.

## T-02 request (`dwl/validate-request.dwl`, rewritten by us 2026-10-28 to input schema 0.2.0, not yet deployed)

Validates the tool arguments against the owner's `schemas/T02-get-property-details.input.schema.json` **0.2.0** and applies the server defaults; `common-validate-request` (`validate-request.xml`) runs it into `vars.validation` / `vars.request`.

- **Schema names:** `propertyCode` (required, digits), `checkinDate` (default today + `t02.checkinOffsetDays`, **30**), `checkoutDate` (default check-in + `t02.nights`, 1), `noOfadults` (default **1**), `noOfchildren` (default 0), **`childAges` (required when `noOfchildren` > 0, one age per child, 0–17)**, `currencyCode` (upper-cased; default the property's own), `language` (the 11-tag enum; anything else falls back to `default.language`). Both `t02.*` keys are optional. Limits from `request.maxAdults` / `maxChildren` / `maxNights`.
- **Still accepted so old callers work:** the short names `checkin`, `checkout`, `adults`, `children`, `currency` (the schema name wins when both are sent), a numeric `propertyCode`, a one-code array (the booking search shape the owner sent from Postman on 2026-10-28), and the server-side `maxPois` (`poi.maxPerProperty`, default 5). Unknown fields are ignored.
- **No longer accepted: `propertyName`** (not in 0.2.0). A body with only a name is a 400 "propertyCode is required."
- **Output `vars.request`** keeps the downstream names (`propertyCode`, `checkin`, `checkout`, `adults`, `children`, `currency`, `language`, `maxPois`) and adds `childAges` and `nights`.
- **Checks:** `tests/check_t02_request.py` (23 checks; also validates the bodies against the input schema). Playground: `tests/playground/validate-request.playground.*`. Postman folder "T-02" uses the schema names.

## T-03 mapping (`dwl/service-offerings.dwl`, written by us 2026-10-26, not yet deployed)

Maps `vars.servicesSource` (one `propertyList[]` entry) + `vars.servicesRequest` to T-03 schema 0.1.0 (the owner's file, unchanged from the copy already in `schemas/`). **Services are the property's facilities:** one service per `facilities.facilityDetails[]` item, in upstream order. `services-map-response` now loads it as a resource instead of holding the DataWeave inline, so the XML lost 51 lines.

- **Checked against the real 51052 response** (`examples/upstream-property-details-51052.json`, the same file T-02 uses). `tests/check_t03.py` mirrors the mapping and validates 5 cases (the real payload, `facilityUrl` and untitled items, no facilities and no `t03` key, no request code); it writes `examples/service-offerings-51052-response.sample.json`. The DataWeave itself has not been run here; `tests/playground/service-offerings.playground.dwl` + `-input.json` run it in the DataWeave Playground.
- **Per service:** `service_name` ← `title`; `service_location` ← `location`; `operating_hours` ← `operatingHours` (CMS HTML verbatim); `description` ← `description` (HTML verbatim); `thumbnail_url` ← `thumbnailImage`; `contact_number` ← `contactNumber` / `phone` (reserved: upstream has none); `external_service_url` ← `facilityUrl`, which the schema needs as an absolute URI, so a site-relative path is prefixed with the asset base URL and anything else is left out. An item with no title is dropped. Blank fields are left out, so 51052's last four services carry only name, description and thumbnail.
- **`meta`:** `property_code` from the request (digits only, else the upstream code), `property_name` from `propertyEnName` / `propertyName`, `brand_code` from `brand` else a slug of `brandName` (51052 → `ascott-the-residence`), `country_code` upper case when two letters, `phone`, `asset_base_url` from `t03.assetbaseurl` else `asset.baseUrl` else discoverasr.com, and `total_results` = the length of `services`.
- `services: []` with `total_results: 0` is valid (PRD EC-01), so a property with no facilities is not an error.

## T-04 mapping (`dwl/room-rate-details.dwl`, rewritten by us 2026-10-26, not yet deployed)

Maps `vars.roomsSource` (one `propertyList[]` entry) + `vars.roomsRequest` to T-04 schema **0.3.0** (the owner's file). It replaces the 0.1.0 reference version in `ascott.mcp.get-property-details.xapi/`, which is now out of date on three counts: prices, strikethrough and the response shape.

- **The shape changed.** 0.3.0 is `{meta, requested_rooms[]}`: **one room list per requested room**, not one flat `rooms[]`. Upstream answers `apartmentList[i]` with `apartments[].room{i}`, so entry `i` reads the `room{i}` key wherever it sits (one `apartments` entry holding `room0`, `room1`, … or one entry each — both are handled). Each entry carries `room_index` (1-based), that room's `noOfadults` / `noOfchildren` / `childAges` **from the request** (upstream does not echo them), `total_results` and `rooms[]`. `rooms: []` with `total_results: 0` is valid.
- **`meta`** has no `total_results` any more. `noOfadults` / `noOfchildren` are the sums over `requested_rooms`, `noOfRooms` is its length. New optional keys: `price_includes_tax` (the request's flag echoed) and `voucher_code_valid` (upstream `isCodeValid`, sent only when the caller passed a `voucherCode`).
- **The request has no `apartmentList` yet.** `validate-request.dwl` sends flat `adults` / `children`, so the mapping falls back to one requested room built from those, which is today's single-room behaviour. It reads `apartmentList[]` the moment the validator sends one, and accepts both `checkin` / `checkout` and `checkinDate` / `checkoutDate`, `currency` and `currencyCode`.
- **No request dates?** `meta.checkin_date` / `checkout_date` fall back to upstream's `nightlyRate[].date` values (`MM/dd/yyyy`): the first night, and the last night + 1 day. Both are required by the schema, so there is no shape without them.
- **Rate fields:** `rate_plan_code`, `rate_plan_name`, `is_tax_inclusive`, `per_night_rate`, `total_stay_rate`, `per_night_tax`, `total_tax` (all required), plus optional `description`, `earn_asr_points`, `non_refundable`, `cancellation_description`, `is_app_exclusive` (`ratePlanChannel` == "MOBILE"). `free_cancellation_until`, `includes_breakfast` are RESERVED in the schema and not sent.
- **Room fields** are unchanged from 0.1.0: `room_code` = `apartmentType` (not `apartmentCategoryCode`), `room_category`, `ranking`, `description` = `roomInformation`, `bed_type`, `max_person_in_room`, `max_occupancy`, `size_sqm` = `dimension`, `units_remaining`, the three image paths, `gallery` (`galleryImage` else `path`, `galleryType` "image" only) and `amenity_groups` (groups with no amenities dropped). `tag`, `features`, `view_type`, `accessible` are RESERVED and not sent.
- **Checked against the real 51052 response** (`examples/upstream-property-details-51052.json`, the same file T-02 and T-03 use). `tests/check_t04.py` is a function-for-function Python copy that writes `examples/room-rate-details-51052-response.sample.json` and runs 20 checks (the real payload, three requested rooms, a tax-inclusive rate, no bookable rate, an empty request, a bare property); all validate against 0.3.0. Keep the two in step. On 51052 the studio keeps 6 of its 14 rates (`ASRAPPFX` 211.50 leads) and the four room types come out in `ranking` order. The DataWeave itself has not been run here (no runtime in this session); `tests/playground/room-rate-details.playground.dwl` + `-input.json` run it in the DataWeave Playground.
- **The flow is wired for it** in `get-multi-room-rates.xml` (T-04 multi-room below); T-07 (`t07-compare-rooms.xml`) maps through it too.

### T-04 in this app (`get-room-rates.xml` + `dwl/rooms-validate-request.dwl`, rewritten by us 2026-10-26; SUPERSEDED 2026-10-27)

**History:** this was the single-room T-04 at `/api/v1/room-details`. On 2026-10-27 `get-room-rates.xml` became T-07 (renamed `t07-compare-rooms.xml` on 2026-10-28) and T-04 is served by `/api/v1/multi-room-details`. What follows still describes `dwl/rooms-validate-request.dwl`, which both use; the flow parts (`rooms-*` sub-flows, the one-room guard) are gone.

- **`rooms-validate-request`** runs `dwl/rooms-validate-request.dwl`, T-04's own validator (the shared `dwl/validate-request.dwl` produces no `nights` and no per-room guests). It accepts the short T-02 names (`checkin`, `checkout`, `adults`, `children`, `currency`) and the PRD names (`checkinDate`, `checkoutDate`, `noOfadults`, `noOfchildren`, `currencyCode`), plus `childAges`, `apartmentList[]` and `priceIncludesTax`. It keeps the field names `property-info-request.dwl` reads and adds `nights`, `rooms`, `apartmentList` and `maxPois: 0`. Errors are one `APP:BAD_REQUEST` message per problem; per-room messages name the room (`apartmentList[1].noOfadults …`) and are only produced when the caller actually sent an `apartmentList`. `voucherCode` is deliberately **not** accepted: `property-info-request.dwl` hardcodes `voucherCode: ""`, so upstream would never see it and `meta.voucher_code_valid` would report a flag computed without it.
- **One room per request, for now.** A guard in `rooms-validate-request` raises `APP:BAD_REQUEST` when `apartmentList` has more than one entry, because `property-info-request.dwl` sends `noOfRooms: 1` and a single-entry `apartmentList`, so upstream would answer `room0` only and the other tabs would be empty. Delete that guard once that file passes `vars.request.apartmentList` / `.rooms` through; the mapping already handles `room0`, `room1`, … . `childAges` is validated and echoed but likewise not yet sent upstream.
- **`rooms-get-rates`** no longer has its own `http:request`: it sets `vars.request` = `vars.roomsRequest` and calls the shared `get-property-common-info`, then `vars.roomsSource` = `vars.property`.
- **Logs:** `T04.start`, `xapi.bookingsearch.request` and `xapi.property.response` (from the shared sub-flow, now labelled `get_room_rate_details` through `vars.toolName`), `xapi.downstream.error` on any HTTP failure (status + first 1000 characters of the upstream body), `T04.success` with `propertyCode`, `noOfRooms`, `roomTypes` and `elapsedMs`, and `xapi.failure`.
- **Errors:** 400 `BAD_REQUEST`, 404 `ROOMS_NOT_FOUND`, 502 `DOWNSTREAM_REJECTED` (an upstream 400: our body was refused), 502 `DOWNSTREAM_UNAVAILABLE`, 504 `DOWNSTREAM_TIMEOUT`, 500 `INTERNAL_ERROR`.
- **Checks:** `tests/check_t04_request.py` mirrors the validator in Python (12 checks) and `tests/check_t04.py` the mapping (20 checks). `tests/playground/rooms-validate-request.playground.*` and `room-rate-details.playground.*` run both in the DataWeave Playground.

### T-04 multi-room (`get-multi-room-rates.xml`, added by us 2026-10-27, not yet deployed)

A second T-04 endpoint, **`POST /api/v1/multi-room-details`**, for **one room or several** in one search. **Owner's plan (2026-10-27): `get-room-rates.xml` will later be reworked for T-07, so this endpoint is to become the T-04 one.** It is therefore self-contained: its own `multi-rooms-map-response` and `multi-rooms-error-handler` (copies of T-04's, same error codes), nothing referenced from `get-room-rates.xml`. Shared with other flows: `get-property-common-info`, `dwl/rooms-validate-request.dwl`, `dwl/room-rate-details.dwl`; keep those working when T-07 changes land. **The MCP tool `getRoomAndRateDetails` still points at `/api/v1/room-details` (`asc-mcp-server/src/main/resources/mcp-tool-xapi.yaml`), which the T-07 `get-room-rates.xml` of 2026-10-27 removes: move it here before deploying T-07.** T-07 also reuses `multi-rooms-validate-request` and `multi-rooms-get-rates` from this file, so keep their names and behaviour.

- **Single room:** any of these is one room, sent as `noOfRooms: 1` with one `apartmentList` entry and answered from `room0`: the T-04 short names with no `apartmentList` (`adults`, `children`, `childAges`, `checkin`, …), the PRD names with no `apartmentList`, the mobile body with one entry (with or without `noOfRooms: 1`), `rooms: 1`, or just `propertyCode` (defaults). `rooms` is accepted as an alias of `noOfRooms`; a count with no matching list (e.g. `rooms: 2`, no `apartmentList`) is a 400, never a silent one-room search.
- **Request:** the mobile app's booking search body as is: `propertyCode`, `checkinDate`, `checkoutDate`, `currencyCode`, `language`, `noOfRooms`, `apartmentList[{noOfadults, noOfchildren, childAges[]}]` (guest counts may be strings), plus `perNightRate`, `isExcludePriceStartFrom`, `promoCorpCode`. Validated by T-04's `dwl/rooms-validate-request.dwl` (1 to `rooms.maxRooms` rooms; per-room adults, children and child ages, ages ≤ children). `noOfRooms`, when sent, must equal the number of rooms `apartmentList` describes, else 400. Ignored: `memberId` (non-logged-in), `messageId` (the correlation ID is used), `version`, `platform`.
- **Booking search body:** inline DataWeave in `multi-rooms-get-rates` (it was `dwl/multi-room-booking-search-request.dwl` until 2026-10-27, moved inline after Studio saved an empty script and the deploy failed with "Missing Body Expression"): the confirmed single-room contract with `noOfRooms` = the room count and **one `apartmentList` entry per room** (counts as strings, `childAges` passed through). Top-level `noOfadults` / `noOfchildren` are the **sums** over the rooms; the mobile app's own multi-room body leaves them out, so drop them if upstream misprices the lead-in. `perNightRate` and `isExcludePriceStartFrom` come from the caller (defaults `true` / `false`), `promoCorpCode` likewise. **The script reads only `vars.roomsRequest`:** `rooms-validate-request.dwl` carries those three flags and `noOfRoomsSent` (single-room T-04 ignores them). An earlier version kept the raw body in a `set-variable` (`#[output application/java --- if (payload is Object) payload else {}]`), which failed in the owner's Studio with "Unable to resolve reference of: `payload`" (2026-10-27), so there is no such variable any more.
- **One `http:request` for everything:** the flow puts its body in `vars.bookingSearchBody` and calls the shared `get-property-common-info`, which now sends that body instead of building `property-info-request.dwl`'s. No other flow sets the variable, so T-02/T-03/T-04/T-06 are unaffected.
- **Response:** upstream answers `apartmentList[i]` with `apartments[].room{i}`. By default the T-04 0.3.0 structuredContent from `dwl/room-rate-details.dwl`: `requested_rooms[i]` = `room{i}`'s room types with that room's own guests; a room upstream did not answer is `rooms: []`, `total_results: 0`. **`?format=raw`** returns the unmapped property (`propertyList[0]`, with `room0[]`, `room1[]`, …) to check what upstream sent.
- **Logs:** `T04M.start`, `xapi.bookingsearch.request` (the exact multi-room body), `xapi.property.response`, `T04M.success` with `roomTypesPerRoom` (e.g. `{room0: 4, room1: 3, room2: 2}`), and T-04's error lines.
- **Checks:** `tests/check_t04_multi.py` (25 checks; 12 of them single-room: five request shapes, each mapped and schema-validated, defaults only, and `rooms: 2` without a list): the owner's mobile body through the validator, the body builder (writes `examples/multi-room-booking-search-request.sample.json`), and a three-room answer built from 51052 through the mapping, validated against 0.3.0 (writes `examples/multi-room-rate-details-51052-response.sample.json`). Not run against UAT yet. Playground: `tests/playground/multi-room-booking-search-request.playground.*`. Postman: folder "T-04 Multi-room details and rates".

## T-05 in this app (`t05-get-promotions.xml`, written by us 2026-10-28, not yet deployed)

**Minimal, vouchers only** (owner, 2026-10-28: "keep it simple"). It is the anonymous core of the owner's mobile flow `ODX_Search_Purchase_Voucher_Flow`: one `POST /v1/searchvoucher` on the CPRV process API, anonymous: `memberId ""`, `userCountryCode` = `countryCode` and header `userToken ""` (added 2026-10-28: UAT answered 500, errorCode 325, on every call without them; the 500 comes from a null in searchvoucher's own response logger, so if it persists the fix is theirs).

- **`POST /api/v1/promotions`.** Input schema 0.1.0, validated by `dwl/promotions-validate-request.dwl`:
  - `countryCode` (required, upper-cased) and optional `city`, `propertyCode` (digits), `voucherName` and `voucherCategory[]` (duplicates removed ignoring case).
  - `currencyCode` defaults to `property.currency`.
  - `language` is passed through when it is in the schema list, else `default.language`.
- **Upstream:** `HTTP_Request_configuration-CPRVProcessAPI` is defined in `t05-get-promotions.xml`, with the same name and `https.cprvprocessapi.*` keys as the mobile app.
  - Body (inline): `messageId`, `memberId ""`, `userCountryCode`, `language`, `voucherName`, `country`, `voucherCategory`, `propertyCode` [code], `currency`, `sortBy "latest"`, `private false`, `channel "mobile"`. There is no paging, so upstream's default page applies.
  - Headers: `client_id`, `client_secret`, `messageId`, `userToken ""`.
  - The CPRV host in UAT on 2026-10-28 was `lodging-odx-loyalty-dev-app` (DEV), while booking search is UAT.
  - **A 404 counts as zero vouchers** (PRD AC-03). Other errors map to 502 / 504 / 500 as in the other tools.
- **Left out of the mobile flow**, so these parts are missing:
  - The VM archive.
  - **The ASR property cache.** `city` is not turned into property codes, only echoed and used as `location_label`. `scope_label` is built only for country-wide vouchers, from the country names in a small table in the DWL. `meta.property_name` is never sent, and an unknown `propertyCode` is not an error (no ER-04).
  - **The AEM voucher details call.** `voucherUrl`, `imageThumbnail`, `altThumbnail`, `description` and `urgencyTrigger` are used only if `searchvoucher` sends them itself. **`details_url` (required) falls back to `t05.detailsFallbackPath`** (default `/en/member/buy-experiences`). `is_low_stock` is only sent with `urgencyTrigger`. The mobile flow also drops vouchers unknown to AEM; this one keeps them.
- **Mapping (`dwl/promotions-response.dwl`, schema 0.2.0):**
  - `id` ← `voucherProgrammeCode`; `title` ← `voucherTitle`, else `voucherEnTitle`.
  - `scope_level` ← `applicableLevel` (`property_specific` / `country`).
  - `property_codes` / `country_codes` ← `propertyCode` / `countryCode` (array or comma string, de-duplicated).
  - `expiry_date` ← `expiryDate` cut to `YYYY-MM-DD`; null is left out.
  - `details_url` is a full URL with the doubled `/` after the host collapsed, or a path with one leading `/`.
  - `category` verbatim.
  - **`price` ← `preferredCurrencyPromoPrice` (else `promoPrice`).** The request asks upstream for `currency`, so `meta.currency` = that currency, sent only when a voucher has a price. A points-only voucher has no price.
  - `points` ← `points` > 0; `remaining` ← `inventory`.
  - `description_text` is HTML turned into plain text, left out when it only repeats the code.
- **Kept vouchers:** not private, with a code and a title, matching `voucherName` (in the title, ignoring case) and `voucherCategory` (ignoring case), and in scope. In scope means the voucher's country list contains `countryCode`, and with a `propertyCode`, the voucher is country-wide or lists that code. Upstream should filter already; this repeats it. Order: `sequence`, de-duplicated by `id`. `meta.voucher_count` = the number kept.
- **Unconfirmed (no real response shared yet):** `tests/check_t05.py` (24 checks) runs against **`examples/upstream-searchvoucher.SYNTHETIC.json`**, built from the field names the mobile flow reads, and writes `examples/promotions-SG-response.sample.json`. Replace the sample with a real response when the owner sends one. The log `xapi.searchvoucher.response` lists the real top-level and first-voucher field names. The DataWeave itself has not been run. Postman: folder "T-05 Get promotions (vouchers)".
- **Open items for the owner:** the price field and currency (schema open item 1/2); whether `searchvoucher` itself sends `voucherUrl` / `imageThumbnail`; and whether to add the property cache (city filter, scope labels, ER-04) and the AEM details call later.
- **MCP server:** `asc-mcp-server`'s `getPromotions` still calls `GET /properties/{id}/promotions`. It should become `get_promotions` with the input schema above, pointing at `/api/v1/promotions`; change it only when the owner asks.

## T-07 in this app (`t07-compare-rooms.xml`, formerly `get-room-rates.xml`, written by us 2026-10-27, reworked to the owner's schema 0.4.0 on 2026-10-28, not yet deployed)

**Owner's request (2026-10-27):** fetch the property's room information, keep only the `roomCodes` in the request, and fetch all room codes when none are given. **Owner's schema 0.4.0 (2026-10-28)** fixes the output: 2–4 rooms, the first four when `roomCodes` is omitted. Gather only (owner decision 2026-10-26): no recommendation or ranking; the model recommends in its reply.

- **`POST /api/v1/compare-rooms`.** Request = the owner's body: `propertyCode`, `roomCodes[]` (optional; PRD name `roomCategoryCodes` also accepted), `checkinDate`, `checkoutDate`, `noOfadults`, `noOfchildren`, `childAges`, `currencyCode`, `priceIncludesTax`, `language`. The T-04 short names work too, and so does the mobile body with **one** `apartmentList` entry. The stay is validated by `multi-rooms-validate-request`. **One room's guests only:** more than one `apartmentList` entry → 400.
- **Room codes (`dwl/compare-rooms-validate-request.dwl` → `vars.roomCodesRequest {errors, roomCodes}`):** non-blank strings of 1–40 `A-Za-z0-9_-` characters, kept **as written** (`excluded[].room_code` echoes them "as requested"), with duplicates removed ignoring case. When sent, it must name **2 to 4** room types, else 400. Absent / null / `[]` = the first four room types.
- **Matching (`dwl/compare-rooms-response.dwl`):** a code matches upstream `apartmentType` (T-04 `room_code`), else `apartmentCategoryCode` (`room_category`), ignoring case. Each code takes its first matching room that has not already been picked. **51052's codes are `0BRCT`, `1DLXT`, `1BRT`, `1BRMT`**; the owner's example codes (`0BRXA`, `1BRXB`, `2BRXC`) are not 51052 codes.
- **Upstream:** one booking search call via `multi-rooms-get-rates`, so `childAges` reaches upstream.
- **Response (schema 0.4.0, the owner's file):** `{meta, rooms[2..4], excluded[]}`.
  - `meta`: `property_code`, `property_name`, `brand_code`, `country_code`, `asset_base_url`, `total_results` (= the length of `rooms`), `currency`, `checkin_date`, `checkout_date`, `noOfadults`, `noOfchildren`, `childAges`, `price_includes_tax`, all taken from the T-04 mapping's `meta` / `requested_rooms[0]`.
  - **Each room is the T-04 `room` object unchanged**, from `requested_rooms[0].rooms`, which holds only rooms with a bookable rate, in ranking order.
  - Rooms are in the order the codes were given; without codes, the first four.
  - `excluded[] {room_code, reason}` is left out when empty. Reasons: `not_available` (a requested code with no bookable room type, whether the room is missing or has no rate; decision 5) and `over_limit` (no codes, the room types past the first four, under their own code; decision 8).
- **The schema refers to the T-04 0.4.0 `room`** (`urn:…get_room_rate_details:structured-content:0.4.0#/$defs/room`; rates may carry `is_member_rate`), **which is not in this repo yet.** We still map T-04 0.3.0, which drops member rates, so `is_member_rate` is never sent. `tests/check_t07.py` registers the 0.3.0 schema under the 0.4.0 id. Ask the owner for T-04 0.4.0.
- **Errors:**
  - 400 `BAD_REQUEST`.
  - 404 `NOT_ENOUGH_ROOMS` when fewer than two rooms are left (the tool's `isError`, ER-05 / EC-04). The message names the unavailable codes and the room types that do have rates, so the model can retry.
  - 404 `ROOMS_NOT_FOUND` when the property is not found.
  - 502 `DOWNSTREAM_REJECTED` / `DOWNSTREAM_UNAVAILABLE`, 504 `DOWNSTREAM_TIMEOUT`, 500 `INTERNAL_ERROR`.
- **Logs:** `T07.start`, `xapi.bookingsearch.request`, `xapi.property.response`, `T07.success` (`roomCodes`, `rooms`, `excluded`), `xapi.downstream.error`, `xapi.failure`.
- **Checks:** `tests/check_t07.py` runs 30 checks (including the owner's minimal `{propertyCode, roomCodes}` body):
  - the owner's body → 404, and real codes → `examples/compare-rooms-51052-{request,response}.sample.json`, validated against 0.4.0;
  - no codes / `[]` / null, and six room types → `over_limit`;
  - an unknown code, one available, and no bookable rate;
  - the category-code alias, duplicates, 1 and 5 codes;
  - bad input, and one vs two `apartmentList` entries.

  It reuses the T-04 mirrors. The DataWeave itself has not been run; the Playground copies are `tests/playground/compare-rooms-*.playground.*`, and Postman has the folder "T-07 Compare rooms and rates".
- **Known gap (shared T-04 validator):** with the top-level shape (no `apartmentList`), `childAges` is not compared with `noOfchildren`.
- **Not in the response:** PRD scoring fields (the schema leaves them out). The widget builds Deciding Criteria from `bed_type`, the selected rate's `non_refundable` and `amenity_groups`. `minPrice` / `maxPrice` / `requiredInclusions` / `attributeToCompare` are ignored.

## T-08 in this app (`t08-create-booking.xml`, written by us 2026-10-28, not yet deployed)

**Read-only checkout hand-off** (PRD AC-08): nothing is reserved, held or paid, and no cart, reservation or payment API is called. It re-checks that each room is bookable now and returns the summary the widget turns into a discoverasr.com checkout link. Owner's schemas 0.1.0 (2026-10-28): input `schemas/T08-create-booking.input.schema.json`, output `schemas/T08-create-booking.structured-content.schema.json`.

- **`POST /api/v1/create-booking`.** Input: `propertyCode` (required, digits), `checkinDate` (default today + `t08.checkinOffsetDays`, 30), `checkoutDate` (default check-in + `t08.nights`, 1), `apartmentList[]`, `currencyCode`, `voucherCode` and `language`.
  - `apartmentList[]` entries are `{noOfadults, noOfchildren, childAges, roomCode, ratePlanCode}`. Without it, the default is one room for 1 adult.
  - **`childAges` length must equal `noOfchildren`.** `roomCode` and `ratePlanCode` come both or neither.
  - Lower-case currency is upper-cased.
  - A `language` outside the schema's list falls back to `default.language`; listed values are passed through untouched.
  - `memberId`, `enrollAsrOnCheckout` and other unknown fields are ignored.
- **Multi-room, as T-04 multi-room:** one booking search call with one `apartmentList` entry per room, `noOfRooms` = their count and summed top-level guests (inline body in `create-booking-get-rates`). Upstream answers `apartmentList[i]` with `room{i}`. **Unlike T-04, the body also carries the caller's `voucherCode`**, so `meta.voucher_code_valid` is real. Then `dwl/room-rate-details.dwl` prices every room with the T-04 rules: bookable rates only (member / ACRS / TEST dropped), ranking order, upstream's tax basis.
- **Choosing each room (`dwl/create-booking-response.dwl`):**
  - **Selected** (`roomCode` + `ratePlanCode`): the room whose `room_code` (else `room_category`) matches and its rate whose `rate_plan_code` matches, ignoring case, taken from that room's own `room{i}`.
  - **Cheapest** (neither): the rate with the lowest per-night price **including tax** (`per_night_rate + per_night_tax`, so tax-inclusive and tax-exclusive rates compare fairly) across that room's types. A tie goes to the better-ranked room.
  - `meta.resolution` is `selected` / `cheapest` / `mixed`.
- **Response:** `{meta, rooms[], add_ons[]}`.
  - Each room is `{room_index, noOfadults, noOfchildren, childAges, room_code, room_name, banner_image_url, rate}`, where `rate` is the **T-04 rate object unchanged**.
  - `meta` holds `property_code`, `property_name`, `brand_code`, `country_code`, `asset_base_url`, `address` (upstream `address`), `banner_image_url` (upstream `bannerImageMobile`), the stay, `noOfRooms`, summed guests, `currency`, `resolution`, `total_stay_price`, `total_earn_asr_points` and `voucher_code_valid` (only with a `voucherCode`).
  - `total_stay_price` = Σ `total_stay_rate` + `total_tax` when not tax-inclusive (rounded to 2 places).
  - `total_earn_asr_points` is the sum of `earn_asr_points`, left out when 0.
- **The schema refers to the T-04 0.4.0 `ratePlan`** (with `is_member_rate`), which is not in the repo. We map T-04 0.3.0, which drops member rates. **A member rate picked by the user therefore comes back 409** (PRD conflict noted under "T-08 Create_booking"). `tests/check_t08.py` registers 0.3.0 under the 0.4.0 id.
- **Errors:**
  - 400 `BAD_REQUEST`, with one message per problem.
  - **409 `RATE_NOT_AVAILABLE`** (ER-04): a picked room + rate is not bookable now. The message lists that room's bookable rates, or the room types available.
  - **404 `NO_AVAILABILITY`** (ER-02): a room with nothing bookable. The message names the room and its guests.
  - 404 `PROPERTY_NOT_FOUND`.
  - 502 `DOWNSTREAM_REJECTED` / `DOWNSTREAM_UNAVAILABLE`, 504 `DOWNSTREAM_TIMEOUT`, 500 `INTERNAL_ERROR`.

  When both kinds of problem occur, 409 wins and the message covers every room.
- **Add-ons (optional, schema RESERVED):** only when `t08.addons.enabled` is "true", `create-booking-add-ons` calls the **bookings process API `POST /v1/addonlist`** on `HTTP_Request_Bookings_config`. This is the call in the owner's mobile flow `ODX_Booking_AddOn_ListFlow` (2026-10-28).
  - Headers: `client_id`, `client_secret`, `messageId`, `userToken` "".
  - The body mirrors that flow's "Request Payload" for this booking: `memberId ""`, `currencyCode`, the stay, `noOfAdults` / `noOfChildren` as strings, `ratePlanCodes` (the booked rates), `channel "mobile"`, `voucherCode`. That flow hardcodes `noOfChildren "1"`; we send the real count. `perRoom` is not sent (its meaning is unknown).
  - **No sample addonlist response has been shared**, so `dwl/create-booking-add-ons.dwl` guesses the field names (`addOnName` / `title` / `name`, `description`, `imageUrl` / `image`, `preferredCurrencyPrice` / `price`, …) and logs `xapi.addons.response` with the real field names. **Ask the owner for a response sample** and fix the lists from it.
  - Any failure → no `add_ons` (log `xapi.addons.unavailable`); it never fails the call.
  - **`HTTP_Request_Bookings_config` needs `https.bookingsprocessapi.*` in `uat.yaml` even with add-ons off,** or the app does not start. Nest those keys inside the existing `https:` block.
- **Logs:** `T08.start`, `xapi.bookingsearch.request`, `xapi.property.response`, `xapi.addons.request` / `xapi.addons.response` / `xapi.addons.unavailable`, `T08.success` (resolution, room + rate per room, total, currency), `xapi.downstream.error`, `xapi.failure`.
- **Checks:** `tests/check_t08.py` runs 44 checks:
  - the minimal `{propertyCode}` defaults, one selected room, and three rooms mixed;
  - a member rate, unknown room or empty room → 409 / 404;
  - the tax-inclusive cheapest rule and the ranking tie-break;
  - voucher, points and 14 bad inputs;
  - guessed add-on shapes.

  All outputs validate against 0.1.0, and the script writes `examples/create-booking-51052-{request,response}.sample.json`. The DataWeave itself has not been run; Playground copies are in `tests/playground/create-booking-*`, and Postman has the folder "T-08 Create booking".
- **MCP server:** `asc-mcp-server`'s `createBooking` is still the old WRITE tool (guest, `confirmed`, `idempotencyKey`). It must be replaced by `create_booking` with the input schema above, pointing at `/api/v1/create-booking`; change it only when the owner asks.

## T-06 in this app (owner decision, 2026-10-25)

**T-06 only puts the requested properties together in one payload. It does not compare, rank, filter or recommend.** The model and the widget do that. So the PRD's `recommendation` block, `is_recommended`, match flags, reason lines and the filter inputs (`maxRate`, `facilities`, `roomType`, `poi`, `travellerProfile`, `serviceCategory`) are not in the xAPI. They are accepted in the body and ignored. Do not add them back unless the owner asks.

- **Request:** `propertyCodes[]` (2–4 distinct codes; duplicates removed, codes past the 4th dropped and echoed in `meta.dropped_property_codes`), `checkinDate` (default today + 30), `checkoutDate` (default check-in + 1), `noOfadults` (default 1), `noOfchildren` (default 0), `currencyCode`, `language`. The T-02 names (`checkin`, `adults`, `currency`, …) also work.
- **Lookup (`compare-get-properties`):**
  1. If `t06.batchLookup` is "true" (**default "false"** since 2026-10-25), `compare-batch-lookup` makes one booking search call. It sends the `property-info-request.dwl` body with `propertyListing: true` and `propertyCode` set to the first `t06.batchSize` (3) codes. The reference caller allows at most 3 codes with `propertyListing` true, and exactly 1 with false. **In UAT (2026-10-25) the cards came back empty except code and name**, so the batch call most likely returns slim listing entries. Hence the default "false", and a batch entry is now used only when it has `apartments` and a `location` object; otherwise the code is fetched one by one. The `xapi.compare.batch` log lists each entry's field names. Any failure leaves `vars.batchList` empty (log `xapi.compare.batch.failed`).
  2. Every code not returned by the batch call with full details (`apartments` array and `location` object) goes through `compare-single-lookup` in a `parallel-foreach` (`t06.maxConcurrency`). That calls the shared `get-property-common-info`, one code at a time. `APP:NOT_FOUND` → status `not_found`; any other error → `unavailable` (logged as `xapi.downstream.error` with the code).
  3. `vars.lookups` = one `{code, status, source: batch|single, property}` per requested code, in request order.
- **At least TWO properties must come back** (schema 0.1.0: `properties` is 2–4). Errors: fewer than two found → 404 `PROPERTIES_NOT_FOUND`, whose message names the codes that were not found; fewer than two and at least one lookup failed → 502 `DOWNSTREAM_UNAVAILABLE`.
- **Response (schema 0.1.0, the owner's file 2026-10-27, mapped by `dwl/compare-properties-response.dwl`):** `{meta, properties[], excluded[]}`. **Optional fields upstream has no value for are left out** (`skipNullOn="everywhere"`), unlike our earlier 0.2.0 version which sent them as `null`.
  - `meta {total_results, location_query, currency, checkin_date, checkout_date, noOfadults, noOfchildren, childAges, asset_base_url}`. `additionalProperties: false`, so **`dropped_property_codes` has nowhere to go**: codes past the 4th are still removed by the validator but only appear in the logs. `location_query` is sent only when every card shares the same `city, country` line. `childAges` is echoed from the request — `compare-validate-request.dwl` now accepts and validates it (0–17), though `property-info-request.dwl` still sends upstream an empty `childAges`.
  - **Card fields** (in request order): `property_code` (digits only), `property_name` (`propertyEnName` / `propertyName`), `brand_code` (slug of `brand`, else `brandName`, else `ascott`), `banner_image_url` (`bannerImageMobile` → `newPropertyThumbnail` → first gallery image), `location_label` (`cityName, countryName`, de-duplicated when they are the same word), `amenity_highlights[] {imagePath, description}`, `nearby[] {title, icon_code, distance_minutes}`, `availability_status`, `per_night_rate`, `is_asr_participating` (`asrParticipating`), `earn_asr_points`.
  - **Prices:** the property's own **cheapest bookable rate** under the T-04 rate filter (no `AOA` / member / "ACRS Compare" / TEST rates), as `per_night_rate` = that rate's `perNightRatePrefCurr`, **as upstream gives it** (T-04 0.3.0's basis; the earlier T-06 added the tax). `earn_asr_points` is that same rate's `earnASRpoints`. A listing-style entry with no `apartments` falls back to the property-level `perNightRatePrefCurr`. No rate → `availability_status: on_request` with no price. `next_available_date` is never sent (upstream does not say).
  - **`amenity_highlights`:** from `facilities.facilityGroup[].facilities[]` — `imagePath` plus the label (`description`, else `name` / `enName`, since some rows have a null description). The `facilities-amenities` group first, de-duplicated by label, then ranked by a keyword list (pool, gym, fitness, spa, business, wifi, breakfast, restaurant, lounge, parking, laundry, airport, …) and cut to 6, so the chips are highlights rather than whatever upstream lists first. 51052 → Swimming pool, Gymnasium, WiFi, Daily continental breakfast, Residents' lounge, Laundry.
  - **Left out for lack of a source:** `average_ratings` / `total_number_of_reviews` (booking search has no reviews; the schema wants both or neither) and `nearby` (T-06 does not call the POI system — the mapping fills it when a lookup carries `pois`, which only T-02 does today).
  - **`excluded[] {property_code, reason}`** carries only `reason: "not_found"`, the schema's single enum value. A code whose lookup failed (`unavailable`) therefore has no slot: it is simply absent from the response and reported in the `xapi.downstream.error` log.
- **Checks:** `asc-mcp-odx-backend-xapi/tests/check_t06.py` is a function-for-function Python copy of the response DataWeave. It builds `examples/compare-properties-response.sample.json` from the real 51052 response plus the 8790 / 8791 samples and runs 19 checks (not found, unavailable, no bookable rate, a listing entry, POIs and `childAges`, different cities); all validate against 0.1.0. Keep it in step with the DataWeave. The DataWeave itself has not been run here (no runtime); `tests/playground/compare-properties-response.playground.dwl` + `-input.json` run it in the DataWeave Playground.
- **Known issues:** `compare-batch-lookup` is a fourth copy of the booking search `http:request` (see issue 8). The batch path is unconfirmed (above). Set `t06.batchLookup: "false"` to use only one-by-one calls.
- **Postman:** see "Postman collection" under "How to work on it". Set `propertyCode4` to a real 4th code.

## Wiring the MCP tools to our xAPI (`asc-mcp-server/src/main/mule/mcp-tool.xml`, rewritten by us 2026-10-28, not yet deployed)

Owner's request (2026-10-28): map every tool call to its xAPI endpoint, with proper wiring, logging and descriptions written for the model. Built on the owner's `mcp-tool.xml` of that day; `asc-mcp-server/src/main/resources/mcp-tool-xapi.yaml` holds the `xapi.*` keys (**every `*.path` key must exist, or the app does not start**).

| Tool | PRD | Path key | xAPI endpoint |
|---|---|---|---|
| `get_property_details` | T-02 | `xapi.propertydetails.path` | `/api/v1/property-details` |
| `get_service_offerings` | T-03 | `xapi.serviceofferings.path` | `/api/v1/service-offerings` |
| `get_room_rate_details` | T-04 | `xapi.roomdetails.path` | `/api/v1/multi-room-details` |
| `get_promotions` | T-05 | `xapi.promotions.path` | `/api/v1/promotions` |
| `compare_properties` | T-06 | `xapi.compareproperties.path` | `/api/v1/compare-properties` |
| `compare_rooms_rates` | T-07 | `xapi.comparerooms.path` | `/api/v1/compare-rooms` |
| `create_booking` | T-08 | `xapi.createbooking.path` | `/api/v1/create-booking` |

- **Tool names** are the schema ids' names (`urn:ascott:mcp:<name>:…`), all snake_case. **`compare-properties` (the owner's hyphen) became `compare_properties`**: confirm the widget matches on that name.
- **One vocabulary for the model:** `propertyCode` (digits), `checkinDate` / `checkoutDate`, `noOfadults` / `noOfchildren` / `childAges` or `apartmentList[{noOfadults, noOfchildren, childAges}]`, `currencyCode` (`^[A-Z]{3}$`), `language` (the 11-tag enum of the owner's schemas).
  - `get_promotions` and `create_booking` declare **the owner's input schemas verbatim** (`schemas/T05-…input…`, `schemas/T08-…input…`), with only `$schema` set to draft-07 and `dependentRequired` written as draft-07 `dependencies`.
  - **`get_property_details`** declares the owner's T-02 input schema 0.2.0 (draft-07 `$schema`; `propertyName` is gone, `childAges` added) and sends the arguments unchanged: the xAPI's `validate-request.dwl` reads those names since 2026-10-28 (the `vars.xapiBody` mapping to short names was removed).
  - `get_room_rate_details` takes `apartmentList[]` (1–4 rooms) and `priceIncludesTax`; `compare_rooms_rates` takes `roomCodes[]` (2–4) and one room's guests; `compare_properties` now also takes `childAges`.
  - Limits in the non-owner schemas (8 adults, 6 children, 4 rooms) are guesses at `request.maxAdults` / `request.maxChildren` / `rooms.maxRooms`; the xAPI still enforces its own and answers 400.
- **Descriptions** say what each tool returns, when to use it and which tool to use instead, how results chain (`room_code` / `rate_plan_code` from T-04 into T-07 and T-08), the tax basis of prices, that every tool is read-only, and that `create_booking` reserves nothing.
- **`call-odx-xapi`:** posts `vars.xapiBody` (else `vars.args`, nulls dropped) to `vars.xapiPath` with `Content-Type` and `X-Correlation-ID` = `vars.traceId`, and leaves the xAPI's `structuredContent`, unwrapped, in `vars.toolResponse` (`wrap-success` is not used: the widget reads the bare object).
  - The validator accepts `200..299,400,404,409,422,500,502,504`, so the xAPI's own error body survives. On a status ≥ 400: `vars.publicError` = `payload.error` (else a `DOWNSTREAM_ERROR` object), `vars.httpStatus`, `log-failure`, raise **`APP:XAPI_REJECTED`**.
  - **No answer at all** (an `HTTP:*` error such as timeout or connection refused) → `DOWNSTREAM_TIMEOUT` (504) or `DOWNSTREAM_UNAVAILABLE` (502) in `vars.publicError`, log `xapi.unreachable`, `log-failure`, and the error propagates to `generic-tool-error-handler`.
- **Logs** (category `ascott.audit`): `tool.start` (`log-start`), `xapi.request` (path and exact body), `xapi.response` (status, ms), `xapi.unreachable`, `tool.success` / `tool.failure` (`observability.xml`). The empty `<logger/>` steps of the owner's copy were removed.
- **Not done (no file or no support known):** no tool sets `openai/outputTemplate` to the widget `ui://ascott/widget-v3.html`; `generic-tool-error-handler` is still not shared, and the tools rely on it keeping `vars.publicError`.
- **Checked here:** the XML parses, every input schema is valid draft-07, and a sample call per T-04 / T-05 / T-07 / T-08 passes both its tool schema and the Python mirror of the xAPI validator. Not run in Mule.

## Product specs (PRDs) for tools not yet built

Full text: `asc-mcp-odx-backend-xapi/docs/PRD-T05-get-promotions.md`, `PRD-T06-compare-properties.md`, `PRD-T07-compare-rooms-rates.md` (pasted as text by the owner) and `PRD-T08-create-booking.md`. Read the full PRD before you build a tool. T-05 is built minimal: see "T-05 in this app". T-08 is built: see "T-08 in this app". T-07 is built as a gather-only tool: see "T-07 in this app". T-06 is built as a pass-through only: where the PRD below and "T-06 in this app" disagree, the latter wins.

Tool map from the PRDs:

| Tool | Name | Status in this app |
|---|---|---|
| T-01 | Search properties | not in this app |
| T-02 | Get_property_details | built |
| T-03 | Get_service_offerings | built |
| T-04 | Get_room_rate_details | built; rewritten for schema 0.3.0 (2026-10-26) |
| T-05 | Get_promotions | built minimal (2026-10-28): vouchers only, one `/v1/searchvoucher` call; owner's schemas 0.2.0 / 0.1.0 |
| T-06 | Compare_properties | built: puts properties together only; mapped to the owner's schema 0.1.0 (2026-10-27) |
| T-07 | Compare_rooms_rates | built (2026-10-27/28): 2–4 of the property's rooms by `roomCodes`, else the first four; owner's schema 0.4.0 |
| T-08 | Create_booking | built (2026-10-28): read-only checkout hand-off, one or several rooms; owner's schemas 0.1.0 |

Rules for T-05 and T-06:

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

### T-07 Compare_rooms_rates

Compares 2–4 room types **at one property**. It has a single inline component and no full screen. Every card hands off to T-04 for that room, and there is no booking action: T-08 is reached only through T-04 (AC-10, SM-06). The card shows one starting rate per room, so the full rate-plan list stays in T-04.

**Owner decision (2026-10-26): T-07 only gathers the rooms, like T-06.** No recommendation, ranking or filtering: no `recommendation` block, no `is_recommended`, no match flags or reason lines, and `minPrice` / `maxPrice` / `requiredInclusions` / `attributeToCompare` are accepted and ignored. The model and the widget compare.

**Inputs:**

- `propertyCode` (required).
- `roomCategoryCodes[]` (2–4; duplicates removed, extra codes past 4 dropped and reported: EC-01/02, AC-04). **Owner decision (2026-10-26): match them against `apartmentType`**, which is what T-04 returns as `room_code`. The PRD's own examples (`"CUTLER-STUDIO"`) are `apartmentCategoryCode`; match that too as a fallback, but `apartmentType` is what the model carries over.
- `checkinDate` / `checkoutDate`: carried from T-04, else today + 30 / + 31.
- `noOfadults` / `noOfchildren`: default 1 / 0.
- `currencyCode`.
- `minPrice` / `maxPrice`: confirmed booking search request fields, already in our body as `""`.
- `requiredInclusions[]`: PARAMETER GAP, OQ-05.
- `attributeToCompare`: API GAP.
- `memberId`: ignore, this is a non-logged-in journey.

**Upstream APIs:**

- **"apartmentlist / apartmentratedetails – V3" is our booking search call.** In this app **one call for the property** returns every room in `apartments[].room0[]`, so filter by code; there is no need for the PRD's per-room fan-out.
- `pricedistribution` is supplemental and is not in this app.
- The PRD's scoring and explanation service has no API (OQ-01).

**Card (PRD §6.1 `rooms[]`), mapped to T-04 fields:**

- `apartment_category_code`, `apartment_name` (`apartmentName` / `apartmentType`).
- `banner_image_url` (room `bannerImageMobile`), `brand_logo_url` (property `brandlogo`).
- `max_person_in_room`, `dimension`.
- `per_night_rate_pref_curr`: the room's cheapest bookable rate under the T-04 rate filter; decide with the owner whether it is tax-inclusive (T-04 0.3.0 passes upstream's basis through instead); no rate → "Availability on request" (ER-07, EC-06).
- `currency`.
- `deciding_criteria`, always all four keys (EC-10: "Not specified" when unknown):
  - `bed_type`: `bedType`.
  - `workspace`, `wifi`: derived from the room's `amenityGroups[].amenities[].description`. The keyword logic is open (OQ-02/03).
  - `cancellation`: condensed from `cancellationDescription` / `nonRefundable`. The labels are open (OQ-04).

**PRD-only parts:**

- `meta {property_code, property_name, total_results, dates, guests, currency, attribution}`. `attribution` is "ASR" here but "discoverasr.com" elsewhere (OQ-08).
- `recommendation {recommended_room_code, traveller_profile_label, recommendation_text, match_flags, reason_lines}` and `is_recommended`. No badge is drawn on the card.

**Errors:**

- A code not at the property → excluded with a reason (ER-04, EC-03).
- Fewer than 2 rooms → ER-01/ER-05; the LLM hands off to T-04 instead (EC-04).
- Upstream 5xx → ER-03.

**Hand-off to T-04:** the expand icon and "View available rates" open T-04 with that room pre-selected and the same dates and guests (AC-09). **Owner decision (2026-10-26): no room filter is to be added to T-04.** T-04 keeps returning every room, and the widget picks the one it needs.

### T-08 Create_booking

Despite its name, T-08 is **read-only**. It never writes a reservation, holds a cart or takes payment (AC-08, SM-05). It re-checks that one room and rate is still bookable and returns a booking summary card plus one external checkout link to discoverasr.com, where the user pays. It collects no guest personal or payment details. There is a single inline component and no full screen. One room per call; multi-room is out of scope (EC-06, OQ-08).

**Two ways in:**

- **Selected:** `resolution_method` "selected". The caller carries `propertyCode`, `apartmentCategoryCode` and `ratePlanCode` from T-04/T-07, plus dates and guests. Availability must be re-checked now, not assumed from the earlier call (AC-03, EC-02). If the room or rate is gone → ER-04 and no checkout link.
- **Cold:** only `propertyCode`, from "book me a room at …". The xAPI runs the same lookup as T-04 and picks the cheapest bookable rate per night; ties go to the room with the best `ranking` (EC-01). No bookable room → ER-02.

**Inputs:**

- `propertyCode` (required).
- `apartmentCategoryCode`, `ratePlanCode` (optional together; cold pick when absent).
- `checkinDate` / `checkoutDate`: default today + 30 / + 31.
- `noOfadults` / `noOfchildren`: default 1 / 0.
- `currencyCode`.
- `voucherCode` / `promotionCode`: from T-05 or stated; passed through. An invalid code → ER-07, standard total.
- `enrollAsrOnCheckout`: PARAMETER GAP, default false.
- `memberId`: auth only. This app is a non-logged-in journey, so ignore it.

**Upstream APIs:**

- **"apartmentlist / apartmentratedetails – V3" is the booking search call this app already makes**: `/v3/checkpropertyavailability` → `propertyList[].apartments[].room0[].ratePlan[]`, the T-04 source. Reuse `get-property-common-info` and the T-04 rules (`room-rate-details.dwl`): bookable rates only, `ranking` order, prices on upstream's own tax basis with the tax beside them (T-04 0.3.0).
  - Room fields: `apartmentCategoryCode`, `apartmentName`.
  - Rate fields: `ratePlanCode`, `ratePlanName`, `isTaxInclusive`, `cancellationDescription`, `earnASRpoints`.
  - Property fields: `propertyName`, `bannerImageMobile`, `brandlogo`, `address`.
- **`bookingcart`**: a confirmed API, but there is **no config, path or credentials for it in this app yet**. It returns `cartId`, `isAvailable` and `totalChargesIncludingTaxes`. Ask the owner for its contract. Whether `cartId` is usable by the website is OQ-02.
- **`reservationV3` (`v2`/`v3-initiatereservation`) and `mobilev1/v2/confirmreservation`**: must **never** be called by T-08. They are write APIs (OQ-01 future).
- **Checkout deep link: API GAP (OQ-04).** No API builds it and its URL format is unconfirmed. The PRD's example `https://www.discoverasr.com/checkout?propertyCode=…&apartmentCategoryCode=…&ratePlanCode=…&checkin=…&checkout=…&adults=…&children=…&currency=…` is marked "[pending]". Can it be recomputed on the client when the ASR checkbox changes? That is open (OQ-05). If the link cannot be built → ER-08.

**Output packet (PRD §6.1):**

- `meta {property_code, resolution_method ("selected" | cold), checkin_date, checkout_date, noOfadults, noOfchildren, currency}`
- `property {property_name, brand_logo_url, banner_image_url, address}`
- `room_and_rate {apartment_category_code, apartment_name, rate_plan_code, rate_plan_name, is_tax_inclusive, cancellation_description, earn_asr_points}`
- `cart {cart_id, is_available, total_charges_including_taxes, voucher_code, promotion_code}`
- `enrollment {enroll_asr_on_checkout}`
- `checkout {external_checkout_url}`

**Rules:**

- One currency throughout (AC-07).
- The free-cancellation line appears only for a cancellable rate; never invent one (EC-05). Parsing `cancellationDescription` into a deadline is open (OQ-07).
- No image → leave it out (EC-07).
- The LLM must never claim to know whether the booking succeeded (ER-09, OQ-06).
- A change of dates or guests re-invokes T-08 (AC-09). A change of room or rate goes back to T-04/T-07.

**Conflicts with this app to raise before building:**

- The PRD's examples use a member rate ("First-Stay Member Special") and points. T-04 here drops member (`AOA` / "…Member…") rates for anonymous users, so a selected member rate would fail the re-check.
- The total comes from `bookingcart`, which this app can't call yet. Until then, the T-04 tax-inclusive total is the only source.
- ER-06 is blank in the PRD.

## The MCP server app (`asc-mcp-server/`, owner's files, 2026-10-26)

**Re-shared by the owner on 2026-10-28:** `business-flows.xml` and `observability.xml` (identical to the copies here) and `mcp-html-widget.xml` (only change: the widget URI is now `widget-v3`). These three are current as of that date. Also re-shared the same day: `property-mcp-api.xml` (identical; its 112 KB line 99 is a commented-out dummy payload) and `global-config.xml`. **`global-config.xml` now defines `MCP-ODX_Backend_XAPI_config`** (`${xapi.protocol}` / `${xapi.host}` / `${xapi.port}`), the owner's own copy of our xAPI connection, under a different name from the **`ODX_Backend_XAPI_config`** that our `mcp-tool.xml` defines and `call-odx-xapi` uses. The two names do not clash, but the owner's deployed `mcp-tool.xml` may now point at `MCP-ODX_Backend_XAPI_config` instead of ours; ask for it before changing that file.

A **separate Mule app** that hosts the MCP server ChatGPT talks to. The xAPI in `asc-mcp-odx-backend-xapi/` is a backend; this app is the tool-call layer in front of it. Seven files were shared. **It holds two live generations side by side**, so check which one a change belongs in.

| File | Defines |
|---|---|
| `global-config.xml` | `configuration-properties file="application_properties.yaml"`; `HTTP_Listener` (`${http.host}` / `${http.port}`); **`mcp:server-config` `asc_mcp_config`** (serverName `asc-mcp-server-1`, 1.0.0, streamable HTTP on `${mcp.endpoint}`, 30s, JSON); flow `health` (GET `/health`, reports `p("data.mode")` and `tools: 8`); **`MCP-EXP-HTTPconfig`**: plain **HTTP**, host `test-mcp-xapi-ch01.sg-s1.cloudhub.io`, port 80. |
| `mcp-tool.xml` (**rewritten by us 2026-10-28** on top of the owner's copy of that day, not yet deployed) | **Seven tools, all on our xAPI** through `call-odx-xapi` (connection `MCP-ODX_Backend_XAPI_config`, `global-config.xml`): `get_property_details` (T-02, `xapi.propertydetails.path`), `get_service_offerings` (T-03), `get_room_rate_details` (T-04, `xapi.roomdetails.path` = `/api/v1/multi-room-details`), `get_promotions` (T-05, `xapi.promotions.path`), `compare_properties` (T-06; was `compare-properties`), `compare_rooms_rates` (T-07, `xapi.comparerooms.path`), `create_booking` (T-08, `xapi.createbooking.path`). Each flow: listener → `vars.toolName` (= the tool name) / `vars.args` / `vars.xapiPath` → `log-start` → `call-odx-xapi`; `error-handler ref="generic-tool-error-handler"`. The simulated `getPromotions`, `compareRoomsAndRates` (rates across properties) and the WRITE `createBooking` are gone, so **`business-flows.xml` is no longer used by any tool**. See "Wiring the MCP tools to our xAPI". |
| `business-flows.xml` | `validate-business-input` (dates valid, check-in not past, 30-night max; `createBooking` needs `confirmed == true`), the per-tool sub-flows (`read-property`, `read-services`, `read-rates`, `read-promotions`, `compare-properties`, `compare-rates`, `create-booking`, `search-properties:post:\v2\bookingpropertylist`), the shared callers (`endpoint_CityorCountry-bookingpropertylist`, `endpoint-apartmentrateapi`, `endpoint-getPropertyInfo`, `endpoint-userReview`) and `validate-odx-status` (409 → `APP:CONFLICT`, 422 → `APP:VALIDATION`) / `log-odx-success`. Calls are **GET** `/properties/{id}/…` on `MCP-EXP-HTTPconfig` with `Authorization: Bearer p('odx.token')` and `vars.odxQuery` as query params; `create-booking` is `POST /bookings` with an `Idempotency-Key`. |
| `observability.xml` | `log-start` (sets `vars.startedAt`, `vars.traceId` = `correlationId`, logs `tool.start`), `log-success`, `wrap-success` (**wraps the body as `{success, correlationId, mode, data}`**), `log-failure` (reads `vars.publicError`). |
| `property-mcp-api.xml` | The **newer** style, for T-01 only: tool listener `find_properties` with the full PRD input schema (`countryCode` required; `city`, `checkinDate`, `checkoutDate`, `noOfadults`, `noOfchildren`, `noOfRooms`, `isLongStay`, `facilities[]`, `roomType`, `poi`, `currencyCode`, `maxRate`, `memberId`, `voucherCode`, `promotionCode`). Sets `vars.correlationId` = `uuid()`, normalises the body, **POST `/findproperties`** with `x-correlation-id` only, then `vars.mcpResponseText` = `write(payload, 'application/json')`. It uses none of the sub-flows above. |
| `tool-routes.xml` | Eight `<flow>`s (`route-findPropertiesByLocation`, `route-getPropertyDetails`, `route-getServiceOfferings`, `route-getRoomAndRateDetails`, `route-getPromotionsAndDeals`, `route-compareProperties`, `route-compareRoomsAndRates`, `route-createBooking`) that POST the payload to the matching path, accept `200..299,400,404,409,422`, then `check-process-response` (≥400 → `APP:FUNCTIONAL`). **Only `route-findPropertiesByLocation` is referenced, and only from the commented-out `findProperties` flow, so none of them runs today.** This is the shape to reuse when pointing the tools at our xAPI. |
| `mcp-html-widget.xml` | Flow `serve-html-resource-flow`: `mcp:resource-listener` serving **`ui://ascott/widget-v3.html`** (was `widget-v2.html` until the owner's copy of 2026-10-28) as `text/html;profile=mcp-app`, read from `classpath://ui/ui_widget.html`. The ChatGPT widget that renders our `structuredContent`. No tool file in this repo refers to the URI (no `openai/outputTemplate`), so the link from a tool to the widget is either in a file not shared or not set; ask before relying on it. |

**Registered tools (8, matching `health`), after our rewrite of 2026-10-28:** `find_properties` (T-01, `property-mcp-api.xml`), then from `mcp-tool.xml`: `get_property_details`, `get_service_offerings`, `get_room_rate_details`, `get_promotions`, `compare_properties`, `compare_rooms_rates`, `create_booking`, all calling our xAPI. The MCP tool name and the flow name differ in two places: flow `getPromotionsAndDeals` registers as `getPromotions`, and flow `getPropertyDetails` registers as `get_property_details`. Naming is mixed: `find_properties` and `get_property_details` are snake_case, the rest camelCase.

**History (before 2026-10-26):** the tools did not call our xAPI; they called `GET /properties/{id}/…` on `test-mcp-xapi-ch01.sg-s1.cloudhub.io:80` with a bearer token. Ours are `POST /api/v1/…` on `asc-mcp-odx-backend-xapi-1` with a JSON body and no auth. Ask the owner whether `test-mcp-xapi-ch01` is a different experience API in front of ours or a placeholder. The mapping:

| MCP tool | Calls today | `tool-routes.xml` path | Our xAPI |
|---|---|---|---|
| `find_properties` | POST `/findproperties` | `/findPropertiesByLocation` | not in our xAPI |
| `get_property_details` | GET `/properties/{propertyId}` | `/getPropertyDetails` | `POST /api/v1/property-details` |
| `getServiceOfferings` | GET `/properties/{id}/services` | `/getServiceOfferings` | `POST ${t03.http.path}` |
| `getRoomAndRateDetails` | GET `/properties/{id}/rates` | `/getRoomAndRateDetails` | `POST /api/v1/room-details` today (`mcp-tool-xapi.yaml`); **must move to `/api/v1/multi-room-details`**, since T-07 removes `/room-details` |
| `getPromotions` | GET `/properties/{id}/promotions` | `/getPromotionsAndDeals` | not built |
| `compareProperties` | GET per id, in parallel | `/compareProperties` | `POST ${t06.http.path}` |
| `compareRoomsAndRates` | GET per id, in parallel | `/compareRoomsAndRates` | not built |
| `createBooking` | POST `/bookings` | `/createBooking` | not built |

**History:** input names did not match our xAPI. The live schemas use `propertyId`, `propertyIds`, `checkIn`, `checkOut`, `adults`, `limit`, `location`. Our validators take `propertyCode` / `propertyCodes` plus the PRD names (`checkinDate`, `noOfadults`, `currencyCode`) or the short T-02 names (`checkin`, `checkout`, `adults`, `children`, `currency`). So `checkIn` / `checkOut` / `propertyId` would all be ignored and the call would fail validation. Only `find_properties` already uses PRD names. Either rename in the tool schemas or map in the route flows; prefer renaming, so ChatGPT sees one vocabulary.

**Conflicts with the PRDs (1, 2, 3 and 5 are resolved by the 2026-10-28 rewrite of `mcp-tool.xml`; 4 is why `wrap-success` is not used):**

1. **`createBooking` is declared a WRITE** that creates a reservation and requires `guest {name, email}`, `expectedTotal`, `currency`, `confirmed` and `idempotencyKey`. **The T-08 PRD is read-only**: no guest or payment details, no reservation, just a summary and an external checkout link. These are two different tools. Decide which one is being built before any T-08 work.
2. **`compareRoomsAndRates` takes `propertyIds[]`** and `compare-rates` loops over properties. **The T-07 PRD compares rooms within one property** (`propertyCode` + `roomCategoryCodes[]`). The current tool is really "compare rates across properties", not T-07.
3. **`maxItems: 5`** on `compareProperties` and `compareRoomsAndRates`, where both PRDs and our T-06 allow at most 4.
4. **`wrap-success` wraps the body** as `{success, correlationId, mode, data}`. Our responses are the bare `structuredContent` the widget's schema expects, so wrapping puts it under `data`. Confirm which shape `ui_widget.html` reads.
5. `currency` is `{"enum": ["SGD"]}` in `createBooking`, so no other currency can be booked.

**Bugs in the owner's files:**

1. **`route-findPropertiesByLocation` uses `method="CONNECT"`** where every other route uses POST. `CONNECT` is a proxy verb and will not reach the API. It only matters once that route is used again.
2. **`property-mcp-api.xml` reads `payload.curreny`** (typo), so `currency` is always the `"SGD"` default and the caller's `currencyCode` is ignored.
3. Paths disagree for the same tool across the three generations (`/findproperties` vs `/findPropertiesByLocation` vs `/properties`).
4. `validate-business-input` only checks dates when `vars.args.checkIn` is set, so `find_properties`' `checkinDate` is never validated; it also reads `vars.args`, which `property-mcp-api.xml` does not set.

**Not shared yet (ask before relying on it):** `generic-tool-error-handler` (referenced by all seven tool flows; it should set `vars.publicError`, which the error responses and `log-failure` read), `dwl/map-find-properties-response.dwl` (referenced but commented out), `src/main/resources/ui/ui_widget.html`, `application_properties.yaml` (share without secrets: it holds `odx.token`, `odx.timeout`, `http.*`, `mcp.endpoint`, `data.mode`) and `pom.xml`.

## How to work on it

- Diagnose from the audit log lines: `xapi.start` / `T04M.start` / `T05.start` / `T06.start` / `T07.start` / `T08.start`, `xapi.searchvoucher.request` / `xapi.searchvoucher.response` (T-05), `xapi.compare.batch` / `xapi.compare.batch.failed` / `xapi.compare.lookup` (T-06), `xapi.bookingsearch.request` (exact body sent), `xapi.property.response` (upstream field names), `xapi.downstream.error` (upstream status and body), `xapi.poi.unavailable`, `xapi.failure`.
- Check any response change against the tool's schema, using a sample built from real upstream data where possible.
- Hand back complete, drop-in files with the owner's config names (`common_HTTP_Listener_Config`, `HTTP_Request_Bookingsearch_config`, `Property_POI_HTTP`) and key names (`https.*`, `poisystem.*`, `t03.*`, `t06.*`).
- **Postman collection** (rebuilt 2026-10-28): `asc-mcp-odx-backend-xapi/postman/ascott-mcp-xapi.postman_collection.json` is **generated** by `postman/build_collection.py`. Edit the script, then run `python -I postman/build_collection.py`; never hand-edit the JSON.
  - **Content:** 8 folders, 73 requests: one folder per tool, T-02 to T-08 (happy paths, edge cases, every 400 / 404 / 409), plus "00 Journey", the ChatGPT order T-02 → T-04 → T-07 → T-08 → T-05.
  - **Shared scripts:** a collection pre-request sets check-in today + 21, three nights, and a fresh `X-Correlation-ID`. A collection test checks the JSON body, the echoed correlation ID and, on errors, the `{success, correlationId, error{category, code, message, retryable}}` envelope.
  - **Per-request tests:** the status. For a 200, also the tool schema's required top-level and `meta` keys, read from `schemas/` at build time, plus request-specific checks (order, counts, `resolution`, totals, error codes).
  - **Chaining:** the first T-04 request saves `pickedRoomCode`, `pickedRoomCode2` and `pickedRatePlanCode`, which the T-07 and T-08 "carried from T-04" requests use.
  - **Variables:** `propertyCode` 51052, `roomCode1..4` = its room codes.
  - **Checked here only offline:** every script passes `node --check`. The tests were also run with a small `pm` stand-in against the Python mirrors' responses; the only failures were the limits of the single 51052 / T-06 samples.
- Commit to branch `claude/get-property-details-xapi`.
- `asc-mcp-server/` holds the owner's MCP server files for reference. Change them only when asked, and keep the xAPI (`asc-mcp-odx-backend-xapi/`) and the MCP server apart: they are separate Mule apps.
