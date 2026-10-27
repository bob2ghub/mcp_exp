%dw 2.0
// Bookings process API POST /v1/addonlist response (payload) -> create_booking `add_ons[]` {title, description,
// image_url, price}, or null when there is nothing usable (the widget hides the row; schema: optional and RESERVED).
//
// UNCONFIRMED: no sample addonlist response has been shared yet, so the field names below are the likely ones, tried
// in order. The flow logs `xapi.addons.response` with the response's field names; fix the lists here from that log.
//   list:        the payload itself when it is an array, else every array under a key containing "addon" (any case);
//                entries that themselves hold such an array (per-room answers) are flattened one level.
//   title:       addOnName, addonName, title, name, addOnTitle
//   description: shortDescription, description, addOnDescription (HTML tags stripped, first line only)
//   image_url:   imageUrl, image, imagePath, thumbnailImage, thumbnail
//   price:       preferredCurrencyPrice, priceInPrefCurrency, prefCurrPrice, price, amount, unitPrice (number >= 0)
// Entries without a title are dropped; titles are de-duplicated (one row per add-on, whichever room offered it).
output application/json skipNullOn="everywhere"
import try from dw::Runtime

fun text(v) = if (v is String) (if (isBlank(v)) null else trim(v)) else if (v is Number) (v as String) else null
fun num(v) = if (v is Number) v else if ((v is String) and !isBlank(v)) try(() -> trim(v) as Number).result else null
fun objects(v) = if (v is Array) (v filter ($ is Object)) else []
fun firstText(o, keys) = (keys map text(o[$]) filter ($ != null))[0]
fun firstNum(o, keys) = (keys map num(o[$]) filter ($ != null))[0]
fun addOnArrays(o) = if (o is Object) flatten((o pluck ((v, k) -> if ((lower(k as String) contains "addon") and (v is Array)) objects(v) else [])))
	else []
fun oneLine(s) = do {
	var plain = if (s == null) null else trim((s replace /<[^>]*>/ with " ") replace /\s+/ with " ")
	---
	if ((plain == null) or (plain == "")) null else plain
}

var top = if (payload is Array) objects(payload) else addOnArrays(payload)
// A per-room answer: entries that hold their own add-on list contribute that list instead of themselves.
var entries = flatten(top map ((e) -> do { var inner = addOnArrays(e) --- if (isEmpty(inner)) [e] else inner }))
var mapped = (entries map ((a) -> {
	title: firstText(a, ["addOnName", "addonName", "title", "name", "addOnTitle"]),
	description: oneLine(firstText(a, ["shortDescription", "description", "addOnDescription"])),
	image_url: firstText(a, ["imageUrl", "image", "imagePath", "thumbnailImage", "thumbnail"]),
	price: do { var p = firstNum(a, ["preferredCurrencyPrice", "priceInPrefCurrency", "prefCurrPrice", "price", "amount", "unitPrice"]) --- if ((p != null) and (p >= 0)) round(p * 100) / 100 else null }
})) filter ($.title != null) distinctBy $.title
---
if (isEmpty(mapped)) null else mapped
