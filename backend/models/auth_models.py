"""
AUTH MODELS
NarrativeIQ — User, Session, Story database schemas
Uses SQLite via SQLAlchemy (zero config, no server needed)
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Column, String, DateTime, Integer, Text, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


# ─────────────────────────────────────────
# DATABASE TABLES (SQLAlchemy)
# ─────────────────────────────────────────

class UserDB(Base):
    __tablename__ = "users"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name          = Column(String, nullable=False)
    email         = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)
    is_active     = Column(Boolean, default=True)

    stories = relationship("StoryDB", back_populates="user", cascade="all, delete-orphan")


class StoryDB(Base):
    __tablename__ = "stories"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id       = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    series_title  = Column(String, nullable=False)
    story_idea    = Column(Text, nullable=False)
    genre         = Column(String, nullable=True)
    episode_count = Column(Integer, nullable=False, default=5)
    status        = Column(String, default="pending")  # pending/running/complete/failed
    job_id        = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    completed_at  = Column(DateTime, nullable=True)

    user     = relationship("UserDB", back_populates="stories")
    episodes = relationship("EpisodeDB", back_populates="story", cascade="all, delete-orphan")
    analysis = relationship("AnalysisDB", back_populates="story", uselist=False, cascade="all, delete-orphan")


class EpisodeDB(Base):
    __tablename__ = "episodes"

    id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id         = Column(String, ForeignKey("stories.id"), nullable=False, index=True)
    episode_number   = Column(Integer, nullable=False)
    title            = Column(String, nullable=False)
    plot_beat        = Column(Text, nullable=True)
    emotion_score    = Column(Float, nullable=True)
    cliffhanger_score= Column(Float, nullable=True)
    continuity_score = Column(Float, nullable=True)
    drop_off_probability = Column(Float, nullable=True)

    story = relationship("StoryDB", back_populates="episodes")


class AnalysisDB(Base):
    __tablename__ = "analyses"

    id                  = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id            = Column(String, ForeignKey("stories.id"), nullable=False, unique=True)
    overall_arc_score   = Column(Float, nullable=True)
    avg_cliffhanger     = Column(Float, nullable=True)
    avg_drop_off        = Column(Float, nullable=True)
    continuity_issues   = Column(Integer, default=0)
    flat_zones          = Column(Text, nullable=True)   # JSON string
    suggestions_json    = Column(Text, nullable=True)   # Full pipeline JSON
    created_at          = Column(DateTime, default=datetime.utcnow)

    story = relationship("StoryDB", back_populates="analysis")


# ─────────────────────────────────────────
# PYDANTIC SCHEMAS (request/response)
# ─────────────────────────────────────────

# — Auth —

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    email: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True

# — Story —

class StoryCreateRequest(BaseModel):
    series_title: str = Field(..., min_length=1, max_length=100)
    story_idea: str   = Field(..., min_length=20)
    target_episodes: int = Field(default=5, ge=2, le=12)

class StoryResponse(BaseModel):
    id: str
    series_title: str
    story_idea: str
    status: str
    job_id: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

class StoryHistoryItem(BaseModel):
    id: str
    series_title: str
    status: str
    episode_count: int
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True
