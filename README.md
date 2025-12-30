# LIFE OS // HOLD THE LINE

v0.1 Legacy. The Steel Thread MVP.

> *"The database rejects the lie."*

**Life OS** is a ruthless, high-integrity operating system for personal performance. It is not a to-do list. It is a feedback loop that forces you to confront reality.

Built on the philosophy of the **Steel Thread**, this system prioritizes **data integrity over user convenience**. It uses strict database constraints, immutable logs, and rigorous session tracking to prevent you from lying to yourself about how you spend your time.

![Status: Operational](https://img.shields.io/badge/Status-Operational-success)
![Stack: Python](https://img.shields.io/badge/Stack-Python_|_SQLite_|_Streamlit-blue)

## 💀 The Philosophy

Most productivity apps fail because they are "soft." You can delete a missed task, edit a session duration, or backdate a habit to keep a streak alive.

**Life OS is "hard."**
1.  **Immutability:** Once an evening log is submitted, it is locked forever.
2.  **Close-Once Sessions:** You cannot edit a deep work session after it closes. If you worked 10 minutes, the DB records 10 minutes.
3.  **The Judge:** The system calculates a daily **NPS (Net Personal Score)** based on your plan execution, sleep, and spending. You do not grade yourself; the algorithm does.

## ⚡ Features

* **🛡️ The HUD:** A "shadcn-styled" reactive dashboard built in Streamlit.
* **🎯 Focus Engine:** A strict deep-work timer that locks the database session.
* **🗺️ Tactical Planning:** Commit to tasks (Engine, Vessel, Resources, System).
* **⚖️ The Scoring Engine:** Automated daily scoring (WIN / HOLD / FAIL) based on `system_config` rules.
* **🔒 SQLite Hardening:** Triggers prevent tampering, concurrent sessions, or history rewriting.

## 🛠️ Tech Stack

* **Backend:** Python 3.12+
* **Database:** SQLite (WAL Mode, Strict Foreign Keys, JSON Support)
* **Frontend:** Streamlit (Custom CSS injected for React/Tailwind aesthetic)
* **Architecture:** Service-Layer Pattern (`services/`) separating logic from UI.

## 🚀 Quick Start

### 1. Clone & Environment
```bash
git clone https://github.com/yourusername/hold-the-line.git
cd hold-the-line

# Create Virtual Environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install streamlit pandas
```

### 3. Initialize the Vault (Database)
This script builds the schema, applies the "paranoid" triggers, and enables WAL mode.

```bash
python init_db.py
```

### 4. Boot the System (Genesis)
This script injects the initial configuration rules (Scoring weights, Veto thresholds).

```bash
python config_boot.py
```

### 5. Run the OS
```bash
streamlit run app.py
```

## 📖 The Protocol

This system is designed around a daily ritual.

### 🌅 Morning (Planning)
- **Check Status:** Review yesterday's Score (WIN/FAIL).
- **Commit:** Enter the Planning tab. Add 1-3 "Engine" tasks (Deep Work).
- **Keystone:** Mark one task as critical.
- **Rule:** Do not over-plan. 50% completion is a FAIL.

### ⚔️ Day (Execution)
- **Initiate:** Select a task from the dropdown. Click GO.
- **Execute:** The timer runs. The session is open in the DB.
- **Terminate:** Click TERMINATE. The session closes. The duration is written to stone.

### 🌙 Evening (Judgment)
- **Log:** Enter the Evening Log tab.
- **Input:** Enter raw metrics (Sleep Score, Spend, Alcohol Units).
- **Lock:** Click LOCK & SCORE.
- **Verdict:** The system computes your NPS. The day is closed.

## 📂 Project Structure

```
.
├── app.py                  # The Frontend (Streamlit)
├── init_db.py              # Schema & Triggers (The Law)
├── config_boot.py          # Initial Ruleset
├── services/               # The Logic Layer
│   ├── db.py               # Connection Manager (WAL/Foreign Keys)
│   ├── day_service.py      # Day Initialization & Config Inheritance
│   ├── plan_service.py     # Task Inventory & Commitments
│   ├── session_service.py  # Timer Logic & Integrity Checks
│   ├── log_service.py      # Immutable Logging
│   └── scoring_service.py  # The Judge (NPS Calculation)
└── README.md
```

## ⚠️ Integrity Constraints

The `init_db.py` script applies SQLite Triggers that will crash your program if you try to:

- Start a second deep work session while one is active.
- Edit a session's start time after creation.
- Update an immutable log.
- Insert a task with a shipping type outside the 'ENGINE' domain.

**This feature is a bug.**

**Hold The Line.**
