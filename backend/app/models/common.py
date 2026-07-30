from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, JSON, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("departments.id"))
    org_year = Column(Integer)
    dept_type = Column(String(20), default="team")
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    parent = relationship("Department", remote_side="Department.id", back_populates="children")
    children = relationship("Department", back_populates="parent")
    users = relationship("User", back_populates="department")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    employee_code = Column(String(20), unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(150))
    phone = Column(String(20))
    department_id = Column(Integer, ForeignKey("departments.id"))
    position = Column(String(50))
    role = Column(String(30), default="user")
    labor_type = Column(String(20), default="원가")
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    department = relationship("Department", back_populates="users")


class ApiToken(Base):
    __tablename__ = "api_tokens"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    token_prefix = Column(String(20), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scopes = Column(JSON)
    expires_at = Column(DateTime)
    last_used_at = Column(DateTime)
    revoked_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", foreign_keys=[user_id])
    creator = relationship("User", foreign_keys=[created_by])


class UserRegistration(Base):
    __tablename__ = "user_registrations"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False)
    employee_code = Column(String(20))
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(150))
    phone = Column(String(20))
    department = Column(String(100))
    position = Column(String(50))
    reason = Column(Text)
    status = Column(String(20), default="pending")   # pending / approved / rejected
    rejection_reason = Column(Text)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

    reviewer = relationship("User", foreign_keys=[reviewed_by])


class Notice(Base):
    __tablename__ = "notices"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    creator = relationship("User", foreign_keys=[created_by])
    attachments = relationship("NoticeAttachment", back_populates="notice", cascade="all, delete-orphan")


class NoticeAttachment(Base):
    __tablename__ = "notice_attachments"
    id = Column(Integer, primary_key=True, index=True)
    notice_id = Column(Integer, ForeignKey("notices.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    content_type = Column(String(100))
    file_size = Column(Integer, default=0)
    file_path = Column(String(500), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    notice = relationship("Notice", back_populates="attachments")
    creator = relationship("User", foreign_keys=[created_by])


class OpinionPost(Base):
    __tablename__ = "opinion_posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    answer = Column(Text)
    answered_by = Column(Integer, ForeignKey("users.id"))
    answered_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    creator = relationship("User", foreign_keys=[created_by])
    answerer = relationship("User", foreign_keys=[answered_by])
    attachments = relationship("OpinionAttachment", back_populates="post", cascade="all, delete-orphan")


class OpinionAttachment(Base):
    __tablename__ = "opinion_attachments"
    id = Column(Integer, primary_key=True, index=True)
    opinion_id = Column(Integer, ForeignKey("opinion_posts.id"), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    content_type = Column(String(100))
    file_size = Column(Integer, default=0)
    file_path = Column(String(500), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())

    post = relationship("OpinionPost", back_populates="attachments")
    creator = relationship("User", foreign_keys=[created_by])


class OpinionNotificationSetting(Base):
    __tablename__ = "opinion_notification_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    notify_on_new_post = Column(Boolean, default=True)
    notify_on_registration = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])



class Holiday(Base):
    __tablename__ = "holidays"
    __table_args__ = (
        UniqueConstraint("year", "month", "day", name="uq_holidays_ymd"),
    )

    id = Column(Integer, primary_key=True, index=True)
    year = Column(String(4), nullable=False, index=True)
    month = Column(String(2), nullable=False, index=True)
    day = Column(String(2), nullable=False, index=True)
    content = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    @property
    def date(self) -> str:
        return f"{self.year}-{self.month}-{self.day}"


class CalendarSchedule(Base):
    __tablename__ = "calendar_schedules"
    __table_args__ = (
        UniqueConstraint("google_event_id", "category", name="uq_calendar_schedules_google_category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    google_event_id = Column(String(255), nullable=False, index=True)
    category = Column(String(20), nullable=False, index=True)  # company / refresh
    content = Column(String(255), nullable=False)
    type = Column(String(30), nullable=False)
    user_name = Column(String(100), nullable=False)
    is_all_day = Column(Boolean, default=True)
    date = Column(Date)
    end_date = Column(Date)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    schedule_kind = Column(String(50))
    timesheet_project_id = Column(Integer)
    timesheet_project_name = Column(String(255))
    timesheet_project_source = Column(String(20), default="공통")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    creator = relationship("User", foreign_keys=[created_by])

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String(50))
    action = Column(String(20), nullable=False)
    table_name = Column(String(100))
    record_id = Column(String(50))
    old_values = Column(JSON)
    new_values = Column(JSON)
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=func.now())
