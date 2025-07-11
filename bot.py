# bot.py
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncpg
import config

# Importa as views que precisam ser persistentes
from cogs.views import SalesPanelView, VIPPanelView, ClientPanelView, TutorialGamepassView

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class IsrabuyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.pool = None

    async def setup_hook(self):
        # Adiciona as Views persistentes ANTES de conectar
        self.add_view(SalesPanelView(self))
        self.add_view(VIPPanelView(self))
        self.add_view(ClientPanelView(self))
        self.add_view(TutorialGamepassView()) # Esta não precisa do bot, então não passamos

        try:
            self.pool = await asyncpg.create_pool(DATABASE_URL)
            print("Conexão com o banco de dados PostgreSQL estabelecida.")
        except Exception as e:
            print(f"Erro ao conectar com o banco de dados: {e}")
            return

        initial_extensions = [
            'cogs.database',
            'cogs.admin',
            'cogs.tickets',
            'cogs.helpers',
            # As cogs de views e advertising podem ser carregadas se necessário
            # 'cogs.views', 
            # 'cogs.advertising' 
        ]
        
        # Carregamos as cogs que contêm comandos e listeners
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
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
