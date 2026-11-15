import json
from typing import Any, Dict

from fastapi import Body, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from BODtoJSON import (
    BODParseError,
    BODStructureError,
    __version__,
    convert,
    project,
    to_json,
    to_ndjson,
)

MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MiB, aligned with library default

app = FastAPI(
    title="BODtoJSON API",
    version=__version__,
    description="Safe zero-dependency OAGIS BOD to Flattened JSON engine. Unauthenticated — deploy behind your own auth or a reverse proxy.",
)


@app.middleware("http")
async def limit_request_body_size(request: Request, call_next):
    """Reject oversized POST bodies on every route, including JSON wrappers.

    The body is still read into memory once (Starlette caches it). Operators
    should also enforce a limit at the reverse proxy.
    """
    if request.method in {"POST", "PUT", "PATCH"}:
        body = await request.body()
        if len(body) > MAX_BODY_SIZE:
            return JSONResponse(
                {
                    "status": "error",
                    "message": f"Request body exceeds {MAX_BODY_SIZE} bytes.",
                },
                status_code=413,
            )
    return await call_next(request)


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
        "version": __version__,
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


def _handle_library_result(result_str: str, media_type: str = "application/json"):
    """If the library returned an error object, turn it into HTTP 400."""
    try:
        parsed = json.loads(result_str.strip())
        if isinstance(parsed, dict) and parsed.get("status") == "error":
            return JSONResponse(parsed, status_code=400)
    except json.JSONDecodeError:
        pass
    return Response(content=result_str, media_type=media_type)


@app.post("/convert/ndjson")
async def convert_to_ndjson_stream(
    xml_data: str = Body(..., media_type="text/plain"),
    verb: str = "Sync",
):
    try:
        result_str = to_ndjson(xml_data, verb, raise_on_error=True)
        return Response(content=result_str, media_type="application/x-ndjson")
    except (BODParseError, BODStructureError) as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/convert/json")
async def convert_to_standard_json(
    xml_data: str = Body(..., media_type="text/plain"),
    verb: str = "Sync",
):
    try:
        result_str = to_json(xml_data, verb, raise_on_error=True)
        return Response(content=result_str, media_type="application/json")
    except (BODParseError, BODStructureError) as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/project")
async def project_bod_schema(req: ProjectRequest):
    try:
        items = project(req.xml, req.verb, req.schema_map, include_header=req.include_header)
        return Response(content=json.dumps(items), media_type="application/json")
    except (BODParseError, BODStructureError) as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# Legacy endpoints
@app.post("/convert")
async def legacy_convert_raw_xml(
    xml_data: str = Body(..., media_type="text/plain"),
    verb: str = "Sync",
):
    try:
        result_str = convert(xml_data, verb)
        return _handle_library_result(result_str)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/convert/json/wrapper")
async def legacy_convert_json_wrapper(req: BODRequest):
    try:
        result_str = convert(req.xml, req.verb)
        return _handle_library_result(result_str)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
