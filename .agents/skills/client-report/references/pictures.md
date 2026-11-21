# Pictures

Pictures use the [browser command](../../e2e/references/browser.md). Install or run no other browser tool.

- Sign in once for each role: `python3 .hooks/hard-eng.py browser signin <role> --session NAME`. Never open, print or copy the sign-in values.
- Per picture, with one `--session` name and the role's `--state` on the first step: `set viewport 560 520`, `open <live url>`, `wait --load networkidle`. Press only tabs and rows. Never save, send, delete or submit.
- Mark each part the text names. Run one `eval` that adds a style to the page, then `wait 600`:
  `#part { outline: 4px solid #e00000 !important; outline-offset: 4px !important; transition: none !important }`
  Do not use `--ring`: it draws a 3 px box.
- Then `browser measure --session NAME --name <name>`. It hides emails and phone numbers and saves `.hard-eng/browser/<name>-<width>.png`. Look at each image: the command misses names and other personal data. Crop or leave out a picture that shows one.
- Width 560 and height about 520 keep the text readable at half page width. A tall window leaves empty space under the page.
- Caption each picture with what the red line marks. Under "Pictures with no live copy", list each state with no live picture, with the reason.
