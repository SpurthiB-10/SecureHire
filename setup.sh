#!/usr/bin/env bash
# SecureHire AI — one-command local bootstrap (non-Docker path)
# For the Docker path, just run: cd docker && docker compose up --build
set -e

echo "=== SecureHire AI: local bootstrap ==="

echo "[1/5] Generating synthetic dataset..."
cd pipelines
pip install -r requirements.txt --quiet
python3 generate_dataset.py --n 5000

echo "[2/5] Running ETL pipeline (ingest -> clean -> load)..."
python3 run_pipeline.py
cd ..

echo "[3/5] Training ML models..."
cd ml
pip install -r requirements.txt --quiet
python3 train.py
cd ..

echo "[4/5] Setting up backend..."
cd backend
pip install -r requirements.txt --quiet
cp -n .env.example .env || true
echo "  -> Edit backend/.env with your DATABASE_URL / REDIS_URL, then run:"
echo "     uvicorn app.main:app --reload"
cd ..

echo "[5/5] Setting up frontend..."
cd frontend
npm install
echo "  -> Run: npm run dev"
cd ..

echo ""
echo "✅ Bootstrap complete."
echo "   Backend:  cd backend && uvicorn app.main:app --reload   (http://localhost:8000/docs)"
echo "   Frontend: cd frontend && npm run dev                    (http://localhost:5173)"
