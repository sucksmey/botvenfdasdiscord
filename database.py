# database.py
import os
import logging
from sqlalchemy import (Table, Column, Integer, String, Float, DateTime, BigInteger, Boolean, MetaData)
from sqlalchemy.ext.asyncio import create_async_engine
from datetime import datetime

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não foi encontrada!")

engine = create_async_engine(DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1))
metadata = MetaData()

transactions = Table(
    'transactions', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', BigInteger, nullable=False),
    Column('user_name', String(100)),
    Column('channel_id', BigInteger),
    Column('product_name', String(255), nullable=False),
    Column('price', Float, nullable=False),
    Column('gamepass_link', String(255), nullable=True),
    Column('review_rating', Integer, nullable=True),
    Column('review_text', String(1024), nullable=True),
    Column('handler_admin_id', BigInteger, nullable=True),
    Column('delivery_admin_id', BigInteger, nullable=True),
    Column('payment_method', String(50), default='PIX'),
    Column('timestamp', DateTime, default=datetime.utcnow),
    Column('closed_at', DateTime, nullable=True),
    Column('is_archived', Boolean, default=False, nullable=False)
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    logging.info("Tabelas do banco de dados verificadas e prontas.")
