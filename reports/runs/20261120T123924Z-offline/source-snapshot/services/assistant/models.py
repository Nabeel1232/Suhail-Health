"""Chat history is separate from the clinical ledger and cannot advance care."""
from sqlalchemy import String, Text, JSON, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from services.api.db import Base, now_iso, uid


class AssistantConversation(Base):
    __tablename__ = 'assistant_conversations'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('chat'))
    owner_id: Mapped[str] = mapped_column(String, index=True)
    owner_role: Mapped[str] = mapped_column(String)
    organization: Mapped[str] = mapped_column(String)
    patient_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, default='Care workspace conversation')
    related_case_ids: Mapped[list] = mapped_column(JSON, default=list)
    access_dependencies: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, index=True)


class AssistantMessage(Base):
    __tablename__ = 'assistant_messages'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uid('chatmsg'))
    conversation_id: Mapped[str] = mapped_column(ForeignKey('assistant_conversations.id'), index=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    answer: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    context_case_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
