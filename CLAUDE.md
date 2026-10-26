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
| T-02 `get_property_details` | `/api/v1/property-details` | `get-property-details.xml` | `schemas/T02-get-property-details.structured-content.schema.json` (**0.6.0**, owner's file 2026-10-26) |
| T-03 `get_service_offerings` | `${t03.http.path}` (`/api/v1/service-offerings`) | `get-service-offerings.xml` | `schemas/T03-get-service-offerings.structured-content.schema.json` (0.1.0) |
| T-04 `get_room_rate_details` | `/api/v1/room-details` | `get-room-rates.xml` | `schemas/T04-get-room-rate-details.structured-content.schema.json` (**0.3.0**, owner's file 2026-10-26) |
| T-06 `compare_properties` | `${t06.http.path}` (`/api/v1/compare-properties`) | `compare-properties.xml` | `schemas/T06-compare-properties.structured-content.schema.json` (0.2.0, written by us from PRD §6.1) |

Every response body is the tool's `structuredContent`, exactly as its schema defines it. Errors are `{success: false, correlationId, error: {category, code, message, retryable}}`. The caller's `X-Correlation-ID` (`^[A-Za-z0-9_-]{1,80}$`) is reused as `vars.traceId` and returned as a header.

## Files in the base and what they define

| File | Defines | Notes |
|---|---|---|
| `global-config.xml` | `common_HTTP_Listener_Config`; `HTTP_Request_Bookingsearch_config` (`https.bookingsearchprocessapi.*`, TLS insecure, config-level validator `${validation.successcodes}`); `Property_POI_HTTP` and `HTTP_Request_POI_System_config` (`poisystem.*`); `HTTP_Request_configuration_InternalCommonServices`; plus AEM configs `HTTP_Request_configuration1` / `HTTPS_Request_configuration-dynamic`, the caching strategy and the object store. | The AEM configs, the commonservices config, the caching strategy and the object store are not used by T-02/03/04. |
| `validate-request.xml` | `common-validate-request`: runs `dwl/validate-request.dwl` and sets `vars.validation` and **`vars.request`**; raises `APP:BAD_REQUEST`. | It catches every `MULE:EXPRESSION` error as "Request body must be valid JSON.", which hides missing-property errors. The real reason is in the ERROR log line `validate-request.dwl failed: …`. |
| `get-common-details.xml` | `get-property-common-info`: builds the body from `dwl/property-info-request.dwl` (reads **`vars.request`**), logs `xapi.bookingsearch.request`, POSTs booking search, 404 → `APP:NOT_FOUND`, `dwl/unwrap-property.dwl` → **`vars.property`** (the `propertyList[0]` object), logs `xapi.property.response` (field names only). It raises `APP:NOT_FOUND` when the response has no code or name. | This is the shared booking search call. |
| `get-poi-details.xml` | `get-property-pois`: only when `vars.request.maxPois > 0`; `dwl/poi-request.dwl`, POST `${poisystem.path}` via `Property_POI_HTTP` → `vars.pois`. Any error → `vars.pois = null`, logged as `xapi.poi.unavailable`. | Optional: never fails the call. |
| `get-property-details.xml` | Flow `get-property-details` (T-02): `common-validate-request` → `get-property-info` → `vars.propertyCode` → `get-property-pois` → `dwl/map-structured-content.dwl` → `xapi.success`; error handler `property-details-error-handler`. Sub-flow `get-property-info` = `get-property-common-info`, then unwraps, logs and checks again. | Its old `validate-request` and `get-property-pois` copies are commented out (moved to `validate-request.xml` / `get-poi-details.xml`). |
| `get-service-offerings.xml` | Flow `get-service-offerings` (T-03; sets `vars.toolName`): `services-validate-request` (parses the body first, so only bad JSON gives "invalid JSON"; requires a digits-only `propertyCode`; adds a default stay from `default.*`) → **`vars.servicesRequest`**. Then `services-get-facilities` copies it into `vars.request`, calls booking search **itself** (not via `get-property-common-info`) and selects the `propertyList` entry → **`vars.servicesSource`**. Then `services-map-response` → `{meta, services[]}`; **changed by us 2026-10-26** from inline DataWeave to `<ee:set-payload resource="dwl/service-offerings.dwl"/>` (see "T-03 mapping"). Error handler `property-details-error-handler`. | Its header comment is out of date (it names `Property_Info_HTTP` and `property.*`; the flow uses `HTTP_Request_Bookingsearch_config` and `https.bookingsearchprocessapi.*`). |
| `get-room-rates.xml` | Flow `get-room-details`; sub-flows `rooms-get-rates`, `rooms-map-response`; `rooms-error-handler`; `rooms-format-and-log-error`. | See the known issues below. |
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
- T-06: `t06.{http.path, minProperties, maxProperties, checkinOffsetDays, nights, adults, children, batchLookup, batchSize, maxConcurrency, maxAmenityHighlights, maxRoomTypes}`, in `src/main/resources/compare-properties.yaml` (to append to `uat.yaml`).
- A missing key read with `p()` gives null, and `null as Number` fails the request. `uat.yaml` has `startdate: 7`, `enddate: 8`, `noofadults: 2`, the defaults other booking search callers use. A check-in of tomorrow in UTC can already be "today" in Singapore.

## Known issues in the base (2026-10-25)

`get-room-rates.xml`:
1. It validates with `common-validate-request`, which sets `vars.request` without `nights` or `rooms`. Its own `rooms-validate-request` is commented out, so **`vars.roomsRequest` is never set**. `rooms-get-rates` (roomsSource selection) and `rooms-map-response` read `vars.roomsRequest`, so dates and nights come out null.
2. `rooms-map-response` is still the **old flat mapping** (`apartments[]`, `apartment_count`), not the T-04 schema. Replace its body with `<ee:set-payload resource="dwl/room-rate-details.dwl"/>`, which needs `vars.roomsSource` and `vars.roomsRequest` (no `nights`: 0.3.0 passes upstream's prices through). See "T-04 mapping" below.
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
- `src/main/resources/dwl/*`: `validate-request.dwl`, `property-info-request.dwl`, `unwrap-property.dwl` and `poi-request.dwl`. Until the deployed versions arrive, assume the versions in `ascott.mcp.get-property-details.xapi/src/main/resources/dwl/` at commit `76aa457`. (`map-structured-content.dwl` for T-02 is now in the base: see "T-02 mapping" below.)
- `uat.yaml` (share without secrets) and `pom.xml`.

## T-02 mapping (`dwl/map-structured-content.dwl`, written by us 2026-10-26, not yet deployed)

Maps `vars.property` (one `propertyList[]` entry) + `vars.pois` + `vars.request` to T-02 schema **0.6.0**. Same file name and inputs as the version the T-02 flow already references, so it is a drop-in replacement.

- **Checked against the real 51052 (Ascott Raffles Place) booking search response**, stored at `examples/upstream-property-details-51052.json`. `tests/check_t02.py` is a function-for-function Python copy that writes `examples/property-details-51052-response.sample.json` and runs 23 checks (that sample, no stay in the request, `childAges`, no rate, POIs, the best-rate text, a bare property); all validate against 0.6.0. Keep the two in step. The DataWeave itself has not been run here: a downloaded runtime may not be executed in this session. `tests/playground/map-structured-content.playground.dwl` + `-input.json` run it in the DataWeave Playground.
- **Rules worth knowing:**
  - `brand_code`: upstream `brand`, else slug of `brandName` ("Ascott The Residence" → `ascott-the-residence`). The 51052 response has no `brand` field.
  - `thumbnail_url` (required): `newPropertyThumbnail` → `bannerImageMobile` → first gallery image → first room's `thumbnailImage` / `bannerImageMobile` → `location.mapImage`.
  - `pricing`: property-level `perNightRatePrefCurr` / `totalStayRatePrefCurr` (**ex-tax, as upstream gives them**; unlike T-04, which adds tax). `strikethrough_rate` comes from the rate plan whose per-night rate equals the lead-in (51052: `ASRAPPFX` 211.50 → 940.00), kept only when higher. No rate → `on_request`.
  - `based_on`: the request's stay; when the request has none, the first and last+1 `nightlyRate` dates (`MM/dd/yyyy`). `adults` ≥ 1 (default 1), `children` default 0. `child_ages` from `vars.request.childAges`, **which `validate-request.dwl` does not set yet**, so it is absent until the validator passes it.
  - `hotel_information.check_in_time` / `check_out_time`: upstream "03:00 PM" → "15:00" (schema is 24-hour).
  - `location`: coordinates are converted to numbers; `gettingToProperty` / `publicTransport` titles have upstream's `{0}` replaced with the property name.
  - `amenities.facility_groups` from `facilities.facilityGroup`: label = `description`, else `name` (e.g. "Residents' lounge" has a null description); rows without label or icon dropped; **de-duplicated within and across groups** (schema: "De-duplicated by the server"), so groups left empty disappear (51052: "Business Matters").
  - `reviews`: booking search has none → `{average_ratings: 0, total_number_of_reviews: 0}`, kept as an empty shell.
  - `nearby`: from `vars.pois`, max 5, POIs missing any required field dropped; `[]` when none (the POI mock answers 400 today).
  - `accessibility_note`: the `tag[].susstainable.allItems[]` item whose `identityName` is "Accessibility" (title = its label, body = its tooltip with HTML stripped). Absent when upstream has no such item.
  - `best_rate_guaranteed`: upstream only has the `isBestRateGuaranteeEnabled` flag, so the sentence is the optional key `t02.bestrateguaranteedtext` (`src/main/resources/property-details.yaml`). Not set → no cell.
  - `awards` from `listOfAwards` (image + title), `gallery` titles fall back to the property name (upstream sends "").
- **Required in the schema with no fallback:** `location.address` and `location.coordinates`. Both are present in the booking search response; a property without them would not validate.

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
- **Wiring still needed in `get-room-rates.xml`** (known issues 1–2, unchanged): `vars.roomsRequest` is never set, and `rooms-map-response` still holds the old flat mapping. Point it at `<ee:set-payload resource="dwl/room-rate-details.dwl"/>` and set `vars.roomsRequest` / `vars.roomsSource`. `nights` is no longer needed by the mapping (prices are not divided any more).

## T-06 in this app (owner decision, 2026-10-25)

**T-06 only puts the requested properties together in one payload. It does not compare, rank, filter or recommend.** The model and the widget do that. So the PRD's `recommendation` block, `is_recommended`, match flags, reason lines and the filter inputs (`maxRate`, `facilities`, `roomType`, `poi`, `travellerProfile`, `serviceCategory`) are not in the xAPI. They are accepted in the body and ignored. Do not add them back unless the owner asks.

- **Request:** `propertyCodes[]` (2–4 distinct codes; duplicates removed, codes past the 4th dropped and echoed in `meta.dropped_property_codes`), `checkinDate` (default today + 30), `checkoutDate` (default check-in + 1), `noOfadults` (default 1), `noOfchildren` (default 0), `currencyCode`, `language`. The T-02 names (`checkin`, `adults`, `currency`, …) also work.
- **Lookup (`compare-get-properties`):**
  1. If `t06.batchLookup` is "true" (**default "false"** since 2026-10-25), `compare-batch-lookup` makes one booking search call. It sends the `property-info-request.dwl` body with `propertyListing: true` and `propertyCode` set to the first `t06.batchSize` (3) codes. The reference caller allows at most 3 codes with `propertyListing` true, and exactly 1 with false. **In UAT (2026-10-25) the cards came back empty except code and name**, so the batch call most likely returns slim listing entries. Hence the default "false", and a batch entry is now used only when it has `apartments` and a `location` object; otherwise the code is fetched one by one. The `xapi.compare.batch` log lists each entry's field names. Any failure leaves `vars.batchList` empty (log `xapi.compare.batch.failed`).
  2. Every code not returned by the batch call with full details (`apartments` array and `location` object) goes through `compare-single-lookup` in a `parallel-foreach` (`t06.maxConcurrency`). That calls the shared `get-property-common-info`, one code at a time. `APP:NOT_FOUND` → status `not_found`; any other error → `unavailable` (logged as `xapi.downstream.error` with the code).
  3. `vars.lookups` = one `{code, status, source: batch|single, property}` per requested code, in request order.
- **Errors:** none found → 404 `PROPERTIES_NOT_FOUND`; none returned and at least one lookup failed → 502 `DOWNSTREAM_UNAVAILABLE`; at least one found → 200, with the rest in `missing_properties[]` (`not_found` / `lookup_failed`).
- **Response:** `{meta, properties[], missing_properties[]}`.
  - Cards are in request order. Every card has every key; a value upstream lacks is `null` (PRD EC-10).
  - Card fields:
    - `property_code`, `property_name`, `property_type`, `brand_name`;
    - `is_asr` from `asrParticipating`;
    - `brand_logo_url` from `brandlogo`;
    - `banner_image_url` from `bannerImageMobile`, else `newPropertyThumbnail`, else the first gallery image;
    - `card_location_line` from the city and country;
    - `location {area_label, district_label, country_code}`;
    - `rating`: null, because booking search has no reviews (PRD source `v1/propertyreviews` is not integrated);
    - `max_person_in_room`: the largest `maxOccupancy`;
    - `room_types[]`: room names with a bookable rate;
    - `amenity_highlights[] {label, icon_url}`: from `facilities.facilityGroup`, with the `facilities-amenities` group first. This assumes the same path as T-02's amenities, which is unconfirmed;
    - `pricing`: this property's own cheapest bookable rate under the T-04 rate filter, **tax included** (stay + `totalTaxPrefCurrency`, ÷ nights), with `availability_status` `on_request` when it has none. T-04's own schema 0.3.0 no longer adds the tax; T-06 still does, since its schema says tax-inclusive. Change both together if that is revisited. `next_available_date` is always null.
- **Checks:** `asc-mcp-odx-backend-xapi/tests/check_t06.py` is a Python copy of the response DataWeave. It builds `examples/compare-properties-response.sample.json` from the 8790 and 8791 samples, runs not-found, on-request and T-02-shaped cases, and validates them against the schema. Keep it in step with the DataWeave. The DataWeave itself has not been run here (no runtime).
- **Known issues:** `compare-batch-lookup` is a fourth copy of the booking search `http:request` (see issue 8). The batch path is unconfirmed (above). Set `t06.batchLookup: "false"` to use only one-by-one calls.
- **Postman:** `asc-mcp-odx-backend-xapi/postman/ascott-mcp-xapi.postman_collection.json` (T-02/03/04 plus a T-06 folder). Set `propertyCode4` to a real 4th code.

## Wiring the MCP tools to our xAPI (added by us 2026-10-26, not yet deployed)

`asc-mcp-server/src/main/mule/mcp-tool.xml` now calls the ODX backend xAPI for the four tools it serves. Only that file changed; `asc-mcp-server/src/main/resources/mcp-tool-xapi.yaml` holds the keys to append to `application_properties.yaml`.

- **New in `mcp-tool.xml`:** `http:request-config` **`ODX_Backend_XAPI_config`** (`${xapi.protocol}` / `${xapi.host}` / `${xapi.port}`) and sub-flow **`call-odx-xapi`**. The owner's `MCP-EXP-HTTPconfig` is left alone for the tools that still use it.
- **`call-odx-xapi`:** builds `vars.xapiRequest` from `vars.args` (`skipNullOn="everywhere"`), logs `xapi.request` with the exact body, POSTs to `vars.xapiPath` with `Content-Type` and `X-Correlation-ID` = `vars.traceId`, then leaves the xAPI's `structuredContent` in **`vars.toolResponse`**.
- **`wrap-success` is deliberately not used** on these four: the widget expects the bare `structuredContent`, and `wrap-success` would bury it under `data`.
- **`validate-business-input` is deliberately not called** on these four: it reads `vars.args.checkIn` (camelCase), which none of these schemas use, and the xAPI validates the stay itself and answers `BAD_REQUEST`.
- **Errors:** the validator accepts `200..299,400,404,409,422,500,502,504` so the xAPI's own error body survives. On a status ≥ 400 the flow sets `vars.publicError` from `payload.error` (falling back to a `DOWNSTREAM_ERROR` object when the body is not readable), sets `vars.httpStatus`, calls `log-failure` and raises **`APP:XAPI_REJECTED`**. The listeners' existing `mcp:on-error-responses` already renders `vars.publicError`.
- **Tool names are unchanged**, so nothing breaks for the widget: `get_property_details`, `getServiceOfferings`, `getRoomAndRateDetails`, `compareProperties`.
- **Input schemas were rewritten to our xAPI's own field names** (they previously used `propertyId` / `checkIn` / `adults`, which our validators ignore):
  - `get_property_details`: `propertyCode` **or** `propertyName` (draft-07 `anyOf`), `checkin`, `checkout`, `adults`, `children`, `currency`, `language`, `maxPois`.
  - `getServiceOfferings`: `propertyCode` (digits only, as T-03 requires), `language`.
  - `getRoomAndRateDetails`: `propertyCode` required, plus the same stay fields.
  - `compareProperties`: `propertyCodes[]` (2–4, unique), `checkinDate`, `checkoutDate`, `noOfadults`, `noOfchildren`, `currencyCode`, `language`.
- **Confirm before deploying:** `xapi.host` and `xapi.port`. The YAML defaults to the public CloudHub URL on port 80; if both apps sit in the same VPC use the `mule-worker-internal-*` host on 8081.
- **Untouched:** `getPromotions` and `createBooking` still call `business-flows.xml` (`GET /properties/{id}/promotions`, `POST /bookings` on `MCP-EXP-HTTPconfig`), because our xAPI has no T-05 or T-08. `createBooking` is still the write-style tool that conflicts with the T-08 PRD.

## Product specs (PRDs) for tools not yet built

Full text: `asc-mcp-odx-backend-xapi/docs/PRD-T05-get-promotions.md`, `PRD-T06-compare-properties.md`, `PRD-T07-compare-rooms-rates.md` (pasted as text by the owner) and `PRD-T08-create-booking.md`. Read the full PRD before you build a tool. No flow exists for T-05, T-07 or T-08 yet; build one only when asked. T-06 is built as a pass-through only: where the PRD below and "T-06 in this app" disagree, the latter wins.

Tool map from the PRDs:

| Tool | Name | Status in this app |
|---|---|---|
| T-01 | Search properties | not in this app |
| T-02 | Get_property_details | built |
| T-03 | Get_service_offerings | built |
| T-04 | Get_room_rate_details | built (issues 1–6) |
| T-05 | Get_promotions | PRD only |
| T-06 | Compare_properties | built: puts properties together only (see below) |
| T-07 | Compare_rooms_rates | PRD only |
| T-08 | Create_booking | PRD only |

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

A **separate Mule app** that hosts the MCP server ChatGPT talks to. The xAPI in `asc-mcp-odx-backend-xapi/` is a backend; this app is the tool-call layer in front of it. Seven files were shared. **It holds two live generations side by side**, so check which one a change belongs in.

| File | Defines |
|---|---|
| `global-config.xml` | `configuration-properties file="application_properties.yaml"`; `HTTP_Listener` (`${http.host}` / `${http.port}`); **`mcp:server-config` `asc_mcp_config`** (serverName `asc-mcp-server-1`, 1.0.0, streamable HTTP on `${mcp.endpoint}`, 30s, JSON); flow `health` (GET `/health`, reports `p("data.mode")` and `tools: 8`); **`MCP-EXP-HTTPconfig`**: plain **HTTP**, host `test-mcp-xapi-ch01.sg-s1.cloudhub.io`, port 80. |
| `mcp-tool.xml` | **The tool listeners.** Seven live flows, plus `findProperties` commented out. **Changed by us 2026-10-26:** the four tools our xAPI serves (`get_property_details`, `getServiceOfferings`, `getRoomAndRateDetails`, `compareProperties`) now go `log-start` → `call-odx-xapi` and POST to the xAPI; see "Wiring the MCP tools to our xAPI" below. `getPromotions` and `createBooking` are untouched and still go `log-start` → `validate-business-input` → their `business-flows.xml` sub-flow → `wrap-success`. All eight keep `error-handler ref="generic-tool-error-handler"`. This file also now holds `ODX_Backend_XAPI_config` and the `call-odx-xapi` sub-flow. |
| `business-flows.xml` | `validate-business-input` (dates valid, check-in not past, 30-night max; `createBooking` needs `confirmed == true`), the per-tool sub-flows (`read-property`, `read-services`, `read-rates`, `read-promotions`, `compare-properties`, `compare-rates`, `create-booking`, `search-properties:post:\v2\bookingpropertylist`), the shared callers (`endpoint_CityorCountry-bookingpropertylist`, `endpoint-apartmentrateapi`, `endpoint-getPropertyInfo`, `endpoint-userReview`) and `validate-odx-status` (409 → `APP:CONFLICT`, 422 → `APP:VALIDATION`) / `log-odx-success`. Calls are **GET** `/properties/{id}/…` on `MCP-EXP-HTTPconfig` with `Authorization: Bearer p('odx.token')` and `vars.odxQuery` as query params; `create-booking` is `POST /bookings` with an `Idempotency-Key`. |
| `observability.xml` | `log-start` (sets `vars.startedAt`, `vars.traceId` = `correlationId`, logs `tool.start`), `log-success`, `wrap-success` (**wraps the body as `{success, correlationId, mode, data}`**), `log-failure` (reads `vars.publicError`). |
| `property-mcp-api.xml` | The **newer** style, for T-01 only: tool listener `find_properties` with the full PRD input schema (`countryCode` required; `city`, `checkinDate`, `checkoutDate`, `noOfadults`, `noOfchildren`, `noOfRooms`, `isLongStay`, `facilities[]`, `roomType`, `poi`, `currencyCode`, `maxRate`, `memberId`, `voucherCode`, `promotionCode`). Sets `vars.correlationId` = `uuid()`, normalises the body, **POST `/findproperties`** with `x-correlation-id` only, then `vars.mcpResponseText` = `write(payload, 'application/json')`. It uses none of the sub-flows above. |
| `tool-routes.xml` | Eight `<flow>`s (`route-findPropertiesByLocation`, `route-getPropertyDetails`, `route-getServiceOfferings`, `route-getRoomAndRateDetails`, `route-getPromotionsAndDeals`, `route-compareProperties`, `route-compareRoomsAndRates`, `route-createBooking`) that POST the payload to the matching path, accept `200..299,400,404,409,422`, then `check-process-response` (≥400 → `APP:FUNCTIONAL`). **Only `route-findPropertiesByLocation` is referenced, and only from the commented-out `findProperties` flow, so none of them runs today.** This is the shape to reuse when pointing the tools at our xAPI. |
| `mcp-html-widget.xml` | Flow `serve-html-resource-flow`: `mcp:resource-listener` serving `ui://ascott/widget-v2.html` as `text/html;profile=mcp-app`, read from `classpath://ui/ui_widget.html`. The ChatGPT widget that renders our `structuredContent`. |

**Registered tools (8, matching `health`):** `find_properties` (T-01, `property-mcp-api.xml`), then from `mcp-tool.xml`: `get_property_details`, `getServiceOfferings`, `getRoomAndRateDetails`, `getPromotions`, `compareProperties`, `compareRoomsAndRates`, `createBooking`. The MCP tool name and the flow name differ in two places: flow `getPromotionsAndDeals` registers as `getPromotions`, and flow `getPropertyDetails` registers as `get_property_details`. Naming is mixed: `find_properties` and `get_property_details` are snake_case, the rest camelCase.

**It does not call our xAPI.** The live tools call `GET /properties/{id}/…` on `test-mcp-xapi-ch01.sg-s1.cloudhub.io:80` with a bearer token. Ours are `POST /api/v1/…` on `asc-mcp-odx-backend-xapi-1` with a JSON body and no auth. Ask the owner whether `test-mcp-xapi-ch01` is a different experience API in front of ours or a placeholder. The mapping:

| MCP tool | Calls today | `tool-routes.xml` path | Our xAPI |
|---|---|---|---|
| `find_properties` | POST `/findproperties` | `/findPropertiesByLocation` | not in our xAPI |
| `get_property_details` | GET `/properties/{propertyId}` | `/getPropertyDetails` | `POST /api/v1/property-details` |
| `getServiceOfferings` | GET `/properties/{id}/services` | `/getServiceOfferings` | `POST ${t03.http.path}` |
| `getRoomAndRateDetails` | GET `/properties/{id}/rates` | `/getRoomAndRateDetails` | `POST /api/v1/room-details` |
| `getPromotions` | GET `/properties/{id}/promotions` | `/getPromotionsAndDeals` | not built |
| `compareProperties` | GET per id, in parallel | `/compareProperties` | `POST ${t06.http.path}` |
| `compareRoomsAndRates` | GET per id, in parallel | `/compareRoomsAndRates` | not built |
| `createBooking` | POST `/bookings` | `/createBooking` | not built |

**Input names do not match our xAPI.** The live schemas use `propertyId`, `propertyIds`, `checkIn`, `checkOut`, `adults`, `limit`, `location`. Our validators take `propertyCode` / `propertyCodes` plus the PRD names (`checkinDate`, `noOfadults`, `currencyCode`) or the short T-02 names (`checkin`, `checkout`, `adults`, `children`, `currency`). So `checkIn` / `checkOut` / `propertyId` would all be ignored and the call would fail validation. Only `find_properties` already uses PRD names. Either rename in the tool schemas or map in the route flows; prefer renaming, so ChatGPT sees one vocabulary.

**Conflicts with the PRDs to raise with the owner:**

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

- Diagnose from the audit log lines: `xapi.start` / `T04.start` / `T06.start`, `xapi.compare.batch` / `xapi.compare.batch.failed` / `xapi.compare.lookup` (T-06), `xapi.bookingsearch.request` (exact body sent), `xapi.property.response` (upstream field names), `xapi.downstream.error` (upstream status and body), `xapi.poi.unavailable`, `xapi.failure`.
- Check any response change against the tool's schema, using a sample built from real upstream data where possible.
- Hand back complete, drop-in files with the owner's config names (`common_HTTP_Listener_Config`, `HTTP_Request_Bookingsearch_config`, `Property_POI_HTTP`) and key names (`https.*`, `poisystem.*`, `t03.*`, `t06.*`).
- Commit to branch `claude/get-property-details-xapi`.
- `asc-mcp-server/` holds the owner's MCP server files for reference. Change them only when asked, and keep the xAPI (`asc-mcp-odx-backend-xapi/`) and the MCP server apart: they are separate Mule apps.
