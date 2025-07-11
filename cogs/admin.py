# cogs/admin.py

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import logging
import asyncio
import math
from config import *
import database
from sqlalchemy import insert, select, update
from cogs.cliente import CustomerAreaView

# Grupo de comandos para cupons
cupom_group = app_commands.Group(name="cupom", description="Gerenciamento de cupons de desconto.")

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_loop.start()

    def cog_unload(self):
        self.cleanup_loop.cancel()

    @cupom_group.command(name="criar", description="Cria um novo cupom de desconto.")
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    @app_commands.describe(codigo="O código do cupom (ex: BEMVINDO10)", desconto="A porcentagem de desconto (ex: 10 para 10%)")
    async def criar_cupom(self, interaction: discord.Interaction, codigo: str, desconto: int):
        await interaction.response.defer(ephemeral=True)
        codigo = codigo.upper()

        if not (0 < desconto <= 100):
            await interaction.followup.send("A porcentagem de desconto deve ser entre 1 e 100.", ephemeral=True)
            return

        try:
            async with database.engine.connect() as conn:
                query = select(database.coupons).where(database.coupons.c.code == codigo)
                exists = (await conn.execute(query)).first()
                if exists:
                    await interaction.followup.send(f"❌ O cupom `{codigo}` já existe.", ephemeral=True)
                    return
                
                insert_query = insert(database.coupons).values(code=codigo, discount_percentage=desconto)
                await conn.execute(insert_query)
                await conn.commit()
            
            await interaction.followup.send(f"✅ Cupom `{codigo}` de **{desconto}% de desconto** criado com sucesso!", ephemeral=True)
        except Exception as e:
            logging.error(f"Erro ao criar cupom: {e}")
            await interaction.followup.send("Ocorreu um erro ao tentar criar o cupom.", ephemeral=True)

    @cupom_group.command(name="listar", description="Lista todos os cupons ativos.")
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def listar_cupons(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            async with database.engine.connect() as conn:
                query = select(database.coupons).where(database.coupons.c.is_active == True)
                active_coupons = (await conn.execute(query)).fetchall()

            if not active_coupons:
                await interaction.followup.send("Não há nenhum cupom ativo no momento.", ephemeral=True)
                return
            
            embed = discord.Embed(title="🎟️ Cupons de Desconto Ativos", color=ROSE_COLOR)
            description = ""
            for coupon in active_coupons:
                description += f"**Código:** `{coupon.code}` - **Desconto:** {coupon.discount_percentage}%\n"
            embed.description = description
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logging.error(f"Erro ao listar cupons: {e}")
            await interaction.followup.send("Ocorreu um erro ao tentar listar os cupons.", ephemeral=True)

    @cupom_group.command(name="desativar", description="Desativa um cupom para que não possa mais ser usado.")
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    @app_commands.describe(codigo="O código do cupom a ser desativado.")
    async def desativar_cupom(self, interaction: discord.Interaction, codigo: str):
        await interaction.response.defer(ephemeral=True)
        codigo = codigo.upper()
        try:
            async with database.engine.connect() as conn:
                query = update(database.coupons).where(database.coupons.c.code == codigo).values(is_active=False)
                result = await conn.execute(query)
                await conn.commit()

            if result.rowcount > 0:
                await interaction.followup.send(f"✅ O cupom `{codigo}` foi desativado com sucesso.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Não encontrei um cupom ativo com o código `{codigo}`.", ephemeral=True)

        except Exception as e:
            logging.error(f"Erro ao desativar cupom: {e}")
            await interaction.followup.send("Ocorreu um erro ao tentar desativar o cupom.", ephemeral=True)

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
                    if not channel_id: continue
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.delete(reason="Limpeza automática de ticket antigo.")
                            if transcript_channel:
                                await transcript_channel.send(f"🗑️ O ticket `entregue-{ticket.user_name}` (ID: {channel_id}) foi deletado automaticamente.")
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

    @app_commands.command(name="pix", description="[Admin] Envia as informações de pagamento Pix no canal.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def pix(self, interaction: discord.Interaction):
        pix_embed = discord.Embed(title="Pagamento via PIX", description="Use o QR Code acima ou a chave PIX (E-mail) enviada abaixo para efetuar o pagamento.", color=ROSE_COLOR)
        pix_embed.set_footer(text="Após pagar, por favor, envie o comprovante neste chat.")
        pix_embed.set_image(url=QR_CODE_URL)
        await interaction.response.send_message(embed=pix_embed)
        await interaction.channel.send(PIX_KEY_MANUAL)

    @app_commands.command(name="tutorialgamepass", description="[Admin] Envia o tutorial e o cálculo da Game Pass.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    @app_commands.describe(robux="A quantidade de Robux que o cliente irá receber.")
    async def tutorial_gamepass(self, interaction: discord.Interaction, robux: int):
        if robux <= 0:
            await interaction.response.send_message("A quantidade de Robux deve ser positiva.", ephemeral=True)
            return
        
        gamepass_value = math.ceil(robux / 0.7)
        embed = discord.Embed(title="📄 Tutorial e Cálculo da Game Pass", description=f"Para receber **{robux} Robux**, é preciso criar uma Game Pass no valor de **{gamepass_value} Robux**.\n\nAssista a este vídeo tutorial para aprender como fazer:\n{TUTORIAL_GAMEPASS_URL}\n\n**Importante:** Ao criar, **NÃO** marque a opção de preços regionais.", color=ROSE_COLOR)
        await interaction.response.send_message(embed=embed)

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
                response_message = f"Olá! {admin_user.mention} está assumindo o seu atendimento."
                if not interaction.response.is_done():
                    await interaction.response.send_message(response_message, allowed_mentions=discord.AllowedMentions(users=True))
                else:
                    await interaction.followup.send(response_message, allowed_mentions=discord.AllowedMentions(users=True))
                if channel.id in ONGOING_SALES_DATA:
                    ONGOING_SALES_DATA[channel.id]['handler_admin_id'] = admin_user.id
            except Exception as e:
                logging.error(f"Falha ao atender o ticket {channel.id}: {e}")
                if not interaction.response.is_done(): await interaction.response.send_message("Ocorreu um erro.", ephemeral=True)
                else: await interaction.followup.send("Ocorreu um erro.", ephemeral=True)

        if channel.id in ONGOING_SALES_DATA:
            await perform_attend_logic(is_memory_ticket=True)
            return

        if channel.topic and "ID: " in channel.topic:
            await interaction.response.send_message("Recuperando ticket da memória... Atendendo.", ephemeral=True)
            try:
                client_id = int(channel.topic.split("ID: ")[1].strip())
                ONGOING_SALES_DATA[channel.id] = {'client_id': client_id, 'status': 're-attended'}
                await perform_attend_logic(is_memory_ticket=False)
            except (IndexError, TypeError, ValueError) as e:
                logging.error(f"Falha ao recuperar ID do cliente do tópico: {e}")
                await interaction.followup.send("Não consegui recuperar as informações deste ticket.", ephemeral=True)
            return
        await interaction.response.send_message("Este comando só pode ser usado em um ticket de venda ativo.", ephemeral=True)

    @app_commands.command(name="aprovar", description="[Admin] Aprova a compra e move o ticket para a categoria de entregues.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    @app_commands.describe(produto="[Opcional] Nome do produto, se o bot esqueceu.", valor="[Opcional] Valor da compra. Ex: 4.50 ou 4,50")
    async def aprovar(self, interaction: discord.Interaction, produto: str = None, valor: str = None):
        await interaction.response.defer()
        channel = interaction.channel
        ticket_data = ONGOING_SALES_DATA.get(channel.id)
        
        if not ticket_data:
            if channel.topic and "ID: " in channel.topic:
                try:
                    client_id = int(channel.topic.split("ID: ")[1].strip())
                    if produto and valor is not None:
                        try:
                            corrected_valor = float(valor.replace(',', '.'))
                            ticket_data = {'client_id': client_id, 'item_name': produto, 'final_price': corrected_valor}
                        except ValueError:
                            await interaction.followup.send("⚠️ O valor manual que você inseriu não é um número válido.", ephemeral=True); return
                    else:
                        await interaction.followup.send("⚠️ O bot esqueceu os detalhes. Use `/aprovar` com os campos `produto` e `valor`.", ephemeral=True); return
                except (IndexError, ValueError):
                     await interaction.followup.send("❌ Não foi possível recuperar o cliente deste ticket.", ephemeral=True); return
            else:
                await interaction.followup.send("❌ Não é um ticket válido.", ephemeral=True); return
        
        client_id = ticket_data.get("client_id")
        membro = interaction.guild.get_member(client_id)
        if not membro:
            await interaction.followup.send(f"Não foi possível encontrar o membro com ID {client_id}.", ephemeral=True); return
        
        final_product_name = ticket_data.get("item_name", "N/A")
        final_price = ticket_data.get("final_price", 0.0)
        
        try:
            async with database.engine.connect() as conn:
                await conn.execute(database.transactions.insert().values(user_id=membro.id, user_name=membro.name, channel_id=channel.id, product_name=final_product_name, price=final_price, gamepass_link=ticket_data.get("gamepass_link"), handler_admin_id=interaction.user.id, delivery_admin_id=ROBUX_DELIVERY_USER_ID, timestamp=datetime.utcnow(), closed_at=datetime.utcnow()))
                await conn.commit()
            logging.info(f"Transação salva no banco de dados.")
        except Exception as e:
            logging.error(f"Falha ao salvar a transação no banco de dados: {e}")
            await interaction.followup.send("⚠️ Erro ao salvar a transação no banco de dados.", ephemeral=True); return

        log_channel = self.bot.get_channel(LOGS_COMPRAS_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(title="✅ Log de Compra", color=discord.Color.green(), timestamp=datetime.now(BR_TIMEZONE))
            log_embed.add_field(name="Cliente", value=f"{membro.mention} (`{membro.id}`)", inline=False)
            log_embed.add_field(name="Produto", value=final_product_name, inline=True)
            log_embed.add_field(name="Valor", value=f"R$ {final_price:.2f}", inline=True)
            log_embed.add_field(name="Atendente", value=interaction.user.mention, inline=False)
            if ticket_data.get('gamepass_link'): log_embed.add_field(name="Link da Gamepass", value=ticket_data['gamepass_link'], inline=False)
            log_embed.set_thumbnail(url=membro.display_avatar.url)
            await log_channel.send(embed=log_embed)

        try:
            dm_embed = discord.Embed(title="❤️ Obrigado pela sua compra!", description=f"Sua compra de **{final_product_name}** foi concluída.\n\nAgradecemos a preferência! Clique abaixo para ver seu histórico.", color=ROSE_COLOR)
            dm_embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
            await membro.send(embed=dm_embed, view=CustomerAreaView())
        except Exception as e:
            logging.warning(f"Não foi possível enviar a DM para {membro.name}: {e}")

        final_embed = discord.Embed(title="✅ Compra Finalizada!", description=f"Sua compra de **{final_product_name}** foi entregue! Este ticket foi arquivado.", color=discord.Color.green())
        await interaction.followup.send(embed=final_embed)

        entregues_category = interaction.guild.get_channel(CATEGORY_ENTREGUES_ID)
        if entregues_category:
            try:
                await channel.set_permissions(membro, send_messages=True, read_messages=True)
                await channel.edit(category=entregues_category, name=f"entregue-{membro.name.split('#')[0]}-{channel.id % 1000}")
            except Exception as e:
                logging.error(f"Falha ao mover/arquivar o canal {channel.id}: {e}")
        
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
            await interaction.followup.send("Erro: O cargo VIP não foi encontrado.", ephemeral=True); return
        try:
            await membro.add_roles(vip_role, reason=f"Compra de VIP aprovada por {interaction.user.name}")
            async with database.engine.connect() as conn:
                await conn.execute(database.transactions.insert().values(user_id=membro.id, user_name=membro.name, channel_id=interaction.channel.id, product_name="Assinatura VIP", price=VIP_PRICE, handler_admin_id=interaction.user.id, timestamp=datetime.utcnow(), closed_at=datetime.utcnow()))
                await conn.commit()
            success_embed = discord.Embed(title="💎 VIP Ativado!", description=f"Parabéns {membro.mention}, você agora é um membro VIP!", color=discord.Color.gold())
            await interaction.channel.send(embed=success_embed)
            await interaction.followup.send("Assinatura VIP aprovada e registrada!", ephemeral=True)
        except Exception as e:
            logging.error(f"Erro ao aprovar VIP para {membro.name}: {e}")
            await interaction.followup.send(f"Ocorreu um erro ao tentar aprovar o VIP.", ephemeral=True)

    @app_commands.command(name="fechar", description="[Admin] Força o fechamento e exclusão de um ticket.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def fechar(self, interaction: discord.Interaction):
        channel = interaction.channel
        if "ticket-" not in channel.name and "entregar-" not in channel.name and "atendido-" not in channel.name:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True); return
        
        if channel.id in ONGOING_SALES_DATA:
            del ONGOING_SALES_DATA[channel.id]
        await interaction.response.send_message("Este canal será **deletado permanentemente** em 5 segundos...", ephemeral=True)
        await asyncio.sleep(5)
        await channel.delete(reason="Fechado manualmente por um admin.")

    @app_commands.command(name="sync", description="[Admin] Força a sincronização dos comandos com o Discord.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.send_message("Sincronizando comandos...", ephemeral=True)
        try:
            synced = await self.bot.tree.sync(guild=discord.Object(id=GUILD_ID))
            await interaction.followup.send(f"Sincronizados {len(synced)} comandos com este servidor.", ephemeral=True)
            logging.info(f"Sincronização manual forçada por {interaction.user}. Sincronizados {len(synced)} comandos.")
        except Exception as e:
            logging.error(f"Falha na sincronização manual: {e}")
            await interaction.followup.send(f"Falha ao sincronizar: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    bot.tree.add_command(cupom_group, guild=discord.Object(id=GUILD_ID))
    await bot.add_cog(Admin(bot))
