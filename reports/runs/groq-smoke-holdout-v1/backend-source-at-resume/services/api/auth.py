import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, Request, HTTPException
from sqlalchemy import select
from .db import User, SessionToken, get_db, now_iso
from .config import settings

COOKIE = 'suhail_session'


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000).hex()
    return 'pbkdf2_sha256$310000$' + salt + '$' + digest


def password_verify(password, encoded):
    try:
        _, rounds, salt, digest = encoded.split('$')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def user_dict(user):
    return {k: getattr(user, k) for k in ['id', 'name', 'role', 'organization', 'patient_id']}


def create_session(db, user, response):
    token = secrets.token_urlsafe(40)
    db.add(SessionToken(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()))
    db.commit()
    response.set_cookie(COOKIE, token, max_age=8*3600, httponly=True,
        secure=settings()['session_secure'], samesite='lax', path='/')
    return user_dict(user)


def require_actor(request: Request, db=Depends(get_db)):
    token = request.cookies.get(COOKIE)
    if token:
        session = db.get(SessionToken, hashlib.sha256(token.encode()).hexdigest())
        if session and session.expires_at > now_iso():
            user = db.get(User, session.user_id)
            if user:
                return user_dict(user)
    supplied = request.headers.get('X-Connector-Token')
    org = next((organization for organization, credential in settings()['connector_tokens'].items()
        if supplied and hmac.compare_digest(supplied, credential)), None)
    if org:
        if request.headers.get('X-Organization', org) != org:
            raise HTTPException(403, 'Authenticated connector organization does not match the requested source.')
        return {'id': 'connector:' + org, 'name': 'Synthetic connector', 'role': 'connector',
                'organization': org, 'patient_id': None}
    raise HTTPException(401, 'Sign in to continue.')
