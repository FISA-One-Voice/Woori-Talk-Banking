import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from sqlalchemy import text

USER_ID = 'e0d8499f-1589-426c-a7a3-6c8332be3d35'

db = SessionLocal()
try:
    db.execute(text(f"DELETE FROM event_participations WHERE user_id = '{USER_ID}'"))
    db.execute(text(f"DELETE FROM standing_orders WHERE user_id = '{USER_ID}'"))
    db.execute(text(f"DELETE FROM transactions WHERE user_id = '{USER_ID}'"))
    db.execute(text(f"DELETE FROM registered_recipients WHERE user_id = '{USER_ID}'"))
    db.execute(text(f"DELETE FROM accounts WHERE user_id = '{USER_ID}'"))
    db.execute(text(f"DELETE FROM users WHERE user_id = '{USER_ID}'"))
    db.commit()
    print("삭제 완료!")
except Exception as e:
    db.rollback()
    print(f"오류: {e}")
finally:
    db.close()