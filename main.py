# main.py
import database
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import logging
from config import GUILD_ID
from cogs.vendas import SetupView
from cogs.cliente import CustomerAreaView, VipPurchaseView, StartReviewView

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class IsrabuyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.persistent_views_added = False

    async def setup_hook(self):
        await database.init_db()
        if not self.persistent_views_added:
            self.add_view(SetupView())
            self.add_view(CustomerAreaView())
            self.add_view(VipPurchaseView())
            # A StartReviewView não precisa ser persistente pois é gerada dinamicamente com um ID de transação
            logging.info("Views persistentes registradas.")
            self.persistent_views_added = True

        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f"Cog '{filename[:-3]}' carregado.")
                except Exception as e:
                    logging.error(f"Falha ao carregar o cog '{filename[:-3]}'. Erro: {e}")
        
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        logging.info(f"Sincronizados {len(synced)} comandos para o servidor.")

    async def on_ready(self):
        logging.info(f'Bot conectado como {self.user}')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Vendas 24/7 | Israbuy"))

async def main():
    if not TOKEN:
        logging.critical("TOKEN do Bot não encontrado!")
        return
    bot = IsrabuyBot()
    try:
        await bot.start(TOKEN)
    except Exception as e:
        logging.error(f"Erro fatal ao iniciar o bot: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
