# database.py
import os
import logging
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Float, DateTime, BigInteger, Boolean, ForeignKey
)
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from datetime import datetime

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não foi encontrada nas variáveis de ambiente.")

async_db_url = make_url(DATABASE_URL).render_as_string(hide_password=False).replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(async_db_url)
metadata = MetaData()

# Tabela de transações (compras)
transactions = Table(
    'transactions', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', BigInteger, nullable=False),
    Column('user_name', String(100)),
    Column('channel_id', BigInteger, nullable=True),
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

# NOVA TABELA: Cupons de desconto
coupons = Table(
    'coupons', metadata,
    Column('id', Integer, primary_key=True),
    Column('code', String(100), unique=True, nullable=False),
    Column('discount_percentage', Integer, nullable=False),
    Column('is_active', Boolean, default=True, nullable=False),
    Column('created_at', DateTime, default=datetime.utcnow)
)

# NOVA TABELA: Rastreia quem usou qual cupom
used_coupons = Table(
    'used_coupons', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', BigInteger, nullable=False),
    Column('coupon_id', Integer, ForeignKey('coupons.id'), nullable=False),
    Column('transaction_id', Integer, ForeignKey('transactions.id'), nullable=False),
    Column('used_at', DateTime, default=datetime.utcnow)
)


async def init_db():
    async with engine.begin() as conn:
        logging.info("Verificando e criando tabelas do banco de dados, se necessário...")
        await conn.run_sync(metadata.create_all)
        logging.info("Tabelas prontas.")
