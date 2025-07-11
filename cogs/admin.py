# cogs/admin.py
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import config
import io
import asyncio
from .views import SalesPanelView, VIPPanelView, ClientPanelView

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cleanup_task.start()

    def cog_unload(self):
        self.cleanup_task.cancel()

    @app_commands.command(name="setupvendas", description="Posta o painel de vendas no canal.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setup_vendas(self, interaction: discord.Interaction):
        # Responde primeiro para evitar o timeout
        await interaction.response.send_message("Criando painel de vendas...", ephemeral=True)

        embed = discord.Embed(
            title="🛒 | Central de Vendas - Israbuy",
            description="Bem-vindo à nossa loja! Selecione uma categoria abaixo para ver os produtos disponíveis ou clique no botão para ver a tabela completa.",
            color=discord.Color.blue()
        )
        
        # Envia o painel no canal como uma nova mensagem
        await interaction.channel.send(embed=embed, view=SalesPanelView(self.bot))

    @app_commands.command(name="setupvip", description="Posta o painel de compra de VIP.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setup_vip(self, interaction: discord.Interaction):
        await interaction.response.send_message("Criando painel VIP...", ephemeral=True)
        embed = discord.Embed(
            title="⭐ | Torne-se VIP!",
            description=(
                "Obtenha acesso a benefícios exclusivos, como **descontos especiais em Robux**!\n\n"
                "Clique no botão abaixo para iniciar a compra e se juntar ao nosso clube de membros VIP."
            ),
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=embed, view=VIPPanelView(self.bot))

    @app_commands.command(name="setuppainelcliente", description="Posta o painel da área do cliente.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setup_painel_cliente(self, interaction: discord.Interaction):
        await interaction.response.send_message("Criando painel do cliente...", ephemeral=True)
        embed = discord.Embed(
            title="👤 | Área do Cliente",
            description="Clique no botão abaixo para consultar seu histórico de compras.",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed, view=ClientPanelView(self.bot))

    desconto_group = app_commands.Group(name="desconto", description="Gerencia o desconto global.", guild_ids=[config.GUILD_ID])

    @desconto_group.command(name="aplicar", description="Aplica um desconto global (APENAS PARA ROBUX).")
    @app_commands.describe(porcentagem="Valor do desconto (ex: 10 para 10%).")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def aplicar_desconto(self, interaction: discord.Interaction, porcentagem: float):
        async with self.bot.pool.acquire() as conn:
            await conn.execute("DELETE FROM discount WHERE id = 1;")
            await conn.execute("INSERT INTO discount (id, percentage) VALUES (1, $1);", porcentagem)
        await interaction.response.send_message(f"✅ Desconto de **{porcentagem}%** aplicado com sucesso para a categoria ROBUX!", ephemeral=True)

    @desconto_group.command(name="remover", description="Remove o desconto global de Robux.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def remover_desconto(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            await conn.execute("DELETE FROM discount WHERE id = 1;")
        await interaction.response.send_message("🗑️ Desconto de Robux removido. Os preços voltaram ao normal.", ephemeral=True)

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
