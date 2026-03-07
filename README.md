<<<<<<< HEAD
# NarrativeIQ — Episodic Intelligence Engine

AI-powered story analysis for series creators.

```
narrativeiq/
├── backend/    ← Python FastAPI + SQLite + Auth
└── frontend/   ← React + Vite + Tailwind
```

---

## Quick Start

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Add your OpenAI key to .env
# (open .env and set OPENAI_API_KEY=sk-...)

# Start the server
uvicorn api.module2_api:app --reload --port 8000
```

Server runs at: http://localhost:8000  
API docs at: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs at: http://localhost:5173

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /health | No | Server status |
| POST | /api/auth/register | No | Create account |
| POST | /api/auth/login | No | Login → get JWT |
| GET | /api/auth/me | Yes | Current user |
| POST | /api/analyse | No | Run pipeline (anonymous) |
| GET | /api/jobs/:id | No | Poll job status |
| GET | /api/jobs/:id/result | No | Get result |
| POST | /api/story/analyse | Yes | Run + save to DB |
| GET | /api/story/history | Yes | Past stories |
| GET | /api/story/:id/result | Yes | Saved result |
| DELETE | /api/story/:id | Yes | Delete story |

---

## Environment Variables

**backend/.env**
```
OPENAI_API_KEY=sk-...
JWT_SECRET_KEY=change-this-to-random-string
DATABASE_URL=sqlite:///./narrativeiq.db
```

**frontend/.env**
```
VITE_API_BASE_URL=http://localhost:8000
```
=======
# narrativeiq
>>>>>>> 9529e6d34eab7a5b7f33a11572f6cae0e3140e28
