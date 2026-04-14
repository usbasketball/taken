# taken

Python/FastAPI backend for duty scheduling at [US Basketball Amsterdam](https://usbasketball.nl). Manages referee, table official, and hall duty (zaaldienst) assignments across ~125 members and ~126 home games per season.

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env  # set DATABASE_URL, ADMIN_PASSWORD, JWT_SECRET
alembic upgrade head
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`.

## Tests

```bash
pytest
```

## Deployment

Deployed on Vercel (Fluid Compute). Set environment variables via Vercel dashboard or `vercel env`. Database is PostgreSQL on Neon (Vercel Marketplace).

---

For architecture, commands, and development notes see [CLAUDE.md](CLAUDE.md).
