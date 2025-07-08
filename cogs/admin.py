# cogs/admin.py

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import logging
import asyncio
from config import *
import database
from cogs.cliente import CustomerAreaView # <-- A LINHA QUE FALTAVA FOI ADICIONADA AQUI

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_loop.start()

    def cog_unload(self):
        self.cleanup_loop.cancel()

    @tasks.loop(hours=6)
    async def cleanup_loop(self):
        logging.info("Executando tarefa de limpeza de tickets arquivados...")
        days_to_keep = 4
        cleanup_threshold = datetime.utcnow() - timedelta(days=days_to_keep)
        
        try:
            async with database.engine.connect() as conn:
                query = database.transactions.select().where(
                    database.transactions.c.closed_at <= cleanup_threshold,
                    database.transactions.c.is_archived == False
                )
                old_tickets_to_delete = (await conn.execute(query)).fetchall()
                
                transcript_channel = self.bot.get_channel(TRANSCRIPT_CHANNEL_ID)

                for ticket in old_tickets_to_delete:
                    channel_id = ticket.channel_id
                    if not channel_id:
                        continue
                        
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.delete(reason="Limpeza automática de ticket antigo.")
                            logging.info(f"Canal de ticket {channel_id} deletado com sucesso.")
                            
                            if transcript_channel:
                                await transcript_channel.send(f"🗑️ O ticket `entregue-{ticket.user_name}` (ID: {channel_id}) foi deletado automaticamente após {days_to_keep} dias.")

                        except discord.errors.NotFound:
                            logging.warning(f"Não foi possível deletar o canal {channel_id}, pois ele não foi encontrado.")
                        except Exception as e:
                            logging.error(f"Erro ao deletar o canal {channel_id}: {e}")
                    
                    update_query = database.transactions.update().where(database.transactions.c.id == ticket.id).values(is_archived=True)
                    await conn.execute(update_query)

                await conn.commit()
            logging.info("Tarefa de limpeza finalizada.")
        except Exception as e:
            logging.error(f"Erro na tarefa de limpeza (cleanup_loop): {e}")

    @cleanup_loop.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="atender", description="[Admin] Libera o chat para o admin e renomeia o canal.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def atender(self, interaction: discord.Interaction):
        channel = interaction.channel
        admin_user = interaction.user
        
        async def perform_attend_logic(is_memory_ticket=True):
            try:
                await channel.set_permissions(admin_user, send_messages=True)
                await channel.edit(name=f"atendido-{admin_user.name.split('#')[0]}")
                response_message = f"Olá! {admin_user.mention} está assumindo o seu atendimento a partir de agora."
                if not interaction.response.is_done():
                    await interaction.response.send_message(response_message, allowed_mentions=discord.AllowedMentions(users=True))
                else:
                    await interaction.followup.send(response_message, allowed_mentions=discord.AllowedMentions(users=True))
                if channel.id in ONGOING_SALES_DATA:
                    ONGOING_SALES_DATA[channel.id]['handler_admin_id'] = admin_user.id
            except Exception as e:
                logging.error(f"Falha ao atender o ticket {channel.id}: {e}")
                if not interaction.response.is_done(): await interaction.response.send_message("Ocorreu um erro ao tentar atender este ticket.", ephemeral=True)
                else: await interaction.followup.send("Ocorreu um erro ao tentar atender este ticket.", ephemeral=True)

        if channel.id in ONGOING_SALES_DATA:
            await perform_attend_logic(is_memory_ticket=True)
            return

        if channel.topic and "ID: " in channel.topic:
            await interaction.response.send_message("Recuperando ticket da memória... Atendendo.", ephemeral=True)
            try:
                client_id = int(channel.topic.split("ID: ")[1])
                ONGOING_SALES_DATA[channel.id] = {'client_id': client_id, 'status': 're-attended'}
                await perform_attend_logic(is_memory_ticket=False)
            except (IndexError, TypeError, ValueError) as e:
                logging.error(f"Falha ao recuperar ID do cliente do tópico do canal {channel.id}: {e}")
                await interaction.followup.send("Não consegui recuperar as informações deste ticket pelo tópico do canal.", ephemeral=True)
            return

        await interaction.response.send_message("Este comando só pode ser usado em um ticket de venda ativo.", ephemeral=True)

    @app_commands.command(name="aprovar", description="[Admin] Aprova a compra e envia o pedido de avaliação.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def aprovar(self, interaction: discord.Interaction):
        channel = interaction.channel
        ticket_data = ONGOING_SALES_DATA.get(channel.id)

        if not ticket_data:
            await interaction.response.send_message("Este não parece ser um ticket de venda ativo. Use /atender primeiro.", ephemeral=True)
            return

        await interaction.response.defer()

        client_id = ticket_data.get("client_id")
        membro = interaction.guild.get_member(client_id)
        
        if not membro:
            await interaction.followup.send(f"Não foi possível encontrar o membro com ID {client_id}.", ephemeral=True)
            return
        
        new_transaction_id = None
        try:
            async with database.engine.connect() as conn:
                result = await conn.execute(
                    database.transactions.insert().values(
                        user_id=membro.id, user_name=membro.name, channel_id=channel.id,
                        product_name=ticket_data.get("item_name", "N/A"),
                        price=ticket_data.get("final_price", 0.0),
                        gamepass_link=ticket_data.get("gamepass_link"),
                        handler_admin_id=interaction.user.id,
                        delivery_admin_id=ROBUX_DELIVERY_USER_ID,
                        timestamp=datetime.utcnow(), closed_at=datetime.utcnow()
                    ).returning(database.transactions.c.id)
                )
                new_transaction_id = result.scalar_one()
                await conn.commit()
            logging.info(f"Transação ID {new_transaction_id} para o ticket {channel.id} salva no banco de dados.")
        except Exception as e:
            logging.error(f"Falha ao salvar a transação no banco de dados: {e}")
            await interaction.followup.send("⚠️ Ocorreu um erro ao salvar a transação no banco de dados.", ephemeral=True)

        produto = ticket_data.get("item_name", "N/A")
        log_channel = self.bot.get_channel(LOGS_COMPRAS_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(title="✅ Log de Compra", color=discord.Color.green(), timestamp=datetime.now(BR_TIMEZONE))
            log_embed.add_field(name="Cliente", value=f"{membro.mention} (`{membro.id}`)", inline=False)
            log_embed.add_field(name="Produto", value=produto, inline=True)
            log_embed.add_field(name="Valor", value=f"R$ {ticket_data.get('final_price', 0.0):.2f}", inline=True)
            log_embed.add_field(name="Atendente", value=interaction.user.mention, inline=False)
            if ticket_data.get('gamepass_link'): log_embed.add_field(name="Link da Gamepass", value=ticket_data['gamepass_link'], inline=False)
            log_embed.set_thumbnail(url=membro.display_avatar.url)
            await log_channel.send(embed=log_embed)

        final_embed = discord.Embed(title="✅ Compra Finalizada!", description=f"Sua compra de **{produto}** foi entregue com sucesso! Este ticket foi arquivado para seu histórico.", color=discord.Color.green())
        await interaction.followup.send(embed=final_embed)
        
        try:
            dm_embed = discord.Embed(title="❤️ Obrigado pela sua compra!", description=f"Olá {membro.name}! A sua compra de **{produto}** foi concluída com sucesso.\n\nAgradecemos a sua preferência! Clique no botão abaixo para ver seu histórico de compras conosco.", color=ROSE_COLOR)
            dm_embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
            await membro.send(embed=dm_embed, view=CustomerAreaView())
        except Exception as e:
            logging.warning(f"Não foi possível enviar a DM para o usuário {membro.name}: {e}")

        entregues_category = interaction.guild.get_channel(CATEGORY_ENTREGUES_ID)
        if entregues_category:
            try:
                await channel.set_permissions(membro, send_messages=False, read_messages=True)
                await channel.edit(category=entregues_category, name=f"entregue-{membro.name.split('#')[0]}-{channel.id % 1000}")
            except Exception as e:
                logging.error(f"Falha ao mover/arquivar o canal {channel.id}: {e}")
        else:
            await interaction.channel.send(f"⚠️ Categoria de 'pedidos entregues' não encontrada.")

        if new_transaction_id:
            review_embed = discord.Embed(title="⭐ Avalie sua Compra!", description=f"Obrigado pela sua compra, {membro.mention}! Sua opinião é muito importante para nós. Por favor, deixe uma nota de 1 a 10 e, se quiser, um comentário sobre sua experiência.", color=ROSE_COLOR)
            try:
                await channel.send(embed=review_embed, view=ReviewView(transaction_id=new_transaction_id))
            except Exception as e:
                logging.error(f"Não foi possível enviar o pedido de avaliação no canal {channel.id}: {e}")

        if channel.id in ONGOING_SALES_DATA:
            del ONGOING_SALES_DATA[channel.id]
            
    @app_commands.command(name="aprovarvip", description="[Admin] Aprova a compra de VIP para um membro.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    @app_commands.describe(membro="O membro que comprou o VIP.")
    async def aprovar_vip(self, interaction: discord.Interaction, membro: discord.Member):
        await interaction.response.defer(ephemeral=True)
        vip_role = interaction.guild.get_role(VIP_ROLE_ID)
        if not vip_role:
            await interaction.followup.send("Erro: O cargo VIP não foi encontrado no servidor.", ephemeral=True)
            return
        try:
            await membro.add_roles(vip_role, reason=f"Compra de VIP aprovada por {interaction.user.name}")
            async with database.engine.connect() as conn:
                await conn.execute(database.transactions.insert().values(user_id=membro.id, user_name=membro.name, channel_id=interaction.channel.id, product_name="Assinatura VIP", price=VIP_PRICE, handler_admin_id=interaction.user.id, timestamp=datetime.utcnow(), closed_at=datetime.utcnow()))
                await conn.commit()
            success_embed = discord.Embed(title="💎 VIP Ativado!", description=f"Parabéns {membro.mention}, você agora é um membro VIP! Obrigado pela sua compra.", color=discord.Color.gold())
            await interaction.channel.send(embed=success_embed)
            await interaction.followup.send("Assinatura VIP aprovada e registrada com sucesso!", ephemeral=True)
        except Exception as e:
            logging.error(f"Erro ao aprovar VIP para {membro.name}: {e}")
            await interaction.followup.send(f"Ocorreu um erro ao tentar aprovar o VIP: {e}", ephemeral=True)

    @app_commands.command(name="fechar", description="[Admin] Força o fechamento e exclusão de um ticket.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def fechar(self, interaction: discord.Interaction):
        channel = interaction.channel
        if "ticket-" not in channel.name and "entregar-" not in channel.name and "atendido-" not in channel.name:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)
            return
        
        if channel.id in ONGOING_SALES_DATA:
            del ONGOING_SALES_DATA[channel.id]
        await interaction.response.send_message("Este canal será **deletado permanentemente** em 5 segundos...", ephemeral=True)
        await asyncio.sleep(5)
        await channel.delete(reason="Fechado manualmente por um admin.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
