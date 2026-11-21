# Fixtures for the layout checks

- `govuk-home.html`: the GOV.UK home page, cut down to its HTML and CSS (no scripts, images or fonts). Source: https://www.gov.uk/, published under the Open Government Licence v3.0 (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
- `govuk-buttons.html`: the GOV.UK Design System button page, cut down the same way. Source: https://design-system.service.gov.uk/components/button/, MIT licence (https://github.com/alphagov/govuk-design-system/blob/main/LICENCE.txt).
- `pushed-right.html`: written for this repository. Text with its controls pushed right on the next line at 390 and 768 px.

## Known difference

`govuk-home.html`: its search field has no icon inside it, and one submit button sits beside it. The search row of the standard patterns is the user's decision ("shouldn't eye icon be within the text field??? ... why is search bar looking like this"), and a public page that does it another way does not move the check to judgement. The check keeps its finding on this element. The misfire test leaves out that one element by its selector, `input[name="keywords"]`, and no other.
