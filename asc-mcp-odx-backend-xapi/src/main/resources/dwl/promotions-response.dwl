%dw 2.0
// CPRV process API POST /v1/searchvoucher response (vars.voucherSearch: {voucher: [...], totalNumber, …}) + the request
// (vars.promotionsRequest) -> get_promotions structuredContent,
// schemas/T05-get-promotions.structured-content.schema.json 0.2.0 (the owner's file, 2026-10-28). Vouchers only.
//
// Upstream fields are those ODX_Search_Purchase_Voucher_Flow reads. That flow also merges AEM voucher details
// (voucherUrl, imageThumbnail, description, altThumbnail, urgencyTrigger); this one does not call AEM, so those fields
// are used only when searchvoucher itself sends them:
//   details_url (required)  voucherUrl, else t05.detailsFallbackPath (default "/en/member/buy-experiences")
//   image_url / image_alt   imageThumbnail / altThumbnail, else left out (the card shows its placeholder)
//   is_low_stock            inventory <= urgencyTrigger, only when urgencyTrigger is sent
//   description_text        description as plain text, only when sent and not just the voucher code
// Prices: the request asks upstream for `currency` (the request's, else property.currency), so price =
// preferredCurrencyPromoPrice (else promoPrice) and meta.currency = that currency. A voucher bought with points only
// (no price, points > 0) has no price.
// Kept: not private, with a code and a title, matching voucherName / voucherCategory, and in scope for the request
// (country-wide vouchers of the country, or property vouchers listing the requested propertyCode); upstream should do
// this already, it is repeated here in case it does not. Order: upstream `sequence`, then upstream order.
output application/json skipNullOn="everywhere"
import try from dw::Runtime

var req = vars.promotionsRequest default {}
var resp = vars.voucherSearch default {}

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if (v is Number) (v as String) else null
fun num(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun list(v) = (if (v is Array) (v map text($)) else if (v is String) ((v splitBy ",") map text($)) else []) filter ($ != null) distinctBy $
fun money(n) = round(n * 100) / 100

// Country names for the English labels; any other code is shown as the code.
var countryNames = {
	SG: "Singapore", MY: "Malaysia", ID: "Indonesia", TH: "Thailand", VN: "Vietnam", PH: "Philippines", KH: "Cambodia",
	MM: "Myanmar", LA: "Laos", CN: "China", HK: "Hong Kong", TW: "Taiwan", MO: "Macau", JP: "Japan", KR: "South Korea",
	IN: "India", LK: "Sri Lanka", AU: "Australia", NZ: "New Zealand", GB: "United Kingdom", IE: "Ireland", FR: "France",
	DE: "Germany", BE: "Belgium", ES: "Spain", TR: "Türkiye", GE: "Georgia", AE: "United Arab Emirates",
	SA: "Saudi Arabia", QA: "Qatar", BH: "Bahrain", OM: "Oman", KW: "Kuwait", US: "United States"
}
fun countryName(c) = countryNames[c] default c

fun isoDate(v) = do {
	var s = text(v)
	---
	if (s == null) null
	else if (s matches /^\d{4}-\d{2}-\d{2}.*/) s[0 to 9]
	else try(() -> (s as Date {format: "dd/MM/yyyy"}) as String {format: "yyyy-MM-dd"}).result
		default try(() -> (s as Date {format: "MM/dd/yyyy"}) as String {format: "yyyy-MM-dd"}).result
}

// A full URL with the doubled "/" after the host collapsed, or a path starting with exactly one "/".
fun detailsUrl(v) = do {
	var s = text(v)
	---
	if (s == null) null
	else if (s matches /^https?:\/\/.*/) (s replace /^(https?:\/\/[^\/]+)\/+/ with ((m) -> m[1] ++ "/"))
	else "/" ++ (s replace /^\/+/ with "")
}

fun plain(v) = do {
	var s = text(v)
	var breaks = if (s == null) "" else ((s replace /(?i)<\s*br\s*\/?>/ with "\n") replace /(?i)<\/p>/ with "\n\n")
	var noTags = breaks replace /<[^>]*>/ with ""
	var decoded = ((((((noTags replace /&nbsp;/ with " ") replace /&lt;/ with "<") replace /&gt;/ with ">")
		replace /&quot;/ with "\"") replace /&#39;/ with "'") replace /&amp;/ with "&")
	var spaced = ((decoded replace /[ \t]+/ with " ") replace /\s*\n\s*\n\s*/ with "\n\n") replace /[ \t]*\n[ \t]*/ with "\n"
	var t = trim(spaced)
	---
	if (t == "") null else t
}

fun voucher(v) = do {
	var id = text(v.voucherProgrammeCode)
	var level = lower(text(v.applicableLevel) default "")
	var props = list(v.propertyCode)
	var countries = (list(v.countryCode) map upper($)) filter ($ matches /^[A-Z]{2}$/)
	var price = num(v.preferredCurrencyPromoPrice) default num(v.promoPrice)
	var points = do { var p = num(v.points) --- if ((p != null) and (p > 0)) floor(p) else null }
	var inventory = do { var n = num(v.inventory) --- if ((n != null) and (n >= 0)) floor(n) else null }
	var trigger = num(v.urgencyTrigger)
	var description = plain(v.description)
	---
	{
		id: id,
		title: text(v.voucherTitle) default text(v.voucherEnTitle),
		image_url: text(v.imageThumbnail),
		image_alt: text(v.altThumbnail),
		// Country-wide vouchers only: naming a property or its city needs the ASR property cache, not called here.
		scope_label: if ((level == "country") and !isEmpty(countries)) ((countries map countryName($)) joinBy ", ") else null,
		scope_level: if (level == "property_specific") "property" else if (level == "country") "country" else null,
		property_codes: if (isEmpty(props)) null else props,
		country_codes: if (isEmpty(countries)) null else countries,
		expiry_date: isoDate(v.expiryDate),
		details_url: detailsUrl(v.voucherUrl) default detailsUrl(p('t05.detailsFallbackPath') default "/en/member/buy-experiences"),
		category: text(v.category),
		price: if ((price == null) or ((price <= 0) and (points != null))) null else if (price < 0) null else money(price),
		points: points,
		remaining: inventory,
		is_low_stock: if ((inventory != null) and (trigger != null)) inventory <= trigger else null,
		description_text: if ((description == null) or (lower(description) == lower(id default ""))) null else description,
		// Not output: used by the filters below.
		_private: lower(text(v."private") default "") == "yes" or v."private" == true,
		_sequence: num(v.sequence) default 999999
	}
}

fun inScope(x) = do {
	var countryOk = (x.country_codes == null) or (x.country_codes contains req.countryCode)
	var propertyOk = (req.propertyCode == null) or (x.scope_level == "country") or (x.property_codes == null)
		or (x.property_codes contains req.propertyCode)
	---
	countryOk and propertyOk
}

var categories = (req.voucherCategory default []) map lower($)
var vouchers = ((objects(resp.voucher) map voucher($))
	filter ((x) -> (x.id != null) and (x.title != null) and !x._private and inScope(x)
		and ((req.voucherName == null) or (lower(x.title) contains lower(req.voucherName)))
		and (isEmpty(categories) or (categories contains lower(x.category default "")))))
	orderBy $._sequence
	distinctBy $.id
	map ($ - "_private" - "_sequence")
---
{
	meta: {
		country_code: req.countryCode,
		city: req.city,
		property_code: req.propertyCode,
		// property_name is not sent: resolving it needs a booking search call, which this minimal flow does not make.
		location_label: req.city default countryName(req.countryCode),
		applied_filters: if ((req.voucherName == null) and (req.voucherCategory == null)) null
			else {voucher_name: req.voucherName, voucher_category: req.voucherCategory},
		currency: if (isEmpty(vouchers filter ($.price != null))) null else req.currency,
		voucher_count: sizeOf(vouchers),
		asset_base_url: p('asset.baseUrl') default "https://www.discoverasr.com"
	},
	vouchers: vouchers
}
