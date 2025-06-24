# eyecite API

This project exposes eyecite's core citation extraction, resolution, annotation, and cleaning functions as a RESTful API using FastAPI.

## Endpoints

- `POST /extract` — Extract citations from text
- `POST /resolve` — Cluster and resolve citations
- `POST /annotate` — Annotate text with citation markup
- `POST /clean` — Clean and preprocess text
- `POST /extract-resolve` — Extract and resolve citations in one step
- `POST /dump` — (Optional) Dump detailed citation metadata

All endpoints accept and return JSON.

## Example Usage

### Run Locally

```bash
# Build and run with Docker
cd /workspaces/eyecite

docker build -t eyecite-api .
docker run -p 8000:8000 eyecite-api
```

### Example Request (extract citations)

```bash
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{"text": "See 410 U.S. 113 (1973)."}'
```

### API Documentation

Once running, visit [http://localhost:8000/docs](http://localhost:8000/docs) for interactive OpenAPI docs.

## Development

- Edit `api/main.py` to modify or add endpoints.
- Update `requirements.txt` for dependencies.
- See `PLAN.md` for design notes.

## Security & Production

- Limit request size and sanitize input for production.
- Add authentication if needed.

---

See `PLAN.md` for more details and roadmap.
