# VoidGuard — AI Fraud Detection (Separated Files)

## 📁 File Structure

```
voidguard-static/
├── index.html        ← Main HTML (structure & markup only)
├── css/
│   └── style.css     ← All styles (iOS glass UI, layout, components)
└── js/
    └── app.js        ← All JavaScript (API calls, charts, logic)
```

## 🚀 How to Run

### Option 1 — Open directly in browser
Just double-click `index.html` — works in offline/demo mode without the backend.

### Option 2 — Local server (recommended, avoids CORS issues)
```bash
# Python
python -m http.server 8080

# Node.js
npx serve .

# VS Code
Install "Live Server" extension → right-click index.html → Open with Live Server
```
Then visit: http://localhost:8080

## 🔌 Connect to FastAPI Backend

1. Start your Python backend:
```bash
uvicorn api_v2:app --host 0.0.0.0 --port 8000 --reload
```

2. In the Detect page, set the API URL to `http://localhost:8000`

The app works in **demo mode** when the API is offline (simulates results using the same scoring logic as `predict.py`).
