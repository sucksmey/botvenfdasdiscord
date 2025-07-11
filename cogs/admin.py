# cogs/admin.py
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import config
from .views import SalesPanelView, VIPPanelView, ClientPanelView, PriceTableView

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cleanup_task.start()

    def cog_unload(self):
        self.cleanup_task.cancel()

    @app_commands.command(name="setupvendas", description="Posta o painel de vendas no canal.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setup_vendas(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛒 | Central de Vendas - Israbuy",
            description="Bem-vindo à nossa loja! Selecione uma categoria abaixo para ver os produtos disponíveis ou clique no botão para ver a tabela completa.",
            color=discord.Color.blue()
        )
        embed.set_image(url="https://i.imgur.com/your-banner-image.png") # Coloque uma URL de banner aqui
        await interaction.channel.send(embed=embed, view=SalesPanelView(self.bot))
        await interaction.response.send_message("Painel de vendas criado!", ephemeral=True)

    @app_commands.command(name="setupvip", description="Posta o painel de compra de VIP.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setup_vip(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⭐ | Torne-se VIP!",
            description=(
                "Obtenha acesso a benefícios exclusivos, como **descontos especiais em Robux**!\n\n"
                "Clique no botão abaixo para iniciar a compra e se juntar ao nosso clube de membros VIP."
            ),
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=embed, view=VIPPanelView(self.bot))
        await interaction.response.send_message("Painel VIP criado!", ephemeral=True)

    @app_commands.command(name="setuppainelcliente", description="Posta o painel da área do cliente.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setup_painel_cliente(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👤 | Área do Cliente",
            description="Clique no botão abaixo para consultar seu histórico de compras.",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed, view=ClientPanelView(self.bot))
        await interaction.response.send_message("Painel do cliente criado!", ephemeral=True)

    # Grupo de comandos para desconto
    desconto_group = app_commands.Group(name="desconto", description="Gerencia o desconto global.", guild_ids=[config.GUILD_ID])

    @desconto_group.command(name="aplicar", description="Aplica um desconto global em porcentagem.")
    @app_commands.describe(porcentagem="Valor do desconto (ex: 10 para 10%).")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def aplicar_desconto(self, interaction: discord.Interaction, porcentagem: float):
        async with self.bot.pool.acquire() as conn:
            await conn.execute("DELETE FROM discount WHERE id = 1;")
            await conn.execute("INSERT INTO discount (id, percentage) VALUES (1, $1);", porcentagem)
        await interaction.response.send_message(f"✅ Desconto global de **{porcentagem}%** aplicado com sucesso!", ephemeral=True)

    @desconto_group.command(name="remover", description="Remove o desconto global ativo.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def remover_desconto(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            await conn.execute("DELETE FROM discount WHERE id = 1;")
        await interaction.response.send_message("🗑️ Desconto global removido. Os preços voltaram ao normal.", ephemeral=True)

    @app_commands.command(name="fechar", description="[Admin] Deleta o ticket atual permanentemente.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def fechar(self, interaction: discord.Interaction):
        if "ticket-" in interaction.channel.name or "vip-" in interaction.channel.name or "atendido-" in interaction.channel.name:
            await interaction.response.send_message("Canal será deletado em 5 segundos...", ephemeral=True)
            await asyncio.sleep(5)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)

    # Tarefa de limpeza de tickets antigos
    @tasks.loop(hours=24)
    async def cleanup_task(self):
        await self.bot.wait_until_ready()
        guild = self.bot.get_guild(config.GUILD_ID)
        entregues_category = guild.get_channel(config.CATEGORY_ENTREGUES_ID)
        transcript_channel = guild.get_channel(config.TRANSCRIPT_CHANNEL_ID)
        four_days_ago = datetime.utcnow() - timedelta(days=4)

        for channel in entregues_category.text_channels:
            # Pega a data de criação do canal para verificar a idade
            if channel.created_at.replace(tzinfo=None) < four_days_ago:
                try:
                    # Gera um transcript simples
                    messages = [f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author.name}: {msg.content}" async for msg in channel.history(limit=200, oldest_first=True)]
                    transcript_content = "\n".join(messages)
                    
                    if not transcript_content:
                        transcript_content = "Nenhuma mensagem no ticket."
                    
                    file = discord.File(io.BytesIO(transcript_content.encode('utf-8')), filename=f"transcript-{channel.name}.txt")

                    await transcript_channel.send(f"Transcript do ticket `{channel.name}` deletado por inatividade.", file=file)
                    await channel.delete(reason="Limpeza automática de ticket antigo.")
                except Exception as e:
                    print(f"Erro ao limpar o canal {channel.id}: {e}")

async def setup(bot):
    # Importar views aqui para evitar importação circular
    from . import views
    # Adicionar a cog
    await bot.add_cog(Admin(bot))
