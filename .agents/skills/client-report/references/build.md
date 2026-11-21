# Build the report

## Order and content

The starter holds each section in this order. Delete a section that has nothing to say, except "Where it stands", "What is live", "How it was checked", "Not checked" and "Everything left".

1. Title and date. "Where it stands" and "What finishes it": one or two lines each.
2. Box "What is needed before each next stage": name each stage, then numbered items written in full, what does not block it, and its limits.
3. Correction box, only when an earlier report was wrong.
4. "What is live": area, status label, what a person can do and where. Status words are coloured labels: `chip live` (Live), `chip off` (Not built), `chip wait` (Waiting for an answer).
5. Before and after for each change: pictures side by side ([pictures](pictures.md)).
6. "How it was checked": one line for each check that ran. Then "Not checked". Never claim blanket coverage.
7. "Everything left", by who acts: our team; questions for each client person; things only the client can give; client staff. Each item names its stage in words. Each question has "Why we ask" and "Until you answer, we ...".
8. Small gaps, later work, "When it is done", how to undo a release.

Words: about 80% ASD-STE100, sentences of 20 words or fewer, one fact in each sentence.

## Make the file

- First pick the report's own folder `docs/client-report/<date>` (add `-2` for a second one the same day), and use it in every step below. Commit it only after the user approves it, so the last committed folder is the last approved one and the next report takes its "before" pictures from it. Before any commit, check who can read the repository: for a public repository or a wider audience than the client, keep the folder untracked and store it elsewhere.
- Copy `docs/client-report/template.html` to `docs/client-report/<date>/report.html`. Change text, rows and picture names only. Add no `style` attribute and no stylesheet link. A new look needs the user's approval and a new template commit.
- First report, no template yet: copy `assets/starter.html` to `docs/client-report/template.html` unchanged, and to the report path. Commit both only after the user approves the report and the audience check above allows it. The template keeps its placeholder text.
- Put the pictures next to `report.html`. Name each file as the report's `img src` says, and copy the saved picture to that name: `cp .hard-eng/browser/<name>-560.png docs/client-report/<date>/<img src name>`.
- Crop a picture: `uv run --no-project --with pillow python -I -c "import sys; from PIL import Image; Image.open(sys.argv[1]).crop(tuple(map(int, sys.argv[3:7]))).save(sys.argv[2])" in.png out.png left top right bottom`.
- Run the check always this way, so the Python version is the same everywhere: `uv run --no-project --python '>=3.12' python -I <skill>/scripts/check_report.py docs/client-report/<date>/report.html`. It finds the template from the git top level. It refuses CSS that differs from the template, codes such as A1, leftover `[...]` text, and a report without "How it was checked" and "Not checked". Fix the report, never the check.

## PDF and the page look

- Chrome prints the PDF. The path is for macOS; use the installed Chrome on another system:
  `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --no-pdf-header-footer --print-to-pdf=report.pdf "file://$PWD/report.html"`
- The template's print CSS uses block layout, `break-inside: avoid` on table cells, figures and boxes, and `@page` margins. Colour labels print because of `print-color-adjust: exact`.
- Render every page: `pdftoppm -r 90 -png report.pdf page` when it exists. Else `uv run --no-project --with pymupdf python -I -c "import sys,pymupdf; [p.get_pixmap(dpi=90).save(f'{sys.argv[2]}-{i+1}.png') for i,p in enumerate(pymupdf.open(sys.argv[1]))]" report.pdf page`.
- Open each page image. Look for blank gaps over a quarter of a page, cut-off pictures, text that cannot be read, and a heading alone at the foot of a page. Fix the report, print again, look again. Write down what you saw on each page.
