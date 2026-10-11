# 🚀 CPT Email Agent

> AI-powered cold email tool for F-1 students targeting Summer 2027 CPT internships at top startups.

---

## What it does

1. **Sources** internship listings from Y Combinator Jobs, Hacker News "Who's Hiring", RemoteOK, and Wellfound
2. **Profiles** each company + role using Google Gemini AI
3. **Scores & ranks** by CPT response likelihood (tech match, F-1 friendliness, company stage, location)
4. **Generates** hyper-personalized cold emails per company + specific job role
5. **Sends** via Gmail — one email per company, 10/day max, resume attached
6. **Dashboard** — review, edit, approve, and track all emails before sending

---

## Setup

### Step 1: Python Environment

```bash
cd /Users/rushilreddy/Documents/cold-email-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Gmail API Setup (one-time, ~5 min)

> **You need to do this once to authorize Gmail sending.**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project: `cold-email-agent`
3. Go to **APIs & Services → Library** → search "Gmail API" → Enable
4. Go to **APIs & Services → OAuth consent screen**:
   - User type: External
   - App name: `CPT Email Agent`
   - Add your Gmail as a test user: `rushil.chirla@gmail.com`
5. Go to **APIs & Services → Credentials**:
   - Create Credentials → OAuth 2.0 Client ID
   - Application type: **Desktop app**
   - Download the JSON → save as `credentials.json` in the `backend/` folder
6. Run the auth flow:
   ```bash
   cd backend
   python -c "from agents.sender import GmailSender; GmailSender().authenticate()"
   ```
   A browser window opens → sign in with `rushil.chirla@gmail.com` → Allow
   This creates `token.json` — you won't need to do this again.

### Step 3: Start the Backend

```bash
cd /Users/rushilreddy/Documents/cold-email-agent
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

### Step 4: Start the Frontend

```bash
cd /Users/rushilreddy/Documents/cold-email-agent/frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Usage

### 1. Find Opportunities
Click **🔍 Scrape New Jobs** in the dashboard → pulls from HN Who's Hiring, RemoteOK, YC Jobs.

### 2. Score Them
Click **🤖 Score All** → Gemini analyzes each listing and assigns a 0–100 CPT likelihood score.

### 3. Review Emails
Go to **Companies** tab → filter by **Tier 1** → click **Preview Email** on each company.
Edit if needed → click **Approve ✓**.

### 4. Test Send
Click **🧪 Test Email** to send a test to yourself (`rushil.chirla@gmail.com`) first.

### 5. Go Live
Once you're happy, click **📨 Send Batch** → sends up to 10 approved emails for the day.

---

## DRY_RUN Mode

`.env` has `DRY_RUN=true` by default — emails are **previewed but NOT sent**.

To go live:
```bash
# Edit .env
DRY_RUN=false
```

---

## Scoring Rubric

| Signal | Weight | Your edge |
|---|---|---|
| Tech stack overlap | 25% | Python, Java, Spring Boot, AWS, Angular |
| Role matches SWE/ML/AI | 20% | Exact background |
| F-1/CPT friendly signals | 15% | Biggest filter |
| AI-first company | 15% | IIT Madras AI/ML cert + OpenAI experience |
| Startup stage (Seed–Series B) | 10% | Most flexible hiring |
| NYC/Remote accessible | 10% | Stony Brook → NYC |
| Recent funding | 5% | Active hiring budget |
| Founder is engineer | 5% | More likely to read cold emails |

**Tiers:**
- 🟢 Tier 1 (≥75): Send first
- 🟡 Tier 2 (50–74): Wave 2
- 🔴 Tier 3 (<50): Skip

---

## Email Strategy

Emails are generated per company + specific role by Gemini 1.5 Pro:
- Opens with a **specific fact** about the company (not generic praise)
- Connects **1-2 real achievements** to the role's exact needs
- Mentions Stony Brook naturally (CPT context without making it the focus)
- **150-200 words max**, direct and human
- Subject: role-specific, 6-10 words

---

## Project Structure

```
cold-email-agent/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings
│   ├── db.py                # SQLite + SQLAlchemy
│   ├── agents/
│   │   ├── sourcer.py       # Scrape startups
│   │   ├── researcher.py    # Gemini company profiler
│   │   ├── scorer.py        # CPT-aware scoring
│   │   ├── email_writer.py  # Gemini email generator
│   │   └── sender.py        # Gmail API sender
│   ├── models/models.py     # DB models
│   ├── routers/             # API routes
│   └── resume/resume.pdf    # Your resume
├── frontend/                # React + Vite + Tailwind
├── .env                     # API keys & config
├── requirements.txt
└── README.md
```

---

## Environment Variables

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | Your Google AI Studio key |
| `GMAIL_FROM` | `rushil.chirla@gmail.com` |
| `DAILY_SEND_LIMIT` | `10` (max emails/day) |
| `DRY_RUN` | `true` to preview, `false` to send |
| `RESUME_PATH` | Path to your resume PDF |

---

## Important Notes for CPT

- Most startups can support CPT — they provide an offer letter, Stony Brook approves it
- The emails mention "MS CS at Stony Brook" naturally — CPT comes up if they're interested
- Companies with `CPT OK` badges have explicitly mentioned F-1/OPT/CPT friendliness
- **Target Timeline**: Summer 2027 → start applying **Oct–Dec 2026** (3-6 months early is good)
- Stony Brook CPT requires the internship to be integral to your MS program
