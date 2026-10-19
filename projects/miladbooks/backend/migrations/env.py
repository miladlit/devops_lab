import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import URL, create_engine, pool

config = context.config
fileConfig(config.config_file_name)
url = URL.create(
    "postgresql+psycopg2", username=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"], host=os.environ["DB_HOST"],
    database=os.environ["DB_NAME"],
)

if context.is_offline_mode():
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
