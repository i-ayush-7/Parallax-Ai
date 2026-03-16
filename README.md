# Parallax AI

> A real-time AI pair-programming assistant that lives as a transparent HUD overlay on your desktop. Speak or type — it sees your screen, hears your voice, and responds with audio and code simultaneously.

---

## What it does

Parallax AI is a floating HUD overlay built with Electron that connects to a FastAPI backend powered by two Gemini models running in parallel:

- **gemini-2.5-flash-native-audio** handles all voice I/O and live screen vision via Google's Live API
- **gemini-2.5-flash** handles typed text messages and voice transcripts, streaming clean text and code to the HUD

You can ask it to debug errors it sees on your screen, write code, explain concepts, or execute terminal commands — all hands-free via voice, or through the built-in chat input.

---

## Tech stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron |
| Frontend | HTML / CSS / Vanilla JS |
| Backend | Python + FastAPI + Uvicorn |
| Voice model | gemini-2.5-flash-native-audio-preview-12-2025 |
| Text/chat model | gemini-2.5-flash |
| AI SDK | google-genai (Python) |
| Deployment | Google Cloud Run |

---

## Prerequisites

- Node.js 18+
- Python 3.11+
- A Google AI API key with access to Gemini Live API
- (For deployment) Google Cloud CLI (`gcloud`)

---

## Local setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/parallax-ai.git
cd parallax-ai
```

### 2. Install Python dependencies

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Set your API key

```bash
# Windows
set GEMINI_API_KEY=your_api_key_here

# macOS / Linux
export GEMINI_API_KEY=your_api_key_here
```

### 4. Start the backend

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 5. Install Electron dependencies and launch

```bash
npm install
npm start
```

The HUD overlay will appear in the top-right corner of your screen.

### 6. Using the app

1. Click **Init Screen** — select the screen/window you want the AI to watch
2. Click **Init Audio** — grant microphone access
3. Speak naturally or type in the chat box
4. For bash/cmd code blocks, click **Execute** to run commands directly

---

## Project structure

```
parallax-ai/
├── main.py              # FastAPI backend — WebSocket server, dual-model routing
├── main.js              # Electron entry point — window config, screen capture routing
├── index.html           # HUD frontend — UI, audio pipeline, markdown renderer
├── package.json         # Electron dependencies
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container image for Cloud Run
├── cloudbuild.yaml      # Cloud Build CI/CD config
└── deploy.sh            # One-command GCP deployment script
```

---

## Cloud deployment

See [deploy.sh](./deploy.sh) for automated deployment, or follow the manual steps in the [Cloud Run deployment guide](./DEPLOY.md).

---

## Architecture

See the architecture diagram in the submission for a full visual breakdown of how the Electron frontend, FastAPI backend, and dual Gemini models connect.

---

## License

MIT
