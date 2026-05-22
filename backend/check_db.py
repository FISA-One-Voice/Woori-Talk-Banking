from sqlalchemy import text
from app.core.database import engine

def check_db_changes():
    with engine.connect() as conn:
        print("\n========== 1. accounts 테이블 컬럼 확인 ==========")
        cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'accounts';")).fetchall()
        
        has_is_primary = False
        for c in cols:
            if c[0] == "is_primary":
                has_is_primary = True
                print(f"✅ 발견됨! 👉 {c[0]} ({c[1]})")
            else:
                print(f"   - {c[0]} ({c[1]})")
                
        if not has_is_primary:
            print("❌ is_primary 컬럼이 없습니다!")

        print("\n========== 2. registered_recipients 유니크 제약조건 확인 ==========")
        idxs = conn.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'registered_recipients';")).fetchall()
        
        has_unique_idx = False
        for i in idxs:
            if "UNIQUE" in i[1] and "user_id" in i[1] and "alias" in i[1]:
                has_unique_idx = True
                print(f"✅ 발견됨! 👉 {i[0]}: {i[1]}")
            else:
                print(f"   - {i[0]}")
                
        if not has_unique_idx:
            print("❌ user_id, alias 조합의 유니크 제약조건이 없습니다!")
        print("\n")

if __name__ == "__main__":
    check_db_changes()
