from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

import sys
sys.path.append("..")  # Ensure eyecite is importable

from eyecite import get_citations, resolve_citations, annotate_citations, clean_text
try:
    from eyecite.find import dump_citations
except ImportError:
    dump_citations = None

app = FastAPI(title="eyecite API", description="RESTful API for citation extraction, resolution, annotation, and cleaning.")

# --- Pydantic Models ---
class ExtractRequest(BaseModel):
    text: str
    options: Optional[Dict[str, Any]] = None

class ExtractResponse(BaseModel):
    citations: Any

class ResolveRequest(BaseModel):
    citations: Any
    options: Optional[Dict[str, Any]] = None

class ResolveResponse(BaseModel):
    clusters: Any

class AnnotateRequest(BaseModel):
    text: str
    annotations: Any
    options: Optional[Dict[str, Any]] = None

class AnnotateResponse(BaseModel):
    annotated_text: str

class CleanRequest(BaseModel):
    text: str
    steps: Optional[List[str]] = None

class CleanResponse(BaseModel):
    cleaned_text: str

class ExtractResolveRequest(BaseModel):
    text: str
    options: Optional[Dict[str, Any]] = None

class ExtractResolveResponse(BaseModel):
    clusters: Any

class DumpRequest(BaseModel):
    text: str
    options: Optional[Dict[str, Any]] = None

class DumpResponse(BaseModel):
    citations: Any

# --- Endpoints ---
@app.post("/extract", response_model=ExtractResponse)
def extract(req: ExtractRequest):
    citations = get_citations(req.text, **(req.options or {}))
    return {"citations": citations}

@app.post("/resolve", response_model=ResolveResponse)
def resolve(req: ResolveRequest):
    clusters = resolve_citations(req.citations, **(req.options or {}))
    return {"clusters": clusters}

@app.post("/annotate", response_model=AnnotateResponse)
def annotate(req: AnnotateRequest):
    annotated = annotate_citations(req.text, req.annotations, **(req.options or {}))
    return {"annotated_text": annotated}

@app.post("/clean", response_model=CleanResponse)
def clean(req: CleanRequest):
    cleaned = clean_text(req.text, steps=req.steps)
    return {"cleaned_text": cleaned}

@app.post("/extract-resolve", response_model=ExtractResolveResponse)
def extract_resolve(req: ExtractResolveRequest):
    citations = get_citations(req.text, **(req.options or {}))
    clusters = resolve_citations(citations, **(req.options or {}))
    return {"clusters": clusters}

if dump_citations:
    @app.post("/dump", response_model=DumpResponse)
    def dump(req: DumpRequest):
        citations = dump_citations(req.text, **(req.options or {}))
        return {"citations": citations}
