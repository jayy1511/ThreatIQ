# ThreatIQ – Phishing Awareness Chatbot

## About
**ThreatIQ** is a phishing awareness chatbot that helps users detect suspicious emails or messages.  
It combines heuristic analysis, free threat intelligence sources (VirusTotal, Whois), and generative AI reasoning to:
- Flag phishing indicators (e.g., suspicious links, urgency, poor grammar).
- Explain risks in simple terms.
- Provide safe browsing and handling tips.  
All with a strong focus on **privacy** and **security**.

---

## Project Goal
The goal of ThreatIQ is to support users in recognizing and understanding phishing attempts.  

**Example Workflow:**
1. User pastes a suspicious email or message.
2. Bot analyzes using heuristics + VirusTotal + Whois.
3. Generative AI explains why it might be phishing.
4. User receives safety tips (e.g., don’t click, report, delete).

---

## Tech Stack
- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Python)  
- **Frontend:** [ReactJS](https://react.dev/)  
- **Database:** SQLite / PostgreSQL (user accounts, logs, stats)  
- **AI Model:** [GPT4All](https://github.com/nomic-ai/gpt4all) via llama.cpp (local, free)  

---

## Core Features
- Chat interface for phishing analysis  
- Heuristic checks (keywords, suspicious URLs, spoofed senders)  
- VirusTotal + Whois lookups  
- Generative AI reasoning (explanations + safe handling tips)  
- User authentication (JWT-based) and role management (user/admin)  
- Admin dashboard for usage statistics  

---

## Privacy & Security
- No storage of raw messages (only anonymized statistics).  
- GDPR compliance (account deletion, data removal).  
- Secure authentication with JWT + bcrypt.  
- Countermeasures against prompt injection, SQL injection, and abuse (rate limiting).  

---

## Setup & Run (Prototype)
1. **Clone the repo**
   ```bash
   git clone https://github.com/your-username/ThreatIQ.git
   cd ThreatIQ
