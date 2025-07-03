# cogs/admin.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
import asyncio
from config import *

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
        channel = interaction.channel
        ticket_data = ONGOING_SALES_DATA.get(channel.id)

        if not ticket_data:
            await interaction.response.send_message("Este não parece ser um ticket de venda ativo.", ephemeral=True)
            return

        await interaction.response.defer()

        client_id = ticket_data.get("client_id")
        membro = interaction.guild.get_member(client_id)
        produto = ticket_data.get("item_name", "N/A")
        valor = ticket_data.get("final_price", 0.0)

        if not membro:
            await interaction.followup.send(f"Não foi possível encontrar o membro com ID {client_id}. Ele pode ter saído do servidor.", ephemeral=True)
            return

        final_embed = discord.Embed(title="✅ Compra Finalizada!", description=f"Sua compra de **{produto}** foi entregue com sucesso!\n\nObrigado pela preferência, {membro.mention}! Este ticket será fechado em 15 segundos.", color=discord.Color.green())
        final_embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
        await interaction.followup.send(embed=final_embed)

        log_channel = self.bot.get_channel(LOGS_COMPRAS_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(title="✅ Log de Compra", color=discord.Color.green(), timestamp=datetime.now(BR_TIMEZONE))
            log_embed.add_field(name="Cliente", value=f"{membro.mention} (`{membro.id}`)", inline=False)
            log_embed.add_field(name="Produto", value=produto, inline=True)
            log_embed.add_field(name="Valor", value=f"R$ {valor:.2f}", inline=True)
            log_embed.add_field(name="Atendente", value=interaction.user.mention, inline=False)
            log_embed.add_field(name="Ticket", value=channel.name, inline=False)
            log_embed.set_thumbnail(url=membro.display_avatar.url)
            await log_channel.send(embed=log_embed)

        if channel.id in ONGOING_SALES_DATA:
            del ONGOING_SALES_DATA[channel.id]
        
        await asyncio.sleep(15)
        await channel.delete(reason="Ticket aprovado e concluído.")


    @app_commands.command(name="fechar", description="[Admin] Fecha um ticket manualmente.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def fechar(self, interaction: discord.Interaction):
        channel = interaction.channel
        if "ticket-" not in channel.name and "entregar-" not in channel.name:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)
            return
        
        if channel.id in ONGOING_SALES_DATA:
            del ONGOING_SALES_DATA[channel.id]

        await interaction.response.send_message("O canal será deletado em 5 segundos...", ephemeral=True)
        await asyncio.sleep(5)
        await channel.delete(reason="Fechado manualmente por um admin.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
