from dotenv import load_dotenv
import os
from functools import wraps

import jwt
from jwt import PyJWKClient
from flask import request, jsonify

load_dotenv()
AUTH0_DOMAIN = os.environ["AUTH0_DOMAIN"]
AUTH0_AUDIENCE = os.environ["AUTH0_AUDIENCE"]

ISSUER = f"https://{AUTH0_DOMAIN}/"
JWKS_URL = f"{ISSUER}.well-known/jwks.json"

jwks_client = PyJWKClient(JWKS_URL)


def requires_permission(permission):
    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            authorization = request.headers.get(
                "Authorization", ""
            )

            if not authorization.startswith("Bearer "):
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Bearer token required"
                }), 401

            token = authorization[7:].strip()

            if not token:
                return jsonify({
                    "error": "Unauthorized"
                }), 401

            try:
                signing_key = jwks_client.get_signing_key_from_jwt(
                    token
                )

                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=AUTH0_AUDIENCE,
                    issuer=ISSUER,
                    options={
                        "require": ["exp", "iss", "aud", "sub"]
                    }
                )

            except jwt.PyJWTError as error:

                # Log only the error type, never the token
                print("JWT validation failed:", type(error).__name__)

                return jsonify({
                    "error": "Unauthorized",
                    "message": "Invalid or expired access token"
                }), 401


            permissions = payload.get("permissions", [])

            if permission not in permissions:
                return jsonify({
                    "error": "Forbidden",
                    "message": "Insufficient permissions"
                }), 403

            return function(*args, **kwargs)

        return wrapper

    return decorator
