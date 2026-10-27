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

- `compare-rooms-validate-request.playground.dwl` + `-input.json`: the owner's body with duplicates, lower case and a
  5th code. Expect `roomCodes` `["1BRMT", "0BRCT", "1DLXT", "1BRT"]`, `droppedRoomCodes` `["ZZZ"]`, no errors.
- `compare-rooms-response.playground.dwl` + `-input.json`: the 51052 T-04 sample filtered to `1BRMT`, `0BRCT`, `XXXX`.
  Expect `1BRMT` then `0BRCT` in `requested_rooms[0].rooms`, and `excluded` `[{room_code: "XXXX", reason: "not_found"}]`.
