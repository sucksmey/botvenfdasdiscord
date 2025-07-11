# bot.py
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncpg
import config

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Define as intenções do bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class IsrabuyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.pool = None

    async def setup_hook(self):
        # Conecta ao banco de dados
        try:
            self.pool = await asyncpg.create_pool(DATABASE_URL)
            print("Conexão com o banco de dados PostgreSQL estabelecida.")
        except Exception as e:
            print(f"Erro ao conectar com o banco de dados: {e}")
            # Se não conectar, o bot não deve continuar.
            # Você pode querer um sistema de retry aqui.
            return

        # Carrega as cogs
        initial_extensions = [
            'cogs.database',
            'cogs.admin',
            'cogs.tickets'
        ]
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f'Cog {extension} carregada com sucesso.')
            except Exception as e:
                print(f'Erro ao carregar a cog {extension}: {e}')

        # Sincroniza os comandos com o Discord
        guild = discord.Object(id=config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self):
        print(f'Bot conectado como {self.user} (ID: {self.user.id})')
        print('------')

bot = IsrabuyBot()

async def main():
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
