import sqlalchemy as sa
from studify.db.session import engine
from studify.db.models import Base

def reset():
    print("Dropping all tables...")
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(sa.text('DROP TABLE IF EXISTS alembic_version'))
    print("Done!")

if __name__ == "__main__":
    reset()
