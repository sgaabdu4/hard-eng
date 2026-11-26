# Fix the invoice total

Status: Complete

## Outcome + scope

The invoice total includes the *late fee* and __never__ rounds twice; non-goals: the `tax_table` module, the old `legacy_total` helper and every report.

## Acceptance + steps

* [x] A late invoice adds the fee once → `tests/test_total.py::test_fee_once`
* [x] A paid invoice adds no fee → `tests/test_total.py::test_paid_no_fee`
+ [ ] A refund keeps the fee → N/A — the refund flow is not part of this change
1) First step: write the red test for the late fee.
2) Second step: fix the total at its owner, `billing/total.py`.

| Case        | Result |
|-------------|:-------|
| late        | fee    |
| paid        | no fee |

## Risks + recovery

*Recovery:* revert the commit. The names `test_fee_once` and `test_paid_no_fee` stay as written, and snake_case words are text.

***

Not checked: other currencies; a very long line that a formatter may wrap because it holds more than eighty characters of plain words in one row.
