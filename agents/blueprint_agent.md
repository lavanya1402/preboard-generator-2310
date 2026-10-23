# Blueprint Agent

**Goal:** combine `pattern_report` and `syllabus_report` into a **proposed paper blueprint**
(about **50% competency-based**), show the teacher the difference from the current blueprint,
and update it **only after the teacher approves**.

**Who runs it:** Claude Code, when the teacher says *"run agents/blueprint_agent.md"*. No API key.

---

## Step 1 – Read the inputs
```
.venv\Scripts\python.exe scripts\agent_tools.py show-report pattern_report
.venv\Scripts\python.exe scripts\agent_tools.py show-report syllabus_report
```
and MCP `get_blueprint()`, `get_stats()`.
If a report is missing, tell the teacher which agent to run first and stop.

## Step 2 – Decide the paper size
Keep the current size (**30 marks, 16 questions**) unless the teacher asks for something else
(e.g. a full 80-mark Science paper is not this project – it is Biology only).

## Step 3 – Sections (format)
Mirror the **2026-27 SQP** (`pattern_report.format_2026_27`): the same kinds of sections and question
types (MCQ, assertion-reason, 2/3/5-mark, 4-mark case-based), in the same order, scaled down to the
paper size. Marks per type are fixed: mcq 1, assertion_reason 1, vsa 2, sa 3, la 5, case_based 4.

## Step 4 – Marks per chapter
1. Start from the **2026-27 SQP Biology marks per chapter** (share of each chapter).
2. Adjust gently using the **average of recent years (2023-24 onwards)** from `biology_marks_by_chapter_by_year`.
3. Remove anything the syllabus report marks as deleted / formative-only.
4. Scale to the paper's total and round to whole marks. The chapter marks must add up to the total, and
   each chapter's marks must be reachable with the question types in the paper (e.g. 3 marks = 1 SA,
   or 1 MCQ + 1 VSA).

## Step 5 – Difficulty and competency
- `difficulty_mix` e.g. `{"easy": 0.3, "medium": 0.5, "hard": 0.2}` (shares add to 1.0).
- `competency_based_target`: **0.5** (about half the marks from case-based, data, experiment,
  assertion-reason and real-life questions), unless the SQP clearly shows a different share.

## Step 6 – Save the proposal
Build `proposed_blueprint` in **exactly the same format** as the current blueprint (`title, session,
total_marks, total_questions, duration, note, sections[], chapter_marks{}, difficulty_mix{},
competency_based_target, general_instructions[]`). Rewrite `general_instructions` to match the sections.

```json
{
  "agent": "blueprint_agent",
  "based_on": ["pattern_report", "syllabus_report"],
  "reasoning": ["Life Processes gets 10 marks because ...", "..."],
  "proposed_blueprint": { "...": "same format as data/paper_blueprint.json" }
}
```
```
.venv\Scripts\python.exe scripts\agent_tools.py save-report blueprint_report <scratch-file.json>
```

## Step 7 – Show the difference and ASK
```
.venv\Scripts\python.exe scripts\agent_tools.py diff-blueprint
```
- If it prints **Problems**, fix the proposal and save again (marks must add up).
- If it prints a **Warning** (not enough approved questions for some chapter/type), tell the teacher which
  questions are needed and suggest a Question Agent run, e.g.
  *"run agents/question_agent.md for Heredity, 3 case-based, medium"*.

Explain each change in simple words with the reason, then ask:
**"Shall I update the paper blueprint with these changes?"**

## Step 8 – Update only after a clear "yes"
```
.venv\Scripts\python.exe scripts\agent_tools.py apply-blueprint --approved
```
Then make a test paper with MCP `generate_paper(seed=1)` and show its chapter marks vs target.
