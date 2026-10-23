# Preboard Generator

AI does the repetitive work of reading the CBSE pattern, writing questions and assembling
Class 10 Science (Biology) preboard papers. The teacher approves every question.

Full README comes in Phase 6. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Quick test (command line)

```
.venv\Scripts\python.exe generate_preboard.py --seed 1
```

## Running the agents (no API key)

The agents are instruction files in `agents/`. Open Claude Code in this folder and type one of these:

| You type | What happens |
|---|---|
| `run agents/pattern_agent.md` | Downloads the 2026-27 SQP, marking scheme and past board papers from official CBSE sites, analyses Biology questions, saves `data/reports/pattern_report.json` |
| `run agents/syllabus_agent.md` | Checks `data/syllabus.json` against the CBSE 2026-27 curriculum and NCERT, shows differences, updates only after you say yes |
| `run agents/blueprint_agent.md` | Proposes a new blueprint from both reports (~50% competency-based), shows the difference, updates only after you say yes |
| `run agents/question_agent.md for Life Processes, 10 case-based, medium` | Writes 10 new original questions with answers and marking schemes, saved as **pending** |

Recommended order the first time: pattern → syllabus → blueprint → question.

If a PDF cannot be downloaded, the agent lists it with the official page and the folder
(`data/sources/...`) to save it in. Download it yourself, then say "continue".

New questions are never used in a paper until you approve them (app → Teacher Review, or tell Claude
"approve LP-CB-003").
