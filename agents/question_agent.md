# Question Agent

**Goal:** write **new, original** questions in CBSE Sample Question Paper style, with answers and a
step-wise marking scheme, and save them as **pending** for the teacher to review.

**Who runs it:** Claude Code, when the teacher says for example:
*"run agents/question_agent.md for Life Processes, 10 case-based, medium"*. No API key.

**Inputs** (ask the teacher if one is missing):
| Input | Values |
|---|---|
| chapter | Life Processes · Control and Coordination · How do Organisms Reproduce? · Heredity · Our Environment |
| type | mcq · assertion_reason · vsa (2 marks) · sa (3) · la (5) · case_based (4) – or "mixed" |
| count | how many (max 15 per run, so the teacher can review comfortably) |
| difficulty | easy · medium · hard · mixed (default medium) |

---

## Step 1 – Gather context
1. MCP `get_syllabus(chapter_id=...)` – write **only** within these topics; never use anything in
   `deleted_or_formative_only`.
2. MCP `search_questions(chapter=..., qtype=..., status="any", limit=100)` – see what already exists
   (approved, pending and rejected) so you **do not repeat** a topic + context that is already there.
   Rejected questions show what the teacher did not like.
3. If `pattern_report` exists (`scripts\agent_tools.py show-report pattern_report`), prefer its
   **most repeated topics** and follow the 2026-27 SQP style.

## Step 2 – Plan
Spread the questions over different topics of the chapter. Use a variety of CBSE competency formats:
- **case-based** – a short passage (60–150 words) about a real situation, then sub-parts
  (i), (ii), (iii) with marks in brackets that add up to 4 (e.g. 1 + 1 + 2);
- **experiment / activity** – what a student set up, observed, and why;
- **data / table / graph described in words** – read and interpret numbers;
- **assertion–reason**;
- **real-life application** – home, school, farm, hospital, everyday Indian contexts.

## Step 3 – Write each question
Rules:
- **Original.** Never copy a past-paper, SQP or textbook question word for word, and never just change
  a name or a number. New situation, new wording.
- NCERT-accurate science; Class 10 language; one clear correct answer.
- **mcq:** 4 options, exactly one correct, plausible distractors; `answer` = the correct option text
  (or its letter "a"–"d"); add `explanation`.
- **assertion_reason:** write `"question": "Assertion (A): ...\nReason (R): ..."`. Options are filled in
  automatically with the standard CBSE wording; give `answer` as the letter "a"–"d"; add `explanation`.
- **vsa / sa / la / case_based:** no options. Marks are fixed: vsa 2, sa 3, la 5, case_based 4.
  Show sub-part marks in brackets in the question.
- **marking_scheme:** a list of steps, each starting with the marks, e.g. `"1 mark: names the gland."`.
  The steps must add up to the question's marks.
- `competency_based`: true for case/data/experiment/application/assertion-reason, false for direct recall.

Question format (one JSON object per question):
```json
{
  "chapter_id": "life_processes",
  "topic": "Respiration: aerobic and anaerobic, human respiratory system",
  "qtype": "case_based",
  "difficulty": "medium",
  "competency_based": true,
  "question": "Read the passage and answer the questions.\n...\n(i) ... (1)\n(ii) ... (1)\n(iii) ... (2)",
  "answer": "(i) ...\n(ii) ...\n(iii) ...",
  "marking_scheme": ["1 mark: ...", "1 mark: ...", "2 marks: ..."]
}
```
Use a `topic` text taken from the syllabus topics list.

## Step 4 – Originality check
Save all the new questions as a JSON list in a scratch file and run:
```
.venv\Scripts\python.exe scripts\agent_tools.py check-original <scratch-file.json>
```
It compares them with the downloaded past papers (`data/sources/**/*.txt`) and with the bank.
Rewrite every question it flags, then run it again until it reports 0 problems.

## Step 5 – Save as pending
For each question call MCP **`add_question(question_json)`**. It is always saved with
`status: "pending"` and `source: "ai"` – never try to approve it yourself.
If the tool returns `ok: false`, read the `errors`, fix the question and call it again.

## Step 6 – Tell the teacher
Show a short table: id · type · difficulty · topic · first line of the question.
Then remind them: *"These are pending. Please review them in the app → Teacher Review
(or tell me 'approve LP-CB-003' / 'reject LP-CB-004')."*
Only call `update_question_status` when the teacher says so for that specific question.
