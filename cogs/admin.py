# cogs/admin.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
from config import *

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # NOVO: Comando para atendimento humano
    @app_commands.command(name="atender", description="[Admin] Assume o atendimento de um ticket, pausando a automação.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def atender(self, interaction: discord.Interaction):
        if interaction.channel.id in ONGOING_SALES_DATA:
            ONGOING_SALES_DATA[interaction.channel.id]['status'] = 'being_attended_by_human'
            await interaction.response.send_message(f"Olá! {interaction.user.mention} está assumindo o seu atendimento a partir de agora.")
        else:
            await interaction.response.send_message("Este não parece ser um ticket de venda ativo.", ephemeral=True)

    @app_commands.command(name="aprovar", description="[Admin] Aprova a compra, registra o log e finaliza o ticket.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def aprovar(self, interaction: discord.Interaction):
        # ... (código do /aprovar continua o mesmo)
        pass # Adicione o código do comando aprovar que já funcionava aqui

    @app_commands.command(name="fechar", description="[Admin] Fecha um ticket manualmente.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def fechar(self, interaction: discord.Interaction):
        # ... (código do /fechar continua o mesmo)
        pass # Adicione o código do comando fechar que já funcionava aqui

# Função obrigatória para o bot carregar este cog
async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
