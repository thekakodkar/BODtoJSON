import json
from typing import Dict, Any
from fastapi import FastAPI, Body, Response
from pydantic import BaseModel
from BODtoJSON import to_json, to_ndjson, project, convert

app = FastAPI(
    title="BODtoJSON API",
    version="2.1.0",
    description="Zero-Dependency Enterprise OAGIS Integration Data Fabric Engine"
)


class BODRequest(BaseModel):
    xml: str
    verb: str = "Sync"


class ProjectRequest(BaseModel):
    xml: str
    verb: str = "Sync"
    schema_map: Dict[str, Any]
    include_header: bool = True


@app.get("/")
async def root():
    return {
        "service": "BODtoJSON",
        "status": "running",
        "version": "2.1.0"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# -------------------------------------------------------------------
# MODERN ENDPOINTS
# -------------------------------------------------------------------

@app.post("/convert/ndjson")
async def convert_to_ndjson_stream(
    xml_data: str = Body(..., media_type="text/plain", description="Paste raw OAGIS XML BOD here"),
    verb: str = "Sync"
):
    """Transforms raw XML payloads into strict single-line NDJSON format."""
    try:
        result_str = to_ndjson(xml_data, verb)
        return Response(content=result_str, media_type="application/x-ndjson")
    except Exception as e:
        return Response(
            content=json.dumps({"status": "error", "message": str(e)}),
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
            content=json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            media_type="application/json"
        )


@app.post("/project")
async def project_bod_schema(req: ProjectRequest):
    """Transforms and projects OAGIS XML directly into a target JSON schema."""
    try:
        items = project(req.xml, req.verb, req.schema_map, include_header=req.include_header)
        return Response(content=json.dumps(items), media_type="application/json")
    except Exception as e:
        return Response(
            content=json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            media_type="application/json"
        )


# -------------------------------------------------------------------
# LEGACY ENDPOINTS (Preserved for backward compatibility)
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
            content=json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            media_type="application/json"
        )


@app.post("/convert/json/wrapper")
async def legacy_convert_json_wrapper(req: BODRequest):
    """Legacy structured JSON request endpoint."""
    try:
        result_str = convert(req.xml, req.verb)
        return Response(content=result_str, media_type="application/json")
    except Exception as e:
        return Response(
            content=json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            media_type="application/json"
        )