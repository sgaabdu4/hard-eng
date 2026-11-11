# Design and mockup posts

Load for every design brief and every mockup or design post to a card. [Design approval](run.md#design-approval) owns the approval steps. [Planning UX](../../he-plan/references/ux.md) owns the usability rules and the brief. This file adds what a card post needs.

## Design brief

Write it per planning UX "Brief": link it, include its full Usability list, and state the job, the users and the constraints, never the layout. Add the agreed items from the call, card or brief, and the [proof rules](#proof-rules).

## Worker output

1. Coverage table: each agreed item → the screen that shows it. An agreed item with no row, or a row with no screen, fails.
2. Nothing-lost list: each current action on the touched pages → its new place, or why it goes.
3. Whole-page captures: each touched page, top to bottom, at 390 and 1280 px wide and at each other width the app supports. They are for your check, not for staff.
4. Taps table: taps per job, before and after, counted by clicking the real app. It goes in the worker's report and the card's plan, never in the staff image.
5. Screens: the real app with fake data, as a local patch only. No live writes.
6. Staff image: one combined image of the After screens only, a plain caption under each and red boxes around what is new. No Before screens and no taps table. The plan and the pull request still keep the real Before per planning UX.
7. The plan's UX Rules block judges every Usability rule.

Check the output and each picture against the proof rules; one fail → back to the worker, not to the card.

## Proof rules

| Key             | Check                                                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `idiotProof`    | Planning UX "Mistake-proof".                                                                                             |
| `leastLoad`     | Planning UX "Least effort" and "Observe".                                                                                |
| `leastClicks`   | Planning UX "Least effort" click count and "Undo"; a destructive action asks more than once.                             |
| `visualFatigue` | Planning UX "Hierarchy" and "No clutter": one focus, few elements and colours, short labels.                             |
| `hierarchy`     | Planning UX "Hierarchy": the one action that matters is the strongest element.                                           |
| `noClutter`     | Planning UX "No clutter"; a messaging-app link is an icon with a screen-reader label, never a text label.                |
| `coverage`      | Each coverage table row this picture shows has its screen; the rows on other pictures are named.                         |
| `wholePage`     | Each touched page in this picture was checked top to bottom in the whole-page captures; old clutter on it is in scope.   |
| `nothingLost`   | Each current action on the pages in this picture has its new place, or a reason it goes.                                 |

## Proof file

Open each picture, then write `<picture>.json` beside it (`home.png` → `home.png.json`). `comment`, `move` and `upload` refuse a `.png`, `.jpg`, `.jpeg`, `.gif` or `.webp` whose proof file is missing, older than the picture or incomplete. Then nothing is uploaded, posted or moved.

```json
{
  "change": "What changed",
  "shows": "What the picture shows, written after opening it",
  "showsChange": true,
  "uiRules": { "idiotProof": "What I checked on this picture for this rule" }
}
```

`uiRules` holds one line of at least 20 characters for each key in the proof rules: what you checked on this picture. A picture that shows no new screen, such as a live result or an error, has `"notNewUi": "<reason>"` instead of `uiRules`. Every picture must show the change, so a testing picture holds before and after side by side.

## Post

`comment <card> <text-file> --image <staff image>` with one tagged question, recommendation first. When a picture's proof has `uiRules`, `comment` ends the post with this line; do not write it yourself:

**IF YOU NEED ANY CHANGES, PLEASE SEND SCREENSHOTS AND PUT ALL OF YOUR ISSUES IN ONE COMMENT.**
