PUBLIC_PATHS = frozenset(
    {
        "/api/v1/system/health",
        "/api/v1/identity/authn/signup",
        "/api/v1/identity/authn/login",
        "/api/v1/identity/authn/refresh",
        "/api/v1/identity/authn/forgot-password",
        "/docs",
        "/docs/oauth2-redirect",
        "/openapi.json",
        "/redoc",
    }
)


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS
