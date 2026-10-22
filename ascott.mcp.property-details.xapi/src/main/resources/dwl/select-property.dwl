%dw 2.0
// Booking search response {messageId, propertyList: [...]} -> the entry for the requested code, or null.
output application/java
var code = vars.request.propertyCode
var list = if ((payload is Object) and (payload.propertyList is Array)) (payload.propertyList filter ($ is Object)) else []
var hit = list filter ((($.propertyCode default "") as String) == code)
---
// Only one code is sent, so a single entry with another code format (e.g. a number) is still this property.
if (!isEmpty(hit)) hit[0] else if (sizeOf(list) == 1) list[0] else null
