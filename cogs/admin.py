# cogs/admin.py
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import config
import io
import asyncio
import traceback
from .views import SalesPanelView, VIPPanelView, ClientPanelView

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

    @desconto_group.command(name="aplicar", description="Aplica um desconto (padrão: 1ª compra de Robux).")
    @app_commands.describe(porcentagem="Valor do desconto (ex: 10).", para_todos="Liberar para todos (Sim/Não)?")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def aplicar_desconto(self, interaction: discord.Interaction, porcentagem: float, para_todos: bool = False):
        try:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("DELETE FROM discount WHERE id = 1;")
                await conn.execute(
                    "INSERT INTO discount (id, percentage, apply_to_all) VALUES (1, $1, $2);",
                    porcentagem, para_todos
                )
            msg = f"✅ Desconto de **{porcentagem}%** aplicado para ROBUX."
            if para_todos:
                msg += " **Liberado para todos os membros!**"
            else:
                msg += " **Válido apenas para a primeira compra de não-clientes.**"
            await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            await self.handle_error(interaction, e)

    @desconto_group.command(name="remover", description="Remove o desconto global de Robux.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def remover_desconto(self, interaction: discord.Interaction):
        try:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("DELETE FROM discount WHERE id = 1;")
            await interaction.response.send_message("🗑️ Desconto de Robux removido. Os preços voltaram ao normal.", ephemeral=True)
        except Exception as e:
            await self.handle_error(interaction, e)

    # --- COMANDO /aprovar ATUALIZADO ---
    @app_commands.command(name="aprovar", description="[Admin] Aprova a compra, registra e move o ticket.")
    @app_commands.describe(
        gamepass_link="O link ou ID da Game Pass do cliente.",
        membro="(Opcional) Marque o cliente se o bot não o encontrar automaticamente."
    )
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def aprovar(self, interaction: discord.Interaction, gamepass_link: str, membro: discord.Member = None):
        try:
            await interaction.response.defer(ephemeral=True)
            channel = interaction.channel
            customer = membro # Usa o membro marcado, se fornecido

            # Se nenhum membro for marcado, tenta a detecção automática
            if not customer:
                try:
                    name_parts = channel.name.split('-')
                    # Itera de trás para frente para encontrar o primeiro número, que deve ser o ID
                    for part in reversed(name_parts):
                        if part.isdigit():
                            user_id = int(part)
                            customer = await self.bot.fetch_user(user_id)
                            break
                    if not customer: # Se o loop terminar e não encontrar
                         raise ValueError("ID do usuário não encontrado no nome do canal.")
                except (ValueError, IndexError):
                    return await interaction.followup.send("Não consegui identificar o cliente pelo nome do canal. Por favor, use o parâmetro opcional `membro` para marcá-lo.", ephemeral=True)

            tickets_cog = self.bot.get_cog("Tickets")
            if not tickets_cog:
                return await interaction.followup.send("Erro: A cog de tickets não foi encontrada.", ephemeral=True)

            ticket_info = tickets_cog.ticket_data.get(channel.id, {})
            product_name = ticket_info.get('product', 'N/A')
            product_price = ticket_info.get('price', 0.0)
            atendente_id = ticket_info.get('admin_id', interaction.user.id)
            atendente = await self.bot.fetch_user(atendente_id)
            
            purchase_id = ticket_info.get('purchase_id')
            if not purchase_id:
                return await interaction.followup.send("Erro: ID da compra não encontrado no ticket. O fluxo pode ter sido interrompido.", ephemeral=True)

            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE purchases SET admin_id = $1, gamepass_link = $2 WHERE id = $3",
                    atendente.id, gamepass_link, purchase_id
                )

            guild = interaction.guild
            entregues_category = guild.get_channel(config.CATEGORY_ENTREGUES_ID)
            log_channel = guild.get_channel(config.LOGS_COMPRAS_CHANNEL_ID)

            log_embed = discord.Embed(title="✅ Log de Compra", color=discord.Color.green(), timestamp=discord.utils.utcnow())
            log_embed.set_thumbnail(url=customer.display_avatar.url)
            log_embed.add_field(name="Cliente", value=f"{customer.mention} ({customer.id})", inline=False)
            log_embed.add_field(name="Produto", value=product_name, inline=True)
            log_embed.add_field(name="Valor", value=f"R$ {product_price:.2f}", inline=True)
            log_embed.add_field(name="Atendente", value=atendente.mention, inline=False)
            log_embed.add_field(name="Entregador", value=f"<@{config.ROBUX_DELIVERY_USER_ID}>", inline=False)
            log_embed.add_field(name="Link da Gamepass", value=gamepass_link, inline=False)

            if log_channel:
                await log_channel.send(embed=log_embed)

            await channel.send(f"Sua compra foi aprovada! O entregador <@{config.ROBUX_DELIVERY_USER_ID}> já foi notificado. Obrigado por comprar conosco!")
            
            if entregues_category:
                await channel.edit(category=entregues_category, name=f"entregue-{customer.name}")

            await interaction.followup.send("Compra aprovada com sucesso!", ephemeral=True)
            if channel.id in tickets_cog.ticket_data:
                del tickets_cog.ticket_data[channel.id]
        except Exception as e:
            await self.handle_error(interaction, e)

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
