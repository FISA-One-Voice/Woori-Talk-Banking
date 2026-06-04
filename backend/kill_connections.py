import os
import sqlalchemy
from dotenv import load_dotenv


def kill_aiven_connections():
    # 백엔드 폴더에서 실행하므로, 상위 폴더(루트)의 .env 파일을 명시적으로 지정해서 불러옵니다.
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    load_dotenv(env_path)

    # .env 파일에 DATABASE_URL이 통째로 있다면 그걸 쓰고, 없다면 개별 조각들을 조립합니다.
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        # 개별 조각(POSTGRES_*) 조립
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        host = os.getenv("POSTGRES_HOST")
        port = os.getenv("POSTGRES_PORT")
        db = os.getenv("POSTGRES_DATABASE")

        if not all([user, password, host, port, db]):
            print("❌ .env 파일에 DB 접속 정보(POSTGRES_...)가 부족합니다.")
            return

        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=require"

    # asyncpg 등 비동기 드라이버가 섞여있을 수 있으므로 기본 postgresql:// 로 변환
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        engine = sqlalchemy.create_engine(db_url)
        with engine.connect() as conn:
            # 나 자신(현재 세션)과 Aiven 내부 시스템 프로세스를 제외한, '내 계정'의 모든 연결(슬롯) 강제 종료
            query = sqlalchemy.text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = current_database() "
                "AND pid <> pg_backend_pid() "
                "AND usename = current_user;"
            )
            # SQLAlchemy 2.0+ 에서는 명시적 커밋 필요
            conn.execute(query)
            try:
                conn.commit()
            except Exception:
                pass
        print("✅ Aiven DB의 모든 좀비 커넥션(슬롯)이 성공적으로 강제 종료되었습니다!")
    except Exception as e:
        print(f"❌ DB 연결 종료 중 오류 발생: {e}")


if __name__ == "__main__":
    kill_aiven_connections()
