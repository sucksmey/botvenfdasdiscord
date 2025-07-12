# cogs/status_manager.py
import discord
from discord.ext import commands, tasks
import itertools
import config

# --- Lista de Mensagens para o Status (Texto ATUALIZADO) ---
STATUS_MESSAGES = [
    "Desenvolvido por edos.",
    "Robux mais barato aqui!",
    "Dimas tá quase de graça aqui!",
    "Valorant Points e Muito Mais!",
    "Sem skin? Sem nada! Compra aqui!",
]

class StatusManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Cria um ciclo infinito com as mensagens de status
        self.status_cycle = itertools.cycle(STATUS_MESSAGES)
        self.change_status.start()

    def cog_unload(self):
        self.change_status.cancel()

    @tasks.loop(minutes=2)
    async def change_status(self):
        """
        Tarefa que roda a cada 2 minutos para alterar o status do bot.
        """
        # Pega a próxima mensagem da lista
        current_status = next(self.status_cycle)
        
        # Cria a atividade "Jogando..."
        activity = discord.Game(name=current_status)
        
        # Altera a presença do bot
        await self.bot.change_presence(activity=activity)

    @change_status.before_loop
    async def before_change_status(self):
        # Espera o bot estar 100% conectado antes de iniciar a tarefa
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(StatusManager(bot))
