# cogs/admin.py
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import config
import io
import asyncio
import traceback
import pytz
from .views import SalesPanelView, VIPPanelView, ClientPanelView, ReviewView, BackfillConfirmView

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cleanup_task.start()

    def cog_unload(self):
        self.cleanup_task.cancel()

    async def handle_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Ocorreu um erro no comando '{interaction.command.name}':")
        traceback.print_exc()
        error_message = f"😕 Ocorreu um erro inesperado.\n**Detalhe:** `{str(error)}`"
        if interaction.response.is_done():
            await interaction.followup.send(error_message, ephemeral=True)
        else:
            await interaction.response.send_message(error_message, ephemeral=True)

    @app_commands.command(name="setupvendas", description="Posta o painel de vendas no canal.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setup_vendas(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            embed = discord.Embed(
                title="✨ Bem-vindo(a) à Israbuy!",
                description="Pronto para a melhor experiência de compra?\n\nSelecione um jogo ou serviço no menu abaixo para abrir um ticket ou clique no botão para ver todos os preços.",
                color=0xFF69B4
            )
            view = SalesPanelView(self.bot)
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await self.handle_error(interaction, e)

    @app_commands.command(name="setupvip", description="Posta o painel de compra de VIP.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setup_vip(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            embed = discord.Embed(
                title="⭐ | Torne-se VIP!",
                description=(
                    "Obtenha acesso a benefícios exclusivos, como **descontos especiais em Robux**!\n\n"
                    "Clique no botão abaixo para iniciar a compra e se juntar ao nosso clube de membros VIP."
                ),
                color=discord.Color.gold()
            )
            await interaction.followup.send(embed=embed, view=VIPPanelView(self.bot))
        except Exception as e:
            await self.handle_error(interaction, e)

    @app_commands.command(name="setuppainelcliente", description="Posta o painel da área do cliente.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setup_painel_cliente(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            embed = discord.Embed(
                title="👤 | Área do Cliente",
                description="Clique no botão abaixo para consultar seu histórico de compras.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, view=ClientPanelView(self.bot))
        except Exception as e:
            await self.handle_error(interaction, e)

    desconto_group = app_commands.Group(name="desconto", description="Gerencia o desconto global.", guild_ids=[config.GUILD_ID])
    @desconto_group.command(name="aplicar", description="Aplica um desconto promocional para todos.")
    @app_commands.describe(porcentagem="Valor do desconto (ex: 10).")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def aplicar_desconto(self, interaction: discord.Interaction, porcentagem: float):
        try:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("DELETE FROM discount WHERE id = 1;")
                await conn.execute(
                    "INSERT INTO discount (id, percentage, apply_to_all) VALUES (1, $1, TRUE);",
                    porcentagem
                )
            msg = f"✅ Desconto promocional de **{porcentagem}%** aplicado para ROBUX para **TODOS**!"
            await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            await self.handle_error(interaction, e)

    @desconto_group.command(name="remover", description="Remove o desconto promocional.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def remover_desconto(self, interaction: discord.Interaction):
        try:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("DELETE FROM discount WHERE id = 1;")
            await interaction.response.send_message("🗑️ Desconto promocional removido.", ephemeral=True)
        except Exception as e:
            await self.handle_error(interaction, e)

    @app_commands.command(name="aprovar", description="[Admin] Aprova a compra, registra e move o ticket.")
    @app_commands.describe(membro="O cliente da compra.", gamepass_link="O link ou ID da Game Pass do cliente.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def aprovar(self, interaction: discord.Interaction, membro: discord.Member, gamepass_link: str):
        try:
            await interaction.response.defer(ephemeral=True)
            channel = interaction.channel
            customer = membro
            atendente = await self.bot.fetch_user(interaction.user.id)
            
            async with self.bot.pool.acquire() as conn:
                purchase_record = await conn.fetchrow("SELECT id, product_name, product_price FROM purchases WHERE user_id = $1 AND admin_id IS NULL ORDER BY id DESC LIMIT 1", customer.id)
                if not purchase_record: 
                    return await interaction.followup.send("Nenhum registro de compra pendente encontrado para este cliente.", ephemeral=True)
                
                purchase_id = purchase_record['id']
                product_name = purchase_record['product_name']
                product_price = float(purchase_record['product_price'])
                
                await conn.execute("UPDATE purchases SET admin_id = $1, gamepass_link = $2 WHERE id = $3", atendente.id, gamepass_link, purchase_id)

            guild = interaction.guild
            client_role = guild.get_role(config.CLIENT_ROLE_ID)
            if client_role and client_role not in customer.roles:
                await customer.add_roles(client_role, reason="Compra aprovada.")

            log_channel = guild.get_channel(config.LOGS_COMPRAS_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(title="✅ Log de Compra", color=discord.Color.green(), timestamp=datetime.now(pytz.timezone('America/Sao_Paulo')))
                log_embed.set_thumbnail(url=customer.display_avatar.url)
                log_embed.add_field(name="Cliente", value=f"{customer.mention} ({customer.id})", inline=False)
                log_embed.add_field(name="Produto", value=product_name, inline=True)
                log_embed.add_field(name="Valor", value=f"R$ {product_price:.2f}", inline=True)
                log_embed.add_field(name="Atendente", value=atendente.mention, inline=False)
                log_embed.add_field(name="Entregador", value=f"<@{config.ROBUX_DELIVERY_USER_ID}>", inline=False)
                log_embed.add_field(name="Link da Gamepass", value=gamepass_link, inline=False)
                await log_channel.send(embed=log_embed)

            await channel.send(f"Sua compra foi aprovada! O entregador <@{config.ROBUX_DELIVERY_USER_ID}> já foi notificado. Obrigado!")
            
            public_log_channel = self.bot.get_channel(config.PUBLIC_LOGS_CHANNEL_ID)
            if public_log_channel:
                tickets_cog = self.bot.get_cog("Tickets")
                ticket_info = tickets_cog.ticket_data.get(channel.id, {}) if tickets_cog else {}
                was_discounted = ticket_info.get('was_discounted', False)
                async with self.bot.pool.acquire() as conn:
                    purchase_count = await conn.fetchval("SELECT COUNT(*) FROM purchases WHERE user_id = $1 AND admin_id IS NOT NULL", customer.id)
                public_embed = discord.Embed(title="🛒 Nova Compra na Israbuy!", description=f"Obrigado, {customer.mention}, por comprar conosco!", color=0x9B59B6, timestamp=datetime.now(pytz.timezone('America/Sao_Paulo')))
                public_embed.set_thumbnail(url=customer.display_avatar.url)
                valor_str = f"R$ {product_price:.2f}"
                if was_discounted: valor_str += " `(-3% de Desconto)`"
                public_embed.add_field(name="Produto Comprado", value=product_name, inline=False)
                public_embed.add_field(name="Valor Pago", value=valor_str, inline=False)
                public_embed.add_field(name="Status de Fidelidade", value=f"`{purchase_count}` compras realizadas! 🌟", inline=False)
                review_view = ReviewView(self.bot, purchase_id, customer.id, atendente.id)
                await public_log_channel.send(embed=public_embed, view=review_view)

            entregues_category = guild.get_channel(config.CATEGORY_ENTREGUES_ID)
            if entregues_category: await channel.edit(category=entregues_category, name=f"entregue-{customer.name}-{customer.id}")
            
            await interaction.followup.send("Compra aprovada com sucesso!", ephemeral=True)
            
            giveaway_cog = self.bot.get_cog("Giveaway")
            if giveaway_cog: await giveaway_cog.update_sales_giveaway(customer.id)
            loyalty_cog = self.bot.get_cog("Loyalty")
            if loyalty_cog: await loyalty_cog.check_loyalty_milestones(interaction, customer)
            
            if tickets_cog and channel.id in tickets_cog.ticket_data: del tickets_cog.ticket_data[channel.id]
        except Exception as e:
            await self.handle_error(interaction, e)

    @app_commands.command(name="avaliacao", description="Envia um pedido de avaliação para o cliente no ticket.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def avaliacao(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            channel = interaction.channel
            if not channel.name.startswith("entregue-"):
                return await interaction.followup.send("Use este comando em um canal de ticket arquivado (`entregue-`).", ephemeral=True)
            customer = None
            try:
                name_parts = channel.name.split('-')
                user_id = int(name_parts[-1])
                customer = await self.bot.fetch_user(user_id)
            except (ValueError, IndexError):
                 return await interaction.followup.send("Não foi possível identificar o cliente pelo nome do canal.", ephemeral=True)
            if not customer:
                return await interaction.followup.send("Cliente não encontrado.", ephemeral=True)
            async with self.bot.pool.acquire() as conn:
                last_purchase = await conn.fetchrow("SELECT id, admin_id FROM purchases WHERE user_id = $1 ORDER BY purchase_date DESC LIMIT 1", customer.id)
            if not last_purchase:
                 return await interaction.followup.send("Nenhuma compra encontrada no banco de dados para este cliente.", ephemeral=True)
            view = ReviewView(self.bot, last_purchase['id'], customer.id, last_purchase.get('admin_id'))
            await interaction.channel.send(f"Olá {customer.mention}, poderia nos dar um feedback sobre sua compra?", view=view)
            await interaction.followup.send("Pedido de avaliação enviado ao cliente.", ephemeral=True)
        except Exception as e:
            await self.handle_error(interaction, e)
    
    logs_group = app_commands.Group(name="logs", description="Comandos para gerenciar logs.", guild_ids=[config.GUILD_ID])
    @logs_group.command(name="preencher_publico", description="[Admin] Envia os logs de compras antigas para o canal público.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def backfill_public_logs(self, interaction: discord.Interaction):
        view = BackfillConfirmView()
        await interaction.response.send_message("**⚠️ ATENÇÃO!** Tem certeza que deseja preencher o log público com **TODAS** as compras antigas?", view=view, ephemeral=True)
        await view.wait()
        if not view.confirmed:
            await interaction.followup.send("Operação cancelada.", ephemeral=True)
            return
        public_log_channel = self.bot.get_channel(config.PUBLIC_LOGS_CHANNEL_ID)
        if not public_log_channel: return await interaction.followup.send("❌ Canal de logs públicos não encontrado.", ephemeral=True)
        await interaction.followup.send("Processando...", ephemeral=True)
        async with self.bot.pool.acquire() as conn:
            all_purchases = await conn.fetch("SELECT * FROM purchases WHERE admin_id IS NOT NULL ORDER BY purchase_date ASC")
        for purchase in all_purchases:
            try:
                customer = await self.bot.fetch_user(purchase['user_id'])
                public_embed = discord.Embed(title="🛒 Compra Antiga Registrada!", description=f"Registro da compra de {customer.mention}.", color=0x71368A, timestamp=purchase['purchase_date'])
                public_embed.set_thumbnail(url=customer.display_avatar.url)
                public_embed.add_field(name="Produto Comprado", value=purchase['product_name'], inline=True)
                public_embed.add_field(name="Valor Pago", value=f"R$ {purchase['product_price']:.2f}", inline=True)
                public_embed.set_footer(text=f"ID da Compra: {purchase['id']}")
                await public_log_channel.send(embed=public_embed)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Erro ao processar log antigo para compra ID {purchase['id']}: {e}")
        await interaction.followup.send("✅ Preenchimento de logs concluído!", ephemeral=True)

    @app_commands.command(name="fechar", description="[Admin] Deleta o ticket atual permanentemente.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def fechar(self, interaction: discord.Interaction):
        if "ticket-" in interaction.channel.name or "vip-" in interaction.channel.name or "atendido-" in interaction.channel.name:
            await interaction.response.send_message("Canal será deletado em 5 segundos...", ephemeral=True)
            await asyncio.sleep(5)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)

    @tasks.loop(hours=24)
    async def cleanup_task(self):
        await self.bot.wait_until_ready()
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild: return
        entregues_category = guild.get_channel(config.CATEGORY_ENTREGUES_ID)
        transcript_channel = guild.get_channel(config.TRANSCRIPT_CHANNEL_ID)
        if not entregues_category or not transcript_channel: return
        four_days_ago = discord.utils.utcnow() - timedelta(days=4)
        for channel in entregues_category.text_channels:
            if channel.created_at < four_days_ago:
                try:
                    messages = [f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author.name}: {msg.content}" async for msg in channel.history(limit=200, oldest_first=True)]
                    transcript_content = "\n".join(messages) or "Nenhuma mensagem no ticket."
                    file = discord.File(io.BytesIO(transcript_content.encode('utf-8')), filename=f"transcript-{channel.name}.txt")
                    await transcript_channel.send(f"Transcript do ticket `{channel.name}` deletado por inatividade.", file=file)
                    await channel.delete(reason="Limpeza automática de ticket antigo.")
                except Exception as e:
                    print(f"Erro ao limpar o canal {channel.id}: {e}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
