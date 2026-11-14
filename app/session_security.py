from hashlib import sha256
from secrets import token_urlsafe

from flask import session


def session_token_hash():
    token = session.get("auth_token")
    return sha256(token.encode()).hexdigest() if token else None


def create_session_token():
    session["auth_token"] = token_urlsafe(32)
    return session_token_hash()
