%dw 2.0
// propertyName -> {propertyCode, message}. The v3 booking search needs property codes, so a request by name
// is looked up in property-codes.json ([{"propertyCode": "50926", "propertyName": "..."}]).
// Match: exact name first, then a single entry containing the name. Case, spacing and punctuation are ignored.
output application/java

fun norm(s) = trim((lower(s default "") replace /[^a-z0-9]+/ with " "))

var name = vars.request.propertyName
var wanted = norm(name)
var catalogue = (readUrl("classpath://property-codes.json", "application/json") default []) filter ($ is Object)
var exact = catalogue filter (norm($.propertyName) == wanted)
var partial = catalogue filter (norm($.propertyName) contains wanted)
var hits = if (!isEmpty(exact)) exact else partial
---
if (sizeOf(hits) == 1) {propertyCode: hits[0].propertyCode as String, message: null}
else if (isEmpty(hits)) {propertyCode: null, message: "No property named '$(name)' was found. Send propertyCode instead."}
else {propertyCode: null, message: "More than one property matches '$(name)': " ++ ((hits map $.propertyName) joinBy ", ") ++ ". Send propertyCode instead."}
