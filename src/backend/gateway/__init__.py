"""aigate OpenAI-compatible gateway package.

Submodules:
* ``resolver``      — resolve ``provider:`` / ``combo:`` model refs to upstreams.
* ``provider_adapter`` — forward requests to an upstream via httpx.
* ``router``        — FastAPI ``APIRouter`` exposing ``/v1`` endpoints.
* ``errors``        — OpenAI-shaped error envelope types + handler.
"""
