# bot.py
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncpg
import config
# A importação da cogs.views não é mais necessária aqui se a view não for persistente
# from cogs.views import SalesPanelView, VIPPanelView, ClientPanelView, TutorialGamepassView

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
        # As views de setup não são mais necessárias aqui se o bot simplificado não as tiver
        # self.add_view(SalesPanelView(self))
        # self.add_view(VIPPanelView(self))
        # self.add_view(ClientPanelView(self))
        # self.add_view(TutorialGamepassView())

        try:
            self.pool = await asyncpg.create_pool(DATABASE_URL)
            print("Conexão com o banco de dados PostgreSQL estabelecida.")
        except Exception as e:
            print(f"Erro ao conectar com o banco de dados: {e}")
            return

        initial_extensions = [
            'cogs.database',
            # 'cogs.admin',
            # 'cogs.tickets',
            # 'cogs.advertising',
            'cogs.ai_assistant',
            # 'cogs.status_manager',
            # 'cogs.loyalty',
            'cogs.giveaway',
            'cogs.voice_manager' # Unifica toda a lógica de voz
            # 'cogs.tts_relay' foi removida
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
