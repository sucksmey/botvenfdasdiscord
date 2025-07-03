# main.py - VERSÃO FINAL CORRIGIDA

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import logging
from config import GUILD_ID

# Carrega o token do arquivo .env ou das variáveis de ambiente da Railway
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Configura o logging para ver o que está acontecendo no painel da Railway
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

    # O setup_hook é executado antes do bot se conectar
    async def setup_hook(self):
        # Carrega os cogs (módulos) da pasta /cogs
        logging.info("Carregando cogs...")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f"Cog '{filename[:-3]}' carregado com sucesso.")
                except Exception as e:
                    logging.error(f"Falha ao carregar o cog '{filename[:-3]}'. Erro: {e}")
        
        # Sincroniza os comandos com o Discord (Método Rápido para Guild Específica)
        logging.info(f"Sincronizando comandos para o servidor ID: {GUILD_ID}...")
        try:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logging.info(f"Sincronizados {len(synced)} comandos para o servidor.")
        except Exception as e:
            logging.error(f"Falha ao sincronizar comandos para o servidor: {e}")

    # on_ready é executado quando o bot está online e pronto
    async def on_ready(self):
        logging.info(f'Bot conectado como {self.user} (ID: {self.user.id})')
        logging.info('O bot está pronto e operacional.')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Vendas 24/7 | Israbuy"))

# Função principal para iniciar o bot
async def main():
    if not TOKEN:
        logging.critical("TOKEN do Bot não encontrado! Verifique as variáveis de ambiente na Railway.")
        return

    bot = IsrabuyBot()
    
    try:
        await bot.start(TOKEN)
    except discord.errors.LoginFailure:
        logging.critical("FALHA NO LOGIN. O token fornecido é inválido. Verifique a variável de ambiente na Railway.")
    except Exception as e:
        logging.critical(f"Erro inesperado ao iniciar o bot: {e}")

# Inicia o bot
if __name__ == "__main__":
    asyncio.run(main())
