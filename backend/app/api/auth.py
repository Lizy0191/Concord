import secrets
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.actions import Principal

bearer = HTTPBearer(auto_error=False)


def authenticate(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> Principal:
    if credentials is None:
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    settings = request.app.state.services.settings
    tokens: list[
        tuple[str, str, Literal["viewer", "coordinator", "approver", "safety_approver", "admin"]]
    ] = [
        (
            settings.api_token,
            "local-admin" if settings.profile in {"local", "desktop"} else "team-admin",
            "admin",
        ),
        (settings.viewer_token, "viewer", "viewer"),
        (settings.coordinator_token, "coordinator", "coordinator"),
        (settings.approver_token, "reviewer", "approver"),
        (settings.safety_token, "safety-reviewer", "safety_approver"),
    ]
    for token, identity, role in tokens:
        if secrets.compare_digest(credentials.credentials, token):
            return Principal(id=identity, role=role)
    raise HTTPException(401, "Invalid token", headers={"WWW-Authenticate": "Bearer"})


CurrentUser = Annotated[Principal, Depends(authenticate)]


def services(request: Request):
    return request.app.state.services
