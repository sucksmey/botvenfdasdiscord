# cogs/admin.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
import asyncio
from config import *
import database

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

    @app_commands.command(name="aprovar", description="[Admin] Aprova a compra e move o ticket para a categoria de entregues.")
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
        
        if not membro:
            await interaction.followup.send(f"Não foi possível encontrar o membro com ID {client_id}. Ele pode ter saído do servidor.", ephemeral=True)
            return

        # Salva a transação no banco de dados
        try:
            async with database.engine.connect() as conn:
                await conn.execute(
                    database.transactions.insert().values(
                        user_id=membro.id,
                        user_name=membro.name,
                        channel_id=channel.id,
                        product_name=ticket_data.get("item_name", "N/A"),
                        price=ticket_data.get("final_price", 0.0),
                        gamepass_link=ticket_data.get("gamepass_link"),
                        handler_admin_id=interaction.user.id,
                        delivery_admin_id=ROBUX_DELIVERY_USER_ID,
                        timestamp=datetime.utcnow(),
                        closed_at=datetime.utcnow()
                    )
                )
                await conn.commit()
            logging.info(f"Transação para o ticket {channel.id} salva no banco de dados.")
        except Exception as e:
            logging.error(f"Falha ao salvar a transação no banco de dados: {e}")
            await interaction.followup.send("⚠️ Ocorreu um erro ao salvar a transação no banco de dados. A compra foi aprovada, mas não registrada.", ephemeral=True)

        # Envia o log da compra
        produto = ticket_data.get("item_name", "N/A")
        log_channel = self.bot.get_channel(LOGS_COMPRAS_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(title="✅ Log de Compra", color=discord.Color.green(), timestamp=datetime.now(BR_TIMEZONE))
            log_embed.add_field(name="Cliente", value=f"{membro.mention} (`{membro.id}`)", inline=False)
            log_embed.add_field(name="Produto", value=produto, inline=True)
            log_embed.add_field(name="Valor", value=f"R$ {ticket_data.get('final_price', 0.0):.2f}", inline=True)
            log_embed.add_field(name="Atendente", value=interaction.user.mention, inline=False)
            log_embed.add_field(name="Ticket", value=channel.name, inline=False)
            if ticket_data.get('gamepass_link'):
                 log_embed.add_field(name="Link da Gamepass", value=ticket_data['gamepass_link'], inline=False)
            log_embed.set_thumbnail(url=membro.display_avatar.url)
            await log_channel.send(embed=log_embed)

        # Envia a mensagem final no ticket
        final_embed = discord.Embed(title="✅ Compra Finalizada!", description=f"Sua compra de **{produto}** foi entregue com sucesso! Este ticket foi arquivado para seu histórico.", color=discord.Color.green())
        final_embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
        await interaction.followup.send(embed=final_embed)
        
        # Lógica para mover e arquivar o canal
        entregues_category = interaction.guild.get_channel(CATEGORY_ENTREGUES_ID)
        if entregues_category:
            try:
                await channel.set_permissions(membro, send_messages=False, read_messages=True)
                await channel.edit(category=entregues_category, name=f"entregue-{membro.name.split('#')[0]}-{channel.id % 1000}")
            except Exception as e:
                logging.error(f"Falha ao mover/arquivar o canal {channel.id}: {e}")
                await interaction.channel.send("⚠️ Não consegui mover este canal para a categoria de entregues.")
        else:
            await interaction.channel.send(f"⚠️ Categoria de 'pedidos entregues' (ID: {CATEGORY_ENTREGUES_ID}) não encontrada. O canal não foi movido.")

        if channel.id in ONGOING_SALES_DATA:
            del ONGOING_SALES_DATA[channel.id]

    @app_commands.command(name="fechar", description="[Admin] Força o fechamento e exclusão de um ticket.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def fechar(self, interaction: discord.Interaction):
        channel = interaction.channel
        if "ticket-" not in channel.name and "entregar-" not in channel.name:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)
            return
        
        if channel.id in ONGOING_SALES_DATA:
            del ONGOING_SALES_DATA[channel.id]

        await interaction.response.send_message("Este canal será **deletado permanentemente** em 5 segundos...", ephemeral=True)
        await asyncio.sleep(5)
        await channel.delete(reason="Fechado manualmente por um admin.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
