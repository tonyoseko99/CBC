# ClassMark — offline class teacher assessment system

Single file: `dist/ClassMark.exe`. Copy it anywhere (e.g. a folder on the Desktop or a flash disk) and double-click. No internet or installation needed.
Data is saved in `ClassMark Data\classmark.db` next to the exe. Generated reports go to `ClassMark Data\Reports`.

## Sign-in and users
- **First launch:** register (full name, username, 4–6 digit PIN). You're then shown a **recovery code**. Write it down; it's the only way to reset a forgotten PIN.
- **Every launch:** choose your name and enter your PIN.
- At most **2 users**. The second user can only be added from **Settings → Users** by the signed-in user, after confirming their own PIN, so nobody can register themselves from the sign-in screen.
- 5 wrong PINs lock that account for 1 minute, then 2, 4… minutes. **Forgot PIN?** on the sign-in screen uses the recovery code and issues a new one.
- **Lock** (top right) hides everything until a PIN is entered. The app also locks itself after 15 minutes without use.
- **Each user sees only their own classes** (with their learners, marks and reports). A new class is owned by whoever creates it, and the class teacher name defaults to that user. If a user is removed, their classes move to the remaining user. School details and learning areas in Settings are shared.

## First use
1. **+ New class**: enter the class (e.g. GRADE 7B), year and class teacher's name. The name prints on every Individual Assessment Report.
2. **+ New assessment**: e.g. "End Term Assessment", term, year, marks out of (e.g. 50). Papers that differ (e.g. Insha /45) can be set per paper.
3. **Learners**: add them one by one, or click **Download template**, fill it in Excel, and **Upload template**. The template already lists existing learners, so you can correct names there too.
4. **Marks entry**: type into the grid (Enter moves down). For mass entry, click **Download template**. It is the school's usual mark sheet layout: row 1 OUT OF, row 2 PUPIL'S NAME, MATH, ENG P1, ENG P2, TOTAL, KISW P1, KISW P2, JUMLA … G. TOTAL. Learners are listed alphabetically, with TOTAL and MEAN rows at the bottom. Type marks in the white cells; the % columns, G. TOTAL, TOTAL and MEAN calculate themselves. Then click **Upload template** and check the preview (problems show in red) before importing. An emptied cell removes that mark.
   - A sheet the school already has in this same layout (e.g. `7BB.xlsx`) can be uploaded directly. Learners are matched by name, and the file's OUT OF row updates the assessment's out-of values.
   - Anything else is rejected: other layouts, templates for another class, or changed headings. In the downloaded template, Excel itself blocks marks outside 0 to the out-of value.
5. **Reports**:
   - **Individual Assessment Reports (PDF)…**: tick which learners to print. Use All, None, With marks, Invert, Only EE/ME/AE/BE, or search. Each learning area shows its **POINTS** (EE1 = 8, EE2 = 7, ME1 = 6, ME2 = 5, AE1 = 4, AE2 = 3, BE1 = 2, BE2 = 1) and **LEVEL**, with total points and overall level in the TOTAL row.
     - Pick up to 3 exams (e.g. Opener, Mid Term, End Term) above the buttons. The POINTS column is then split into one column per exam plus AVG, and level and remarks come from the average. Pick one exam for a single-exam report.
     - **Show marks** (in this window or in Settings) adds a MARKS column and the TOTAL MARKS / OUT OF line. With it off, the report shows points and levels only.
   - **Class mark sheet (Excel / PDF)…**: choose learners (same quick picks), learning areas, and what to show for each (marks, %, points, level). Also choose the totals (total marks, out of, G. Total, average %, total points, overall level), the summary rows (level counts, EE/ME/AE/BE totals, number sat, TOTAL, MEAN SCORE), order (Adm No or name), the subject analysis page, and paper size (A4/A3).
     - Presets: Full mark sheet, Points only, Levels only, Points & levels, Marks & % only. Your last choices are remembered.
     - Summary rows are worked out from the ticked learners only. The sheet title says e.g. "(10 OF 57 LEARNERS)".
   - **Remarks** are written automatically. To edit, double-click a learner (or **Edit remarks…**). You can change the class teacher's and head teacher's remarks, discipline and class attention, with **Use automatic** to restore the suggestion and Previous/Next to go through the class. Edits save when you move to another learner or click Save & close.
6. **Dashboard** (for the class and assessment in the top bar). Nothing on it ranks learners.
   - **Cards:** learners, assessed, class mean, mean level, average points, % of marks entered.
   - **Ready to print?** Missing marks, closing/opening dates, class teacher and head teacher names, discipline/attention filled in, and how many remarks were personalised.
   - **Marks entry progress:** entered / total for each paper, and which learners are missing which papers.
   - **Learners needing support:** in alphabetical order, everyone whose overall level is AE or BE or who dropped a level since the previous assessment, with their two weakest learning areas.
   - **Level distribution** (whole class and each learning area) and **points summary** (average total points and how many learners are in each points range).
   - **Change since the previous assessment:** class mean per learning area with ▲/▼, and how many learners moved up, stayed or dropped a level.
   - **Strongest & weakest learning areas**, **girls & boys** (uses the gender field), a **trend chart** of the class mean across assessments (optionally with one learning area), and the **learning area analysis** table.
7. **Settings**: school name, logo, head teacher, learning areas/papers, and **Back up now**. To rename a paper (e.g. Insha → Kiswahili PP2), select it and click **Edit**. Its existing marks are kept. A paper's **code** is its column heading in the marks template. **Order shown** switches between the report's row order and the mark sheet's column order (P.TECH before AGRIC); ▲ ▼ change whichever is shown.

## Grading (CBC 8-level key)
EE1 90–100 (8) · EE2 75–89 (7) · ME1 58–74 (6) · ME2 41–57 (5) · AE1 31–40 (4) · AE2 21–30 (3) · BE1 11–20 (2) · BE2 0–10 (1).
Percentages are rounded to whole numbers before grading. Once a learner has any mark in an assessment, blank papers count as 0 (like the Excel mark sheet); learners with no marks at all are treated as not assessed and get no Individual Assessment Report. Overall level = average % across all learning areas. No ranking or positions are produced.
Remarks are generated automatically from the levels and can be edited per learner on the Reports page.

## Rebuilding the exe (developer)
Run `build.bat` (creates `.venv` on first run), output: `dist\ClassMark.exe`.
