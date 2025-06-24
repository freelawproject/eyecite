# PLAN.md

## Goal

Deploy eyecite in a Docker container and expose its core functions as RESTful API endpoints, enabling programmatic access to citation extraction, resolution, annotation, and cleaning.

---

## 1. Identify Core Functions to Expose

Based on [README.rst](README.rst) and [eyecite/__init__.py](eyecite/__init__.py), the main user-facing functions are:

- [`get_citations`](eyecite/find.py): Extract citations from text.
- [`resolve_citations`](eyecite/resolve.py): Cluster and resolve citations to logical referents.
- [`annotate_citations`](eyecite/annotate.py): Annotate text with markup around citations.
- [`clean_text`](eyecite/clean.py): Clean and preprocess text for citation extraction.

Optional:
- [`dump_citations`](eyecite/find.py): For debugging, returns detailed metadata for each citation.

---

## 2. Design API Endpoints

Proposed endpoints (all accept/return JSON):

- `POST /extract`
  - Input: `{ "text": "...", "options": {...} }`
  - Output: `{ "citations": [...] }`
  - Calls: `get_citations`

- `POST /resolve`
  - Input: `{ "citations": [...], "options": {...} }`
  - Output: `{ "clusters": {...} }`
  - Calls: `resolve_citations`

- `POST /annotate`
  - Input: `{ "text": "...", "annotations": [...], "options": {...} }`
  - Output: `{ "annotated_text": "..." }`
  - Calls: `annotate_citations`

- `POST /clean`
  - Input: `{ "text": "...", "steps": [...] }`
  - Output: `{ "cleaned_text": "..." }`
  - Calls: `clean_text`

- `POST /extract-resolve`
  - Input: `{ "text": "...", "options": {...} }`
  - Output: `{ "clusters": {...} }`
  - Calls: `get_citations` + `resolve_citations`

- (Optional) `POST /dump`
  - Input: `{ "text": "...", "options": {...} }`
  - Output: `{ "citations": [...] }`
  - Calls: `dump_citations`

---

## 3. Choose API Framework

- Use [FastAPI](https://fastapi.tiangolo.com/) (recommended for Python, async, OpenAPI support) or Flask.
- Add a `Dockerfile` to build the container.
- Add a `requirements.txt` or update `pyproject.toml` for API dependencies.

---

## 4. Implementation Steps

1. **API Server**
   - Create `api/` directory with `main.py` (FastAPI app).
   - Implement endpoints, mapping JSON requests to eyecite functions.
   - Validate and serialize input/output (handle citation objects, spans, etc.).

2. **Dockerization**
   - Write a `Dockerfile`:
     - Use official Python base image.
     - Install eyecite and API dependencies.
     - Set entrypoint to run the API server (e.g., `uvicorn api.main:app`).

3. **Testing**
   - Add example requests for each endpoint.
   - Add unit/integration tests for API.

4. **Documentation**
   - Document endpoints in `README.md` or via OpenAPI (FastAPI auto-generates).
   - Provide usage examples (e.g., with `curl` or Python requests).

5. **Deployment**
   - Optionally add a `docker-compose.yml` for local development.
   - Push image to a registry if needed.

---

## 5. Example Directory Structure

```
eyecite/
api/
  main.py
Dockerfile
requirements.txt
PLAN.md
README.md
...
```

---

## 6. Notes

- Consider exposing tokenizer selection and options via API.
- For large texts, support file uploads or streaming if needed.
- Ensure security best practices (limit request size, sanitize input).
- Optionally, add authentication for production deployments.

---

## 7. References

- [eyecite/README.rst](README.rst)
- [eyecite/__init__.py](eyecite/__init__.py)
- [eyecite/annotate.py](eyecite/annotate.py)
- [eyecite/find.py](eyecite/find.py)
- [eyecite/resolve.py](eyecite/resolve.py)
- [eyecite/clean.py](eyecite/clean.py)
