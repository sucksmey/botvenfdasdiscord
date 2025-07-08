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
from cogs.cliente import CustomerAreaView # Importa a nova view do cliente

# Carrega o token do arquivo .env ou das variáveis de ambiente da Railway
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Configura o logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# Define as intenções (permissões) que o bot precisa
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Cria a classe principal do bot
class IsrabuyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.persistent_views_added = False

    async def setup_hook(self):
        # Inicializa a conexão com o banco de dados e cria as tabelas
        await database.init_db()

        # Adiciona as views persistentes ANTES de conectar
        if not self.persistent_views_added:
            self.add_view(SetupView())
            self.add_view(CustomerAreaView()) # Registra o painel do cliente
            self.persistent_views_added = True
            logging.info("Views persistentes registradas.")

        # Carrega os cogs (módulos) da pasta /cogs
        logging.info("Carregando cogs...")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f"Cog '{filename[:-3]}' carregado com sucesso.")
                except Exception as e:
                    logging.error(f"Falha ao carregar o cog '{filename[:-3]}'. Erro: {e}")
        
        # Sincroniza os comandos com o Discord
        logging.info(f"Sincronizando comandos para o servidor ID: {GUILD_ID}...")
        try:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logging.info(f"Sincronizados {len(synced)} comandos para o servidor.")
        except Exception as e:
            logging.error(f"Falha ao sincronizar comandos para o servidor: {e}")

    async def on_ready(self):
        logging.info(f'Bot conectado como {self.user} (ID: {self.user.id})')
        logging.info('O bot está pronto e operacional.')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Vendas 24/7 | Israbuy"))

async def main():
    if not TOKEN:
        logging.critical("TOKEN do Bot não encontrado!")
        return
    bot = IsrabuyBot()
    try:
        await bot.start(TOKEN)
    except discord.errors.LoginFailure:
        logging.critical("FALHA NO LOGIN. O token fornecido é inválido.")
    except Exception as e:
        logging.critical(f"Erro inesperado ao iniciar o bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
