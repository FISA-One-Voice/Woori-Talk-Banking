from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)
inspector = inspect(engine)

columns = inspector.get_columns("users")
for col in columns:
    if col['name'] == 'embedding_vector':
        print(f"Column: {col['name']}")
        print(f"Type: {col['type']}")
        print(f"Nullable: {col['nullable']}")
        print(f"Default: {col['default']}")
