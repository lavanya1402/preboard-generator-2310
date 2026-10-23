# Preboard Generator – Architecture

AI does the repetitive work (reading the CBSE pattern, drafting questions, assembling papers).
The teacher approves every question before it can appear in a paper.

```mermaid
flowchart LR
    subgraph S[1 · Sources]
        S1[CBSE Sample Paper 2026-27<br/>+ Marking Scheme]
        S2[Past Board Papers]
        S3[CBSE Syllabus 2026-27<br/>+ NCERT Biology]
    end

    subgraph A[2 · Agents run by Claude Code]
        A1[Pattern Agent]
        A2[Syllabus Agent]
        A3[Blueprint Agent]
        A4[Question Agent]
    end

    subgraph M[3 · cbse-paper-mcp + Storage]
        M1[MCP tools<br/>search · add · status · generate · stats]
        M2[(storage.py<br/>JSON locally / Supabase on cloud)]
    end

    subgraph R[4 · Teacher Review]
        R1{Approve / Edit / Reject}
    end

    subgraph O[5 · Streamlit app + outputs]
        O1[Generate Paper]
        O2[Question Paper PDF]
        O3[Answer Key PDF]
        O4[Analysis charts]
    end

    S1 --> A1
    S2 --> A1
    S3 --> A2
    A1 --> A3
    A2 --> A3
    A3 -->|blueprint, after teacher OK| M1
    A4 -->|new questions = pending| M1
    M1 <--> M2
    M2 -->|pending questions| R1
    R1 -->|approved| M2
    M2 -->|approved only| O1
    O1 --> O2
    O1 --> O3
    O1 --> O4

    classDef review fill:#fbeceb,stroke:#c8372d,color:#1b2a4a
    classDef mcp fill:#e8eefc,stroke:#1f4fd1,color:#1b2a4a
    class R1 review
    class M1,M2 mcp
```

## Components

| Part | File | What it does |
|---|---|---|
| Data | `data/*.json` | Syllabus, paper blueprint, question bank, agent reports |
| Storage | `storage.py` | The only code that reads/writes data. `STORAGE=json` (local files) or `supabase` (cloud) |
| MCP server | `mcp_server/server.py` | Tools Claude Code uses: search, add (always pending), approve/reject, generate paper, stats |
| Agents | `agents/*.md` | Step-by-step instructions Claude Code follows. No API key needed |
| App | `app.py` | Streamlit: password, Generate Paper, Teacher Review, Question Bank, About |
| CLI | `generate_preboard.py` | Same paper engine from the command line |

## Deploy later

GitHub (code + animated diagram) → Streamlit Community Cloud (app) → Supabase (data that survives restarts).
