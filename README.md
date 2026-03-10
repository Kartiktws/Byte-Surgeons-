# DICOM & STL Compression Engine

Compress and decompress **DICOM** medical images (lossless & lossy) and **STL** meshes (lossless & lossy). Backend: FastAPI (Python). Frontend: Next.js.

---

## Prerequisites

- **Git**
- **Python 3.10+** (3.11 or 3.12 recommended)
- **Node.js 18+** and **npm** (for the frontend)

---

## 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/dicom_compressor.git
```

*(Replace the URL with your actual repo URL if different.)*

---

## 2. Backend setup

All commands below are from the **project root** (`dicom_compressor/`).

### Option A: Using a virtual environment (recommended)

```bash
# Create and activate a virtual environment
# Windows (PowerShell):
python -m venv venv
.\venv\Scripts\Activate.ps1

# Windows (CMD):
python -m venv venv
venv\Scripts\activate.bat

# macOS / Linux:
python3 -m venv venv
source venv/bin/activate
```

### Install Python dependencies

```bash
pip install -r requirements.txt
```

### Run the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

You should see something like:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

- **API docs (Swagger):** http://127.0.0.1:8000/docs  
- **Health check:** http://127.0.0.1:8000/health  

Keep this terminal open while using the app.

---

## 3. Frontend setup

Open a **new terminal** in the project root.

### Install Node dependencies

```bash
cd frontend
npm install
```

### Run the frontend

```bash
npm run dev
```

You should see:

```
▲ Next.js 16.x.x
- Local: http://localhost:3000
```

- **App in browser:** http://localhost:3000  

The frontend talks to the backend at `http://127.0.0.1:8000` by default. To use another URL, set:

```bash
# Windows (PowerShell):
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"

# macOS / Linux:
export NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Then run `npm run dev` again.

---

## 4. Quick run summary

| Step | Where | Command |
|------|--------|---------|
| 1 | Project root | `pip install -r requirements.txt` |
| 2 | Project root | `uvicorn backend.main:app --reload --port 8000` |
| 3 | New terminal → `frontend/` | `npm install` then `npm run dev` |
| 4 | Browser | Open http://localhost:3000 |

---

## Features

- **DICOM**
  - **Lossless:** Predictor + Huffman → `.dcmz` (bit-exact recovery).
  - **Lossy:** Preprocess → Quantize → Wavelet → Threshold → Huffman → `.dcmz` (configurable Q and threshold).
- **STL**
  - **Lossless:** Parse → Deduplicate → Delta → Huffman → ZSTD → `.twsc`.
  - **Lossy:** Parse → Weld → QEM decimate → Quantize → Morton reorder → Delta → Huffman → ZSTD → `.twsc` (quality: high / med / low).

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/compress` | Upload `.dcm` → lossless compress → stats + download |
| POST | `/compress/lossy` | Upload `.dcm` → lossy compress (Q, threshold_pct) |
| POST | `/decompress` | Upload `.dcmz` → get recovered `.dcm` |
| POST | `/stl/compress` | Upload `.stl` → lossless or simple lossy → `.twsc` |
| POST | `/stl/compress/lossy` | Upload `.stl` → advanced lossy (weld + QEM + reorder) |
| POST | `/stl/decompress` | Upload `.twsc` → get recovered `.stl` |

Interactive docs: **http://127.0.0.1:8000/docs**

---

## Run tests

From the **project root**:

```bash
pytest tests/ -v
```

---

## Project structure

```
dicom_compressor/
├── backend/
│   ├── main.py              # FastAPI app & routes
│   └── compressor/         # DICOM & STL compression logic
├── frontend/               # Next.js app
│   ├── app/
│   └── lib/
├── docs/                    # Approach & block diagrams
│   ├── 01-lossless-dicom.md
│   ├── 02-lossy-dicom.md
│   ├── 03-stl-lossless.md
│   └── 04-stl-lossy.md
├── tests/
├── requirements.txt
└── README.md
```

For detailed pipeline descriptions and block diagrams, see the **docs/** folder.

---

## Troubleshooting

- **Backend won’t start:** Ensure you’re in the project root and ran `pip install -r requirements.txt`. Use Python 3.10+.
- **Frontend can’t reach API:** Ensure the backend is running on port 8000. If it’s on another host/port, set `NEXT_PUBLIC_API_URL` and restart `npm run dev`.
- **CORS errors:** The backend allows all origins in development; if you still see issues, confirm the backend URL in the frontend env.
- **`open3d` install fails (e.g. on some Linux):** STL lossy uses Open3D for QEM decimation. You can try `pip install open3d` separately or use a different OS/Python version; lossless STL and all DICOM features work without it.
