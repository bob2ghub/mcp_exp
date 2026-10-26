%dw 2.0
// Booking search property (vars.servicesSource = one propertyList[] entry) + the request (vars.servicesRequest)
// -> get_service_offerings structuredContent, schemas/T03-get-service-offerings.structured-content.schema.json 0.1.0.
// Services are the property's facilities: one service per facilities.facilityDetails[] item, in upstream order.
// Optional fields upstream leaves empty are left out. Checked against the real 51052 response by tests/check_t03.py.
output application/json skipNullOn="everywhere"

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if (v is Number) (v as String) else null
fun first(o, keys) = if (o is Object) ((keys map ((k) -> text(o[k]))) filter ($ != null))[0] else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun obj(v) = if (v is Object) v else {}
// brand_code: upstream `brand`, else a slug of brandName ("Ascott The Residence" -> "ascott-the-residence").
fun slug(v) = do {
	var s = (lower(text(v) default "") replace /[^a-z0-9]+/ with "-") replace /^-+|-+$/ with ""
	---
	if (s == "") null else s
}

var src = obj(vars.servicesSource)
var req = obj(vars.servicesRequest)
var assetBaseUrl = text(p('t03.assetbaseurl')) default text(p('asset.baseUrl')) default "https://www.discoverasr.com"
// external_service_url must be an absolute URI: a site-relative facilityUrl is resolved against the asset base URL.
fun absoluteUrl(v) = do {
	var s = text(v)
	---
	if (s == null) null
	else if (s matches /^https?:\/\/\S+$/) s
	else if (s matches /^\/\S*$/) assetBaseUrl ++ s
	else null
}
// meta.property_code must be digits only.
fun digits(v) = do { var s = text(v) --- if ((s != null) and (s matches /^[0-9]+$/)) s else null }

var services = objects(obj(src.facilities).facilityDetails) map ((f) -> {
	service_name: first(f, ["title", "name"]),
	service_location: first(f, ["location"]),
	operating_hours: first(f, ["operatingHours"]),
	description: first(f, ["description"]),
	thumbnail_url: first(f, ["thumbnailImage"]),
	// Reserved by the schema: facilityDetails has no phone today.
	contact_number: first(f, ["contactNumber", "phone"]),
	external_service_url: absoluteUrl(f.facilityUrl)
}) filter ($.service_name != null)
var countryCode = upper(first(src, ["countryCode"]) default "")
---
{
	meta: {
		property_code: digits(req.propertyCode) default digits(src.propertyCode),
		property_name: first(src, ["propertyEnName", "propertyName"]) default text(req.propertyCode),
		brand_code: slug(src.brand) default slug(src.brandName) default "ascott",
		country_code: if (countryCode matches /^[A-Z]{2}$/) countryCode else null,
		phone: first(src, ["phone"]),
		asset_base_url: assetBaseUrl,
		total_results: sizeOf(services)
	},
	services: services
}
