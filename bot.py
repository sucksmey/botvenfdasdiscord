# bot.py
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncpg
import config

# --- CORREÇÃO APLICADA AQUI ---
# Aponta para a biblioteca Opus que instalamos
discord.opus.load_opus('libopus.so.0')

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.invites = True
intents.voice_states = True

class IsrabuyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.pool = None

    async def setup_hook(self):
        try:
            self.pool = await asyncpg.create_pool(DATABASE_URL)
            print("Conexão com o banco de dados PostgreSQL estabelecida.")
        except Exception as e:
            print(f"Erro ao conectar com o banco de dados: {e}")
            return

        initial_extensions = [
            'cogs.database',
            'cogs.ai_assistant',
            'cogs.giveaway',
            'cogs.voice_manager'
        ]
        
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f'Cog {extension} carregada com sucesso.')
            except Exception as e:
                print(f'Erro ao carregar a cog {extension}: {e}')

        guild = discord.Object(id=config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self):
        print(f'Bot conectado como {self.user} (ID: {self.user.id})')
        print('------')

bot = IsrabuyBot()

async def main():
    async with bot:
        await bot.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
