%dw 2.0
// Property details response -> the single property object, whatever envelope it arrives in.
output application/java
fun unwrap(b) = if (b is Array) (if (isEmpty(b)) null else unwrap(b[0]))
	else if ((b is Object) and (b.data != null)) unwrap(b.data)
	else if ((b is Object) and (b.propertyList is Array)) unwrap(b.propertyList)
	else if ((b is Object) and (b.properties is Array)) unwrap(b.properties)
	else if ((b is Object) and (b.property is Object)) unwrap(b.property)
	else b
---
unwrap(payload)
