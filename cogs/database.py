# cogs/database.py
from discord.ext import commands

class Database(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.setup_tables())

    async def setup_tables(self):
        await self.bot.wait_until_ready()
        async with self.bot.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS purchases (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        admin_id BIGINT,
                        product_name TEXT NOT NULL,
                        product_price NUMERIC(10, 2) NOT NULL,
                        purchase_date TIMESTAMPTZ DEFAULT current_timestamp,
                        is_vip_purchase BOOLEAN DEFAULT FALSE,
                        gamepass_link TEXT
                    );
                ''')
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS discount (
                        id INT PRIMARY KEY,
                        percentage NUMERIC(5, 2) NOT NULL,
                        apply_to_all BOOLEAN DEFAULT FALSE
                    );
                ''')
                # NOVA TABELA PARA A MENSAGEM DE PROPAGANDA
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS ad_message (
                        id INT PRIMARY KEY,
                        channel_id BIGINT NOT NULL,
                        message_id BIGINT NOT NULL,
                        current_index INT NOT NULL
                    );
                ''')
            print("Tabelas do banco de dados verificadas/criadas.")

async def setup(bot):
    await bot.add_cog(Database(bot))
