"""database.py — Supabase PostgreSQL ma'lumotlar bazasi"""

import json
import logging
import os
from contextlib import contextmanager
from datetime import date
from typing import Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean, Column, DateTime, Integer, BigInteger, String, Text,
    create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

load_dotenv()
logger = logging.getLogger("Database")
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    user_id        = Column(BigInteger, primary_key=True, index=True)
    username       = Column(String(100), nullable=True)
    first_name     = Column(String(100), nullable=True)
    last_name      = Column(String(100), nullable=True)
    language_code  = Column(String(10),  default="uz")
    plan           = Column(String(20),  default="free")
    plan_expires   = Column(DateTime,    nullable=True)
    ai_mode        = Column(String(30),  default="assistant")
    total_messages = Column(Integer,     default=0)
    joined_at      = Column(DateTime,    server_default=func.now())
    last_active    = Column(DateTime,    server_default=func.now(), onupdate=func.now())
    is_banned      = Column(Boolean,     default=False)
    settings       = Column(Text,        default="{}")


class Conversation(Base):
    __tablename__ = "conversations"
    id         = Column(Integer,    primary_key=True, autoincrement=True)
    user_id    = Column(BigInteger, index=True, nullable=False)
    role       = Column(String(10), nullable=False)
    content    = Column(Text,       nullable=False)
    media_type = Column(String(20), default="text")
    created_at = Column(DateTime,   server_default=func.now())


class Memory(Base):
    __tablename__ = "memories"
    id         = Column(Integer,    primary_key=True, autoincrement=True)
    user_id    = Column(BigInteger, index=True, nullable=False)
    category   = Column(String(30), default="umumiy")
    content    = Column(Text,       nullable=False)
    importance = Column(Integer,    default=1)
    created_at = Column(DateTime,   server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    id         = Column(Integer,     primary_key=True, autoincrement=True)
    user_id    = Column(BigInteger,  index=True, nullable=False)
    title      = Column(String(200), nullable=False)
    type       = Column(String(30),  default="umumiy")
    content    = Column(Text,        nullable=False)
    created_at = Column(DateTime,    server_default=func.now())
    updated_at = Column(DateTime,    server_default=func.now(), onupdate=func.now())


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    user_id    = Column(BigInteger, primary_key=True)
    usage_date = Column(String(10), primary_key=True)
    msg_count  = Column(Integer,    default=0)


class Analytics(Base):
    __tablename__ = "analytics"
    id             = Column(Integer,  primary_key=True, autoincrement=True)
    snapshot_date  = Column(DateTime, server_default=func.now())
    total_users    = Column(Integer,  default=0)
    active_today   = Column(Integer,  default=0)
    total_messages = Column(Integer,  default=0)
    free_users     = Column(Integer,  default=0)
    pro_users      = Column(Integer,  default=0)
    elite_users    = Column(Integer,  default=0)


class Broadcast(Base):
    __tablename__ = "broadcasts"
    id         = Column(Integer,   primary_key=True, autoincrement=True)
    admin_id   = Column(BigInteger, nullable=False)
    message    = Column(Text,      nullable=False)
    sent_count = Column(Integer,   default=0)
    created_at = Column(DateTime,  server_default=func.now())


class Database:
    def __init__(self, database_url: str = None):
        url = database_url or os.getenv("DATABASE_URL", "")
        if not url:
            raise ValueError("DATABASE_URL topilmadi!")
        self.engine = create_engine(
            url,
            pool_size=5, max_overflow=10, pool_timeout=30,
            pool_recycle=1800, pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

    @contextmanager
    def session(self):
        s = self.SessionLocal()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def init(self):
        Base.metadata.create_all(bind=self.engine)
        logger.info("Supabase PostgreSQL — jadvallar tayyor.")

    # ── FOYDALANUVCHILAR ──────────────────────────────────────────

    def upsert_user(self, user_id, username=None, first_name=None, last_name=None, language_code="uz"):
        with self.session() as s:
            u = s.get(User, user_id)
            if u:
                u.username = username
                u.first_name = first_name
                u.last_name = last_name
            else:
                s.add(User(user_id=user_id, username=username,
                           first_name=first_name, last_name=last_name,
                           language_code=language_code))

    def get_user(self, user_id) -> Optional[Dict]:
        with self.session() as s:
            u = s.get(User, user_id)
            return self._u(u) if u else None

    def update_user(self, user_id, **kwargs):
        if not kwargs: return
        with self.session() as s:
            u = s.get(User, user_id)
            if u:
                for k, v in kwargs.items():
                    setattr(u, k, v)

    def get_user_settings(self, user_id) -> dict:
        u = self.get_user(user_id)
        try: return json.loads((u or {}).get("settings", "{}") or "{}")
        except: return {}

    def set_user_setting(self, user_id, key, value):
        s = self.get_user_settings(user_id)
        s[key] = value
        self.update_user(user_id, settings=json.dumps(s))

    def get_all_users(self, not_banned=True) -> List[Dict]:
        with self.session() as s:
            q = s.query(User)
            if not_banned: q = q.filter(User.is_banned == False)
            return [self._u(u) for u in q.all()]

    def ban_user(self, user_id, banned=True):
        self.update_user(user_id, is_banned=banned)

    def _u(self, u: User) -> Dict:
        return {
            "user_id": u.user_id, "username": u.username,
            "first_name": u.first_name, "last_name": u.last_name,
            "language_code": u.language_code, "plan": u.plan,
            "plan_expires": str(u.plan_expires) if u.plan_expires else None,
            "ai_mode": u.ai_mode, "total_messages": u.total_messages,
            "joined_at": str(u.joined_at) if u.joined_at else "",
            "last_active": str(u.last_active) if u.last_active else "",
            "is_banned": u.is_banned, "settings": u.settings or "{}",
        }

    # ── KUNLIK LIMIT ──────────────────────────────────────────────

    def get_today_usage(self, user_id) -> int:
        today = date.today().isoformat()
        with self.session() as s:
            row = s.query(DailyUsage).filter_by(user_id=user_id, usage_date=today).first()
            return row.msg_count if row else 0

    def increment_usage(self, user_id):
        today = date.today().isoformat()
        with self.session() as s:
            row = s.query(DailyUsage).filter_by(user_id=user_id, usage_date=today).first()
            if row: row.msg_count += 1
            else: s.add(DailyUsage(user_id=user_id, usage_date=today, msg_count=1))
            u = s.get(User, user_id)
            if u: u.total_messages = (u.total_messages or 0) + 1

    # ── SUHBAT TARIXI ─────────────────────────────────────────────

    def add_message(self, user_id, role, content, media_type="text"):
        with self.session() as s:
            s.add(Conversation(user_id=user_id, role=role, content=content, media_type=media_type))

    def get_history(self, user_id, limit=20) -> List[Dict]:
        with self.session() as s:
            rows = s.query(Conversation).filter_by(user_id=user_id)\
                    .order_by(Conversation.created_at.desc()).limit(limit).all()
            return [{"role": r.role, "content": r.content} for r in reversed(rows)]

    def clear_history(self, user_id):
        with self.session() as s:
            s.query(Conversation).filter_by(user_id=user_id).delete()

    # ── XOTIRA ────────────────────────────────────────────────────

    def add_memory(self, user_id, content, category="umumiy", importance=1):
        with self.session() as s:
            s.add(Memory(user_id=user_id, category=category, content=content, importance=importance))

    def get_memories(self, user_id, limit=25) -> List[Dict]:
        with self.session() as s:
            rows = s.query(Memory).filter_by(user_id=user_id)\
                    .order_by(Memory.importance.desc(), Memory.created_at.desc()).limit(limit).all()
            return [{"id": r.id, "category": r.category, "content": r.content,
                     "importance": r.importance, "created_at": str(r.created_at)} for r in rows]

    def clear_memories(self, user_id):
        with self.session() as s: s.query(Memory).filter_by(user_id=user_id).delete()

    def count_memories(self, user_id) -> int:
        with self.session() as s: return s.query(Memory).filter_by(user_id=user_id).count()

    # ── LOYIHALAR ─────────────────────────────────────────────────

    def save_project(self, user_id, title, content, ptype="umumiy") -> int:
        with self.session() as s:
            p = Project(user_id=user_id, title=title, content=content, type=ptype)
            s.add(p); s.flush(); return p.id

    def get_projects(self, user_id) -> List[Dict]:
        with self.session() as s:
            rows = s.query(Project).filter_by(user_id=user_id)\
                    .order_by(Project.updated_at.desc()).all()
            return [self._p(r) for r in rows]

    def get_project(self, project_id, user_id) -> Optional[Dict]:
        with self.session() as s:
            r = s.query(Project).filter_by(id=project_id, user_id=user_id).first()
            return self._p(r) if r else None

    def delete_project(self, project_id, user_id):
        with self.session() as s:
            s.query(Project).filter_by(id=project_id, user_id=user_id).delete()

    def count_projects(self, user_id) -> int:
        with self.session() as s: return s.query(Project).filter_by(user_id=user_id).count()

    def _p(self, p: Project) -> Dict:
        return {"id": p.id, "user_id": p.user_id, "title": p.title,
                "type": p.type, "content": p.content,
                "created_at": str(p.created_at), "updated_at": str(p.updated_at)}

    # ── ANALITIKA ─────────────────────────────────────────────────

    def snapshot_analytics(self):
        with self.session() as s:
            total   = s.query(User).filter_by(is_banned=False).count()
            today   = date.today().isoformat()
            active  = s.query(DailyUsage).filter(
                DailyUsage.usage_date == today, DailyUsage.msg_count > 0).count()
            msgs    = s.query(func.sum(User.total_messages)).scalar() or 0
            free_u  = s.query(User).filter_by(plan="free",  is_banned=False).count()
            pro_u   = s.query(User).filter_by(plan="pro",   is_banned=False).count()
            elite_u = s.query(User).filter_by(plan="elite", is_banned=False).count()
            s.add(Analytics(total_users=total, active_today=active, total_messages=msgs,
                            free_users=free_u, pro_users=pro_u, elite_users=elite_u))

    def get_latest_analytics(self) -> Dict:
        with self.session() as s:
            r = s.query(Analytics).order_by(Analytics.id.desc()).first()
            if not r: return {}
            return {"total_users": r.total_users, "active_today": r.active_today,
                    "total_messages": r.total_messages, "free_users": r.free_users,
                    "pro_users": r.pro_users, "elite_users": r.elite_users}

    def log_broadcast(self, admin_id, message, sent_count):
        with self.session() as s:
            s.add(Broadcast(admin_id=admin_id, message=message, sent_count=sent_count))
