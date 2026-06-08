from sqlalchemy.orm import Session
from ..models.common import AuditLog


def log_action(db: Session, user_id: int, username: str, action: str,
               table_name: str, record_id: str = None,
               old_values: dict = None, new_values: dict = None,
               ip_address: str = None):
    log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        table_name=table_name,
        record_id=str(record_id) if record_id else None,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
    )
    db.add(log)
    db.commit()
