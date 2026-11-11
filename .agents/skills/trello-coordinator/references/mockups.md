# Design and mockup posts

Load for every design brief and every mockup or design post to a card. [Design approval](run.md#design-approval) owns the approval steps. This file owns what a mockup shows and proves. Shared usability rules = [planning UX](../../he-plan/references/ux.md); where this file is stricter, it wins for card posts.

## Rules brief

Paste into every design brief. Give the job and these rules, never the layout (for example "each line has a note and two buttons"); the design decides what to cut. Check every mockup against each row; one fail → back to the worker, not to the card.

| Rule            | Check on each picture                                                                                                                                                              |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `idiotProof`    | Planning UX "Mistake-proof": the wrong action is impossible or obvious.                                                                                                            |
| `leastLoad`     | Planning UX "Least effort": the app does every step it can see or decide, and never asks staff to record what it already knows.                                                    |
| `leastClicks`   | Taps per job are counted; every step, sheet or confirm that is not essential is gone; Undo instead of "Are you sure?".                                                             |
| `visualFatigue` | Planning UX "Calm screens": few elements, few colours, short words, one focus per screen.                                                                                          |
| `hierarchy`     | The one thing to act on is the strongest element; everything else is quieter.                                                                                                      |
| `noClutter`     | Anything staff would not miss is gone: helper sentences, history notes, badges, repeated text buttons. Icons over text buttons; reasons of 3 words or fewer; details one tap away. |
| `coverage`      | Every row of the coverage table has a screen.                                                                                                                                      |
| `wholePage`     | Every touched page is checked top to bottom at 390 and 1280 px wide, not only the new parts. Old clutter on a touched page is in scope.                                            |
| `nothingLost`   | Every current action on a touched page has its new place, or a reason it goes.                                                                                                     |

Also: a destructive action asks more than once. A messaging-app link is an icon only, never a text label. Tap targets are at least 44 px.

## Worker output

1. Coverage table: each agreed item from the call, card or brief → the screen that shows it. A row with no screen fails.
2. Nothing-lost list: each current action on the touched pages → its new place, or why it goes.
3. Taps table: taps per job, before and after, counted by clicking the real app. It goes in the worker's report and the card's plan, never in the staff image.
4. Screens: the real app with fake data, as a local patch only. No live writes.
5. Staff image: one combined image of the After screens only, a plain caption under each and red boxes around what is new. No Before screens and no taps table. The plan and the pull request still keep the real Before per planning UX.

## Proof file

Open each picture, then write `<picture>.json` beside it (`home.png` → `home.png.json`). `comment`, `move` and `upload` refuse a `.png`, `.jpg`, `.jpeg`, `.gif` or `.webp` whose proof file is missing, older than the picture or incomplete; they upload nothing.

```json
{
  "change": "What changed",
  "shows": "What the picture shows, written after opening it",
  "showsChange": true,
  "uiRules": { "idiotProof": "What I checked on this picture for this rule" }
}
```

`uiRules` holds one line of at least 20 characters for each rule in the rules brief. A picture that shows no new screen, such as a live result or an error, has `"notNewUi": "<reason>"` instead of `uiRules`.

## Post

`comment <card> <text-file> --image <staff image>` with one tagged question, recommendation first. When a picture's proof has `uiRules`, `comment` ends the post with this line; do not write it yourself:

**IF YOU NEED ANY CHANGES, PLEASE SEND SCREENSHOTS AND PUT ALL OF YOUR ISSUES IN ONE COMMENT.**
