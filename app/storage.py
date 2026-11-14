from collections import defaultdict
from itertools import count
from threading import Lock

from flask import current_app
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from .models import AuthSession, SavedRoute, User, db, utc_now


def get_store():
    return current_app.extensions["busadda_store"]


class SQLStore:
    def create_user(self, name, email, password_hash):
        if self.find_user(email) is not None:
            return False
        db.session.add(User(full_name=name, email=email, password_hash=password_hash))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if self.find_user(email) is None:
                raise
            return False
        return True

    def find_user(self, email):
        return db.session.scalar(select(User).where(User.email == email))

    def add_session(self, token_hash, user_id, expires_at):
        db.session.execute(delete(AuthSession).where(AuthSession.expires_at <= utc_now()))
        db.session.add(AuthSession(token_hash=token_hash, user_id=user_id, expires_at=expires_at))
        db.session.commit()

    def authenticated_user(self, token_hash, user_id):
        record = db.session.get(AuthSession, token_hash)
        if record is None or record.user_id != user_id or record.expires_at <= utc_now():
            return None
        return db.session.get(User, user_id)

    def remove_session(self, token_hash):
        db.session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))
        db.session.commit()

    def count_saved(self, user_id):
        return db.session.scalar(select(func.count()).select_from(SavedRoute).where(SavedRoute.user_id == user_id))

    def list_saved(self, user_id):
        return list(db.session.scalars(select(SavedRoute).where(SavedRoute.user_id == user_id)
                                       .order_by(SavedRoute.created_at.desc(), SavedRoute.id.desc())))

    def save_route(self, user_id, source, target, mode):
        existing = select(SavedRoute).where(
            SavedRoute.user_id == user_id, SavedRoute.source_stop_id == source,
            SavedRoute.destination_stop_id == target, SavedRoute.routing_mode == mode,
        )
        row = db.session.scalar(existing)
        if row:
            return row, False
        row = SavedRoute(user_id=user_id, source_stop_id=source, destination_stop_id=target, routing_mode=mode)
        db.session.add(row)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            row = db.session.scalar(existing)
            if row is None:
                raise
            return row, False
        return row, True

    def delete_saved(self, user_id, route_id):
        result = db.session.execute(delete(SavedRoute).where(SavedRoute.id == route_id, SavedRoute.user_id == user_id))
        db.session.commit()
        return result.rowcount > 0


class MemoryStore:
    """Process-local demo storage. A shared lock keeps compound updates atomic."""

    def __init__(self):
        self.users = {}
        self.users_by_id = {}
        self.sessions = {}
        self.routes = defaultdict(dict)
        self.user_ids = count(1)
        self.route_ids = count(1)
        self.lock = Lock()

    def create_user(self, name, email, password_hash):
        with self.lock:
            if email in self.users:
                return False
            user = User(id=next(self.user_ids), full_name=name, email=email,
                        password_hash=password_hash, created_at=utc_now())
            self.users[email] = user
            self.users_by_id[user.id] = user
            return True

    def find_user(self, email):
        with self.lock:
            return self.users.get(email)

    def add_session(self, token_hash, user_id, expires_at):
        with self.lock:
            now = utc_now()
            self.sessions = {key: record for key, record in self.sessions.items() if record.expires_at > now}
            self.sessions[token_hash] = AuthSession(token_hash=token_hash, user_id=user_id, expires_at=expires_at)

    def authenticated_user(self, token_hash, user_id):
        with self.lock:
            record = self.sessions.get(token_hash)
            if record is None or record.user_id != user_id or record.expires_at <= utc_now():
                return None
            return self.users_by_id[user_id]

    def remove_session(self, token_hash):
        with self.lock:
            self.sessions.pop(token_hash, None)

    def count_saved(self, user_id):
        with self.lock:
            return len(self.routes.get(user_id, {}))

    def list_saved(self, user_id):
        with self.lock:
            return list(reversed(self.routes.get(user_id, {}).values()))

    def save_route(self, user_id, source, target, mode):
        with self.lock:
            routes = self.routes[user_id]
            for row in routes.values():
                if (row.source_stop_id, row.destination_stop_id, row.routing_mode) == (source, target, mode):
                    return row, False
            row = SavedRoute(id=next(self.route_ids), user_id=user_id, source_stop_id=source,
                             destination_stop_id=target, routing_mode=mode, created_at=utc_now())
            routes[row.id] = row
            return row, True

    def delete_saved(self, user_id, route_id):
        with self.lock:
            return self.routes.get(user_id, {}).pop(route_id, None) is not None
