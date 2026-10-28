# T-06 DataWeave in the DataWeave Playground

Playground-ready copies of the two T-06 scripts. They are the deployed files plus a short shim:
`vars.*` becomes `ctx.*`, read from the input payload, and `p('key')` reads a fixed map of the
`compare-properties.yaml` / `uat-missing-keys.yaml` values. Regenerate them after changing the real files.

1. Open https://dataweave.mulesoft.com/learn/playground.
2. Paste `compare-properties-response.playground.dwl` into the script pane.
3. Paste `compare-properties-response.playground-input.json` as the `payload` input (application/json).
   It holds `compareRequest` and `lookups` built from the 8790 and 8791 samples, plus one not-found code.
4. The output should match `../../examples/compare-properties-response.sample.json` for 8790 and 8791,
   with 99999 listed in `missing_properties`.

For `compare-validate-request.playground.dwl` the input is a T-06 request body
(`compare-validate-request.playground-input.json`: duplicates, a 5th code, lower-case currency).
The result depends on today's date only through the defaults; the sample sets both dates.

## T-07 compare_rooms_rates

- `compare-rooms-validate-request.playground.dwl` + `-input.json`: the owner's body with a duplicate in another case.
  Expect `roomCodes` `["1brmt", "0BRCT", "1DLXT"]` (as written, duplicates removed ignoring case), no errors.
- `compare-rooms-response.playground.dwl` + `-input.json`: the 51052 T-04 sample with codes `1BRMT`, `0brct`, `XXXX`.
  Expect `rooms` 1BRMT then 0BRCT, `meta.total_results` 2, and `excluded` `[{room_code: "XXXX", reason: "not_available"}]`.
  Schema: T07 0.4.0.

## T-08 create_booking

- `create-booking-validate-request.playground.dwl` + `-input.json`: the selected one-room example (0BRCT + ZZFLEX,
  2 adults, 1 child aged 6). Expect no errors and one apartmentList entry. Defaults depend on today's date.
- `create-booking-response.playground.dwl` + `-input.json`: the 51052 T-04 answer for that request. Expect `problems: []`
  and `response.rooms[0]` = 0BRCT with rate ZZFLEX, `meta.resolution` "selected".
- `create-booking-add-ons.playground.dwl` + `-input.json`: a GUESSED addonlist response (no real sample yet). Expect two add-ons.

## T-02 get_property_details request (input schema 0.2.0)

- `validate-request.playground.dwl` + `-input.json`: 2 adults, 1 child aged 6, 12-10 to 12-13, USD. Expect `errors: []`,
  `request.childAges` `[6]`, `nights` 3. Remove `childAges` to see "childAges is required when noOfchildren is above 0".
