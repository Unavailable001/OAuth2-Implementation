
import os
import time
import secrets
import sqlite3
import hashlib
import hmac
import logging
import requests
from urllib.parse import urlencode

from contextlib import contextmanager
from typing import Iterator

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Response,
    Depends,
    Header
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from pydantic import BaseModel, Field

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.auth import exceptions as google_exceptions


# -----------------------------------
# 1. Configuration
# -----------------------------------

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/auth/callback"
)

FRONTEND_ORIGIN = os.getenv(
    "FRONTEND_ORIGIN",
    "http://localhost:4200"
)

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "sessions.db"
)

COOKIE_SECURE = (
    os.getenv("COOKIE_SECURE", "false").lower() == "true"
)

SESSION_COOKIE_NAME = (
    "__Host-portal_session"
    if COOKIE_SECURE
    else "portal_session"
)

SESSION_TTL_SECONDS = 30 * 60
OAUTH_STATE_TTL_SECONDS = 10 * 60
logger = logging.getLogger(__name__)


if not GOOGLE_CLIENT_ID:
    raise RuntimeError("GOOGLE_CLIENT_ID is missing")


# -----------------------------------
# 2. FastAPI application
# -----------------------------------

app = FastAPI(
    title="OAuth Learning Portal API",
    version="1.0.0"
)


# -----------------------------------
# 3. CORS configuration
# -----------------------------------

app.add_middleware(
    CORSMiddleware,

    allow_origins=[FRONTEND_ORIGIN],

    allow_credentials=True,

    allow_methods=["GET", "POST"],

    allow_headers=[
        "Content-Type",
        "X-CSRF-Token"
    ]
)


# -----------------------------------
# 4. Database connection
# -----------------------------------

@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:

    connection = sqlite3.connect(DATABASE_PATH)

    connection.row_factory = sqlite3.Row

    try:

        yield connection

        connection.commit()

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()


# -----------------------------------
# 5. Create database table
# -----------------------------------

def initialize_database():

    with get_db() as connection:

        connection.execute("""

            CREATE TABLE IF NOT EXISTS sessions (

                session_hash TEXT PRIMARY KEY,

                google_sub TEXT NOT NULL,

                email TEXT,

                name TEXT,

                csrf_hash TEXT NOT NULL,

                expires_at INTEGER NOT NULL

            )

        """)


initialize_database()


# -----------------------------------
# 6. Utility functions
# -----------------------------------

def hash_value(value: str) -> str:

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def check_frontend_origin(request: Request):

    origin = request.headers.get("origin")

    if origin != FRONTEND_ORIGIN:

        raise HTTPException(
            status_code=403,
            detail="Invalid request origin"
        )


# -----------------------------------
# 7. Request model
# -----------------------------------

class GoogleLoginRequest(BaseModel):

    id_token: str = Field(min_length=1)


# -----------------------------------
# 8. Health check
# -----------------------------------

@app.get("/health")
def health_check():

    return {
        "status": "Backend is running"
    }


# -----------------------------------
# 9. Google OAuth and session creation
# -----------------------------------

def create_portal_session(claims: dict, response: Response) -> dict:
    if claims.get("iss") not in [
        "accounts.google.com",
        "https://accounts.google.com"
    ]:
        raise HTTPException(status_code=401, detail="Invalid token issuer")

    google_sub = claims.get("sub")
    if not isinstance(google_sub, str) or not google_sub:
        raise HTTPException(status_code=401, detail="Invalid user identity")

    email_verified = claims.get("email_verified") is True
    email = claims.get("email") if email_verified else None
    name = claims.get("name")

    session_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + SESSION_TTL_SECONDS

    with get_db() as connection:
        connection.execute(
            "DELETE FROM sessions WHERE expires_at <= ?",
            (int(time.time()),)
        )
        connection.execute(
            """
            INSERT INTO sessions (
                session_hash, google_sub, email, name, csrf_hash, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                hash_value(session_id),
                google_sub,
                email,
                name,
                hash_value(csrf_token),
                expires_at
            )
        )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/"
    )
    response.headers["Cache-Control"] = "no-store"

    return {
        "authenticated": True,
        "user": {
            "provider": "google",
            "provider_user_id": google_sub,
            "email": email,
            "email_verified": email_verified,
            "name": name
        },
        "csrf_token": csrf_token
    }


def clear_oauth_cookies(response: Response) -> None:
    response.delete_cookie("oauth_state", path="/auth/callback")
    response.delete_cookie("oauth_nonce", path="/auth/callback")


def redirect_to_login(error: str) -> RedirectResponse:
    url = f"{FRONTEND_ORIGIN.rstrip('/')}/login?{urlencode({'authError': error})}"
    response = RedirectResponse(url, status_code=303)
    clear_oauth_cookies(response)
    return response


@app.get("/auth/login")
def start_google_login():
    if not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_CLIENT_SECRET is not configured in the backend"
        )

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce
    })

    response = RedirectResponse(authorization_url, status_code=302)
    for cookie_name, value in (("oauth_state", state), ("oauth_nonce", nonce)):
        response.set_cookie(
            key=cookie_name,
            value=value,
            max_age=OAUTH_STATE_TTL_SECONDS,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            path="/auth/callback"
        )
    return response


@app.get("/auth/callback")
def google_login_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None
):
    saved_state = request.cookies.get("oauth_state")
    saved_nonce = request.cookies.get("oauth_nonce")
    if (
        not state
        or not saved_state
        or not hmac.compare_digest(state, saved_state)
        or not saved_nonce
    ):
        logger.warning("Google OAuth callback rejected: invalid state")
        return redirect_to_login("invalid_state")

    if error or not code:
        logger.warning("Google OAuth callback returned without an authorization code")
        return redirect_to_login("authorization_failed")

    try:
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            },
            timeout=10
        )
        token_response.raise_for_status()
        token_data = token_response.json()
    except (requests.RequestException, ValueError):
        logger.exception("Google authorization-code exchange failed")
        return redirect_to_login("token_exchange_failed")

    if not isinstance(token_data, dict):
        logger.error("Google returned an invalid token response")
        return redirect_to_login("invalid_token_response")

    google_id_token = token_data.get("id_token")
    if not isinstance(google_id_token, str):
        logger.error("Google token response did not contain an ID token")
        return redirect_to_login("missing_id_token")

    try:
        claims = id_token.verify_oauth2_token(
            google_id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
    except (ValueError, google_exceptions.GoogleAuthError):
        logger.exception("Google ID token verification failed")
        return redirect_to_login("invalid_id_token")

    claim_nonce = claims.get("nonce")
    if (
        not isinstance(claim_nonce, str)
        or not hmac.compare_digest(claim_nonce, saved_nonce)
    ):
        logger.warning("Google OAuth callback rejected: invalid nonce")
        return redirect_to_login("invalid_nonce")

    response = RedirectResponse(
        f"{FRONTEND_ORIGIN.rstrip('/')}/dashboard",
        status_code=303
    )
    try:
        create_portal_session(claims, response)
    except HTTPException:
        return redirect_to_login("invalid_identity")

    clear_oauth_cookies(response)
    return response


@app.post("/auth/google")
def authenticate_google(
    payload: GoogleLoginRequest,
    request: Request,
    response: Response
):
    check_frontend_origin(request)

    try:
        claims = id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Google ID token"
        )
    except google_exceptions.TransportError:
        raise HTTPException(
            status_code=503,
            detail="Google verification service unavailable"
        )
    except google_exceptions.GoogleAuthError:
        raise HTTPException(
            status_code=401,
            detail="Google token verification failed"
        )

    return create_portal_session(claims, response)


# -----------------------------------
# 10. Session authentication dependency
# -----------------------------------

def get_current_session(request: Request):

    session_id = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if not session_id:

        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )


    session_hash = hash_value(session_id)


    with get_db() as connection:

        row = connection.execute("""

            SELECT *

            FROM sessions

            WHERE session_hash = ?

        """, (session_hash,)).fetchone()


    if row is None:

        raise HTTPException(
            status_code=401,
            detail="Invalid session"
        )


    if row["expires_at"] <= int(time.time()):

        with get_db() as connection:

            connection.execute("""

                DELETE FROM sessions

                WHERE session_hash = ?

            """, (session_hash,))

        raise HTTPException(
            status_code=401,
            detail="Session expired"
        )


    return dict(row)


# -----------------------------------
# 11. Current user endpoint
# -----------------------------------

@app.get("/auth/me")
def get_current_user(

    response: Response,

    session: dict = Depends(get_current_session)

):

    response.headers["Cache-Control"] = "no-store"

    return {

        "authenticated": True,

        "user": {

            "provider": "google",

            "provider_user_id": session["google_sub"],

            "email": session["email"],

            "name": session["name"]

        }

    }


# -----------------------------------
# 12. Get a fresh CSRF token
# -----------------------------------

@app.get("/auth/csrf")
def get_csrf_token(

    response: Response,

    session: dict = Depends(get_current_session)

):

    csrf_token = secrets.token_urlsafe(32)

    csrf_hash = hash_value(csrf_token)


    with get_db() as connection:

        connection.execute("""

            UPDATE sessions

            SET csrf_hash = ?

            WHERE session_hash = ?

        """, (

            csrf_hash,
            session["session_hash"]

        ))


    response.headers["Cache-Control"] = "no-store"


    return {

        "csrf_token": csrf_token

    }


# -----------------------------------
# 13. Logout with CSRF protection
# -----------------------------------

@app.post("/auth/logout")
def logout(

    request: Request,

    response: Response,

    session: dict = Depends(get_current_session),

    x_csrf_token: str | None = Header(
        default=None,
        alias="X-CSRF-Token"
    )

):

    check_frontend_origin(request)


    if not x_csrf_token:

        raise HTTPException(
            status_code=403,
            detail="CSRF token required"
        )


    received_hash = hash_value(x_csrf_token)

    if not hmac.compare_digest(
        received_hash,
        session["csrf_hash"]
    ):

        raise HTTPException(
            status_code=403,
            detail="Invalid CSRF token"
        )


    # Invalidate session in database

    with get_db() as connection:

        connection.execute("""

            DELETE FROM sessions

            WHERE session_hash = ?

        """, (session["session_hash"],))


    # Remove browser cookie

    response.delete_cookie(

        key=SESSION_COOKIE_NAME,

        path="/",

        httponly=True,

        secure=COOKIE_SECURE,

        samesite="lax"

    )

    response.headers["Cache-Control"] = "no-store"


    return {

        "logged_out": True,

        "message": "Session terminated successfully"

    }
