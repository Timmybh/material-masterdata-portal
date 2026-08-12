from fastapi import FastAPI

app = FastAPI(
    title="Material Masterdata Portal API",
    version="1.2.0",
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "material-masterdata-portal"}


@app.get("/api/v1")
async def api_root():
    return {
        "name": "Material Masterdata Portal",
        "version": "1.2.0",
        "workflow": [
            "USER",
            "MASTERDATA",
            "ACCOUNTING",
            "COMPLETED",
        ],
    }
