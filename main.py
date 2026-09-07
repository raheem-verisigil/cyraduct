"""
Cyraduct — reference implementation.

An open, vendor-neutral reliance and consequence-boundary protocol for
AI agent actions. Converts governance and assurance evidence into
machine-enforceable reliance limits, with independent Ed25519-signed
receipts, revocation, evidence registration, and conformance testing.

Run locally:
    uvicorn main:app --reload

Deploy: see README.md for Railway instructions.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import advisory, attested, broker, conformance, admin, evidence, receipts as receipts_router
from app.storage import init_db
from app import crypto

app = FastAPI(
    title="Cyraduct",
    description=(
        "Open, vendor-neutral reliance and consequence-boundary protocol. "
        "Receipts are Ed25519-signed and independently verifiable via "
        "/v1/public-key — no trust in this server required to verify one. "
        "See /v1/conformance/fixtures for published test vectors, "
        "including cases the protocol must refuse."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(advisory.router)
app.include_router(attested.router)
app.include_router(broker.router)
app.include_router(conformance.router)
app.include_router(admin.router)
app.include_router(evidence.router)
app.include_router(receipts_router.router)

# Initialize storage at import time so it's ready even under test clients
# that don't trigger startup events (and again on startup for safety).
init_db()


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {
        "service": "cyraduct",
        "version": "0.2.0",
        "tiers": ["advisory", "attested", "broker"],
        "docs": "/docs",
        "public_key": "/v1/public-key",
        "conformance_fixtures": "/v1/conformance/fixtures",
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/v1/public-key")
def public_key():
    """The Ed25519 public key used to sign all receipts. Fetch this once
    and verify receipts locally — you do not need to trust or call back
    to this server to check a receipt's authenticity. See
    verify_receipt.py in the repo for a standalone verification example."""
    return {
        "key_id": crypto.key_id(),
        "alg": "Ed25519",
        "public_key_b64": crypto.public_key_b64(),
    }
