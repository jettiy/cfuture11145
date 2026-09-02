# Run & Deploy (GitHub / Cloudflare)

## Prerequisites

- Node.js 18+
- Python 3.10+
- (Optional) Cloudflare account for Workers + Cron

## 1. Backend (FastAPI)

```bash
cd backend
cp .env.example .env
# Edit .env: set SECRET_KEY, LLM_API_KEY, etc. Never commit .env.

python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

pip install -r requirements.txt
python main.py
```

- API: http://localhost:8000  
- Docs: http://localhost:8000/docs  

## 2. Frontend (Next.js)

```bash
cd frontend
cp .env.example .env.local
# Edit .env.local: set NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_WS_URL if needed.

npm install
npm run dev
```

- App: http://localhost:3001  

## 3. Production build (frontend)

```bash
cd frontend
npm run build
npm run start
```

## 4. First-time admin (optional)

```bash
cd backend
# Activate venv then:
python create_admin.py
# Follow prompts for username/password.
```

## 5. Cloudflare Workers (Frontend – OpenNext)

Frontend는 **frontend** 폴더 기준으로 OpenNext로 배포합니다. 자동 마이그레이션 없이 수동 구성됨.

- **Cloudflare 대시보드**: Root directory = `frontend`, Build command = `npm run deploy` (또는 `npm run build` 후 deploy 단계만).
- **로컬에서 배포**:
  ```bash
  cd frontend
  npm install   # 또는 npm ci (frontend/package-lock.json 사용)
  npm run deploy
  ```
- **미리보기**: `npm run preview` (opennextjs-cloudflare build 후 wrangler dev).
- **의존성**: `frontend/package-lock.json`이 있으므로 Cloudflare가 `frontend`를 루트로 두고 빌드해도 lock file 인식됨.
- **Cron**: `cloudflare-cron/` Worker; `BACKEND_URL`, `CRON_SECRET` 등. See `docs/CRON_CLOUDFLARE.md`.

## Final folder structure (minimal for GitHub)

```
.
├── .gitignore
├── README.md
├── DEPLOYMENT.md
├── RUN.md
├── package.json
├── package-lock.json
├── run.ps1
├── backend/
│   ├── .env.example
│   ├── main.py
│   ├── requirements.txt
│   ├── README_SETUP.md
│   ├── create_admin.py
│   └── app/
│       ├── __init__.py
│       ├── auth.py
│       ├── database.py
│       ├── init_db.py
│       ├── migrations.py
│       ├── models.py
│       ├── schemas.py
│       ├── scheduler.py
│       ├── websocket.py
│       ├── prompts/
│       ├── routers/
│       └── services/
├── frontend/
│   ├── .env.example
│   ├── .npmrc
│   ├── .dev.vars
│   ├── package.json
│   ├── package-lock.json
│   ├── wrangler.jsonc
│   ├── open-next.config.ts
│   ├── next.config.js
│   ├── public/_headers
│   ├── app/
│   ├── components/
│   └── lib/
├── cloudflare-cron/
│   ├── src/index.js
│   └── wrangler.toml
└── docs/
    └── CRON_CLOUDFLARE.md
```

**Not in repo (gitignored):** `.env`, `.env.local`, `venv/`, `node_modules/`, `.next/`, `.open-next/`, `__pycache__/`, `*.db`, `.vscode/`, `.idea/`.
