# Deploy FixMyCity to GitHub + Vercel

## 1. Push this folder to GitHub

```bash
git init
git add .
git commit -m "feat: FixMyCity hackathon MVP"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/fixmycity.git
git push -u origin main
```

Do not commit `.env`, `.venv`, `data/`, or `uploads/`.

## 2. Import into Vercel

1. Open Vercel.
2. Select **Add New → Project**.
3. Import the GitHub repository.
4. Keep the repository root as the Vercel project root.
5. Deploy.

Vercel's current Python runtime supports FastAPI with zero-configuration detection. The repository exposes the FastAPI application through `main.py`.

## 3. Environment variables

For a demo that does not call Kimi:

```text
FMC_AI_PROVIDER=mock
```

For real Kimi inference:

```text
FMC_AI_PROVIDER=auto
KIMI_API_KEY=<your key>
KIMI_MODEL=kimi-k3
```

Set these in Vercel Project Settings → Environment Variables. Never put the key in frontend code or GitHub.

## 4. Public URL and QR codes

After deployment, use the HTTPS Vercel URL for public QR codes. The QR endpoint automatically uses the forwarded Vercel host, so it no longer depends on localhost/LAN IP discovery in production.

## 5. Demo storage limitation

This hackathon deployment uses Vercel `/tmp` storage and seeds the 7 synthetic incidents on cold start. That keeps the demo self-contained without adding another database service, but `/tmp` is ephemeral and is not a durable multi-user database.

For production, replace SQLite with a durable database (such as Postgres/Neon) and move uploaded photos to durable object storage such as Vercel Blob.
