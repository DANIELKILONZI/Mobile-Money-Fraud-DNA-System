from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="Mobile Money Behavioral Risk Intelligence API",
    description=(
        "A fraud detection and behavioral intelligence engine for mobile money "
        "transactions. Analyzes transaction behavior, builds a graph of interactions, "
        "and outputs real-time risk scores."
    ),
    version="1.0.0",
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
