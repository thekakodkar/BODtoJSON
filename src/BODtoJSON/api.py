from fastapi import FastAPI, Body, Response
from pydantic import BaseModel
from BODtoJSON import to_json, to_ndjson, convert

app = FastAPI(
    title="BODtoJSON API",
    version="2.0.0",
    description="Zero-Dependency Enterprise OAGIS Integration Data Fabric Engine"
)

# -------------------------------------------------------------------
# PYDANTIC SCHEMAS (For Structured JSON Input Endpoints)
# -------------------------------------------------------------------
class BODRequest(BaseModel):
    xml: str
    verb: str = "Sync"


# -------------------------------------------------------------------
# METRIC/HEALTH ENDPOINTS
# -------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "service": "BODtoJSON",
        "status": "running",
        "version": "2.0.0"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# -------------------------------------------------------------------
# MODERN ENDPOINTS (Optimized text/plain input for Swagger UI)
# -------------------------------------------------------------------

@app.post("/convert/ndjson")
async def convert_to_ndjson_stream(
    xml_data: str = Body(..., media_type="text/plain", description="Paste raw OAGIS XML BOD here"), 
    verb: str = "Sync"
):
    """Transforms raw XML payloads into strict single-line NDJSON format."""
    try:
        # High performance raw text return - zero double-serialization overhead
        result_str = to_ndjson(xml_data, verb)
        return Response(content=result_str, media_type="application/x-ndjson")
    except Exception as e:
        return Response(
            content=f'{{"status": "error", "message": "{str(e)}"}}',
            status_code=500,
            media_type="application/json"
        )


@app.post("/convert/json")
async def convert_to_standard_json(
    xml_data: str = Body(..., media_type="text/plain", description="Paste raw OAGIS XML BOD here"), 
    verb: str = "Sync"
):
    """Transforms raw XML payloads into standard flattened JSON strings."""
    try:
        result_str = to_json(xml_data, verb)
        return Response(content=result_str, media_type="application/json")
    except Exception as e:
        return Response(
            content=f'{{"status": "error", "message": "{str(e)}"}}',
            status_code=500,
            media_type="application/json"
        )


# -------------------------------------------------------------------
# LEGACY ENDPOINTS (Preserved exactly to prevent production breaks)
# -------------------------------------------------------------------

@app.post("/convert")
async def legacy_convert_raw_xml(
    xml_data: str = Body(..., media_type="text/plain", description="Paste raw OAGIS XML BOD here"), 
    verb: str = "Sync"
):
    """Legacy endpoint mapping directly to the backward-compatible convert function."""
    try:
        result_str = convert(xml_data, verb)
        return Response(content=result_str, media_type="application/json")
    except Exception as e:
        return Response(
            content=f'{{"status": "error", "message": "{str(e)}"}}',
            status_code=500,
            media_type="application/json"
        )


@app.post("/convert/json/wrapper")
async def legacy_convert_json_wrapper(req: BODRequest):
    """
    Legacy structured JSON request endpoint.
    Expects JSON input: {"xml": "<PurchaseOrder>...</PurchaseOrder>", "verb": "Sync"}
    """
    try:
        result_str = convert(req.xml, req.verb)
        return Response(content=result_str, media_type="application/json")
    except Exception as e:
        return Response(
            content=f'{{"status": "error", "message": "{str(e)}"}}',
            status_code=500,
            media_type="application/json"
        )