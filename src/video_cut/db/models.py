"""SQLAlchemy database models for the enterprise video-cut platform."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        Enum("admin", "editor", "viewer", name="user_roles"),
        default="editor",
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    versions = relationship("GenerationVersion", back_populates="creator")
    deleted_versions = relationship(
        "UserDeletedVersion", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Project(Base):
    """Project grouping model."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(
        Enum("active", "archived", "deleted", name="project_status"),
        default="active",
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    owner = relationship("User", back_populates="projects")
    videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project {self.name}>"


class Video(Base):
    """Video processing model."""

    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    duration = Column(Float, nullable=True)
    resolution = Column(String(20), nullable=True)
    file_size = Column(Integer, nullable=True)
    status = Column(
        Enum(
            "uploaded",
            "processing",
            "ready",
            "failed",
            name="video_status",
        ),
        default="uploaded",
        nullable=False,
    )
    metadata_json = Column("metadata", Text, nullable=True)  # JSON string
    current_version_id = Column(
        Integer, ForeignKey("generation_versions.id"), nullable=True
    )
    total_versions = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    project = relationship("Project", back_populates="videos")
    versions = relationship(
        "GenerationVersion",
        back_populates="video",
        cascade="all, delete-orphan",
        foreign_keys="GenerationVersion.video_id"  # Specify which FK to use
    )
    highlights = relationship(
        "Highlight", back_populates="video", cascade="all, delete-orphan"
    )
    current_version = relationship(
        "GenerationVersion",
        foreign_keys=[current_version_id]  # Specify the FK for current version
    )

    def __repr__(self) -> str:
        return f"<Video {self.original_filename}>"


class GenerationVersion(Base):
    """Version tracking model for generated highlights and merged videos."""

    __tablename__ = "generation_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    status = Column(
        Enum(
            "generating",
            "completed",
            "failed",
            name="version_status",
        ),
        default="generating",
        nullable=False,
    )

    # Configuration snapshot
    prompt = Column(Text, nullable=True)
    highlight_count = Column(Integer, nullable=True)
    max_duration = Column(Float, nullable=True)
    with_subtitles = Column(Boolean, default=False, nullable=False)

    # Result file paths
    highlights_json_path = Column(String(500), nullable=True)
    merged_video_path = Column(String(500), nullable=True)

    file_size = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    delete_reason = Column(Text, nullable=True)

    # Relationships
    video = relationship(
        "Video",
        back_populates="versions",
        foreign_keys=[video_id]  # Explicitly specify which FK to use
    )
    creator = relationship("User", back_populates="versions")
    clips = relationship(
        "ClipVersion", back_populates="version", cascade="all, delete-orphan"
    )
    user_deletions = relationship(
        "UserDeletedVersion", back_populates="version", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GenerationVersion v{self.version_number}>"


class Highlight(Base):
    """Highlight segment model."""

    __tablename__ = "highlights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    quote = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="highlights")
    clip_versions = relationship(
        "ClipVersion", back_populates="highlight", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Highlight {self.title}>"


class ClipVersion(Base):
    """Individual clip within a generation version."""

    __tablename__ = "clip_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    generation_version_id = Column(
        Integer, ForeignKey("generation_versions.id"), nullable=False, index=True
    )
    highlight_id = Column(Integer, ForeignKey("highlights.id"), nullable=False, index=True)
    clip_path = Column(String(500), nullable=True)
    subtitled_clip_path = Column(String(500), nullable=True)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    version = relationship("GenerationVersion", back_populates="clips")
    highlight = relationship("Highlight", back_populates="clip_versions")

    def __repr__(self) -> str:
        return f"<ClipVersion {self.order_index}>"


class UserDeletedVersion(Base):
    """Track user-initiated deletions for audit and restore."""

    __tablename__ = "user_deleted_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(
        Integer, ForeignKey("generation_versions.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    deleted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reason = Column(Text, nullable=True)

    # Relationships
    version = relationship("GenerationVersion", back_populates="user_deletions")
    user = relationship("User", back_populates="deleted_versions")

    def __repr__(self) -> str:
        return f"<UserDeletedVersion v{self.version_id} by u{self.user_id}>"
