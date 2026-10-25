# IP-SAKTI: Traditional Knowledge Prior Art Intelligence Platform

IP-SAKTI bridges ancient codified Ayurvedic literature (**Charaka Samhita** via NIIMH e-Samhita) with modern international intellectual property examination (**USPTO, EPO, WIPO**) to validate prior art and defend against biopiracy under **Section 3(p) of the Indian Patents Act, 1970**.

---

## 🎨 Frontend & Stitch Screens

The user interface implements the **Vedic Jurisprudence** design system (authoritative legal-academic atmosphere rooted in historical botany and archival precision).

### Saved Stitch Project Assets (`frontend/stitch-screens/`):
- **Screen 1 (Query & Overview)**: `frontend/stitch-screens/screen_1_query.html` & `screen_1_query.png`
- **Screen 2 (Honest Abstention)**: `frontend/stitch-screens/screen_2_abstention.html` & `screen_2_abstention.png`
- **Screen 3 (Query Processing)**: `frontend/stitch-screens/screen_3_processing.html` & `screen_3_processing.png`
- **Screen 4 (Evidence & Overlap Results)**: `frontend/stitch-screens/screen_4_results.html` & `screen_4_results.png`

### Production Integrated Application:
- **`frontend/index.html`**: A fully functional Single-Page Application (SPA) integrating all 4 screen states, dynamic query processing, honest abstention handling, and live API synchronization.

---

## 🚀 Running Backend & Frontend in Sync

### Step 1: Start Databases (Qdrant & PostgreSQL)
Ensure Docker Desktop is running, then execute:
```bash
docker compose up -d
```
- **Qdrant Vector DB**: `http://localhost:6333/dashboard`
- **PostgreSQL**: Port `5432` (`ipsakti` db)

### Step 2: Start the FastAPI Backend
Using the local virtual environment:
```bash
# Windows PowerShell
.\.venv\Scripts\uvicorn api.main:app --reload --port 8000
```
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **Liveness Health Check**: `http://localhost:8000/health`
- **Semantic Retrieval**: `POST http://localhost:8000/query` with body `{"query": "your search"}`

### Step 3: Launch the Frontend
Open `frontend/index.html` directly in your browser or run a simple local web server:
```bash
# Serve frontend on port 3000
python -m http.server 3000 --directory frontend
```
Visit: **`http://localhost:3000`**

---

## 🔄 Backend & Frontend Synchronization Details

1. **Independent Dual Search**:
   - The NIIMH Traditional Knowledge corpus (Sanskrit/Devanagari) and the Global Patent index (English) run independently.
   - Patent leads are never suppressed if NIIMH search has lower confidence, and vice versa.

2. **Honest Abstention Mechanism**:
   - Threshold is calibrated to `0.30` cosine similarity.
   - If top score < `0.30`, `niimh.abstained` is `true`. The frontend displays the **Honest Abstention** view while still displaying potential patent overlap leads.

3. **Live Health Monitoring**:
   - The frontend continuously pings `GET /health` to display live API connection status in the sidebar.

4. **Evidence Dossier Export**:
   - Generates a timestamped JSON compliance audit file directly from search results.
