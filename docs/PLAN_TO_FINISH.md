# Plan to finish (as of 2026-11-20)

## Deadlines
| Date | What | Required? |
|---|---|---|
| **Nov 23, EOD** | Project video: 15–17 min, slides with narration. Same content as Nov 16, plus an ethics slide. Send the technical appendix with it. | Yes |
| Nov 23, class | Emergency class. Optional if the video is already submitted. | No |
| **Nov 30** | Poster session; three judges, prizes possible. | Yes, attendance required |
| Dec 1 | Both main-study label sheets done (owner decision D5) | Blocks final results |
| Dec 2–3 | Joint adjudication (A + B) | Blocks final results |
| Dec 3–4 | Rerun every method on the human labels, then the final report | After adjudication |

## Video (Nov 21–23)
- **Content:** `docs/video/VIDEO_DECK_nov23.md` has 15 slides with full narration, about 2,200 words (about 15–16 min).
- **Slides:** `SafeAdapt-Math_video_nov23.pptx` has the same 15 slides with the narration in the speaker notes. It uses two charts, `docs/video/fig_prompt.png` and `fig_judges.png`.
- **Appendix:** `docs/video/TECHNICAL_APPENDIX.md`; export it to PDF and send it with the video.
- **Steps:**
  1. Nov 21: decide who narrates which slides (suggested: Cathy slides 1–5, Harshit 6–15).
  2. Nov 21: rehearse once with a timer. Cut narration on slides 12–13 if over 17:00; expand slide 9 if under 15:00.
  3. Nov 22: record with Zoom or PowerPoint "Record slide show" at 1080p, then check the audio.
  4. Nov 23: submit the video and the appendix PDF.

## Poster (Nov 24–30)
- **Layout:** problem statement and main finding (top band); the two charts; checker diagram; calibration finding; ethics box; QR code to the repo and appendix.
- **Possible update:** if labelling is far enough along by Nov 28, add a "preliminary main-study human labels" panel, clearly marked partial. Otherwise use the video content.
- **Print:** check the size and the print deadline with the course staff.

## Labelling (now → Dec 1): the critical path
- **Sheets:**
  - A: `data/annotations/ollama-v1/sheet_A.xlsx`, 693 items;
  - B: `sheet_B.xlsx`, 692 items.
  - Both were re-exported with the rubric v1.2 instructions. They stay local because of blinding and the GSM1K licence.
- **Pace:** about 17.3 h each is about 2.5 h a day for 7 days. Start by Nov 24 at the latest.
- **Rules:** independent labelling; never open the KEY; Cathy doesn't see the calibration overrides first.

## After labels (Dec 2–4; Claude runs it, the owner reviews)
1. Run `python src/adjudicate.py --ann data/annotations/ollama-v1`. Joint adjudication of TO_ADJUDICATE.csv, then rerun with `--resolved`.
2. Rerun every method on the human labels, with `sbatch scripts/human_methods.sbatch` (refuses to run on stand-in labels).py`. That's one CPU job, about 1 h.
3. Final report: replace Part 3 of the status report, and check the careful-prompt rate against the five calibration overrides.
4. Owner only: rotate the OpenRouter key.

## Pending, by owner
| Item | Who |
|---|---|
| Video narration and recording | Harshit + Cathy |
| Main labelling A / B | Harshit / Cathy |
| Joint adjudication | both |
| Rotate the OpenRouter key | Harshit |
| Poster printing | Harshit + Cathy |
| Reruns, final report draft, poster draft | Claude, on request |
