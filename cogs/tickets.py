# cogs/tickets.py
import discord
from discord import app_commands
from discord.ext import commands
import config
import re
from .views import GamepassCheckView, TutorialGamepassView

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Armazena {channel_id: {'product': str, 'price': float, 'admin_id': int, 'purchase_id': int}}
        self.ticket_data = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        channel_name = message.channel.name.lower()
        # Garante que estamos em um canal de ticket válido antes de prosseguir
        if not ("ticket-robux" in channel_name or "ticket-geral" in channel_name):
            return

        # 1. Fluxo para tickets de Robux
        if "ticket-robux" in channel_name:
            # Detecta comprovante (qualquer anexo)
            if message.attachments:
                view = GamepassCheckView()
                await message.channel.send(
                    f"{message.author.mention}, recebemos seu comprovante! Por favor, responda abaixo:",
                    view=view
                )
                return  # Para a execução para não processar duas vezes

            # Detecta link de gamepass
            match = re.search(r'(?:game-pass/|)(\d{8,})', message.content)
            if match:
                from .views import RegionalPricingCheckView  # Evita importação circular
                view = RegionalPricingCheckView()
                await message.reply(
                    "Ótimo! Detectei o link/ID da sua Game Pass. Antes de finalizar, por favor confirme:",
                    view=view
                )

    @app_commands.command(name="minhascompras", description="Ver seu histórico de compras.")
    async def minhas_compras(self, interaction: discord.Interaction):
        # Este comando agora é primariamente acionado pelo botão no ClientPanelView
        # O código da view foi movido para cogs/views.py na classe ClientPanelView
        await interaction.response.send_message("Use o painel do cliente para ver suas compras.", ephemeral=True)

    @app_commands.command(name="atender", description="[Admin] Libera o chat para atendimento manual no ticket.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def atender(self, interaction: discord.Interaction):
        channel = interaction.channel
        if "ticket-" in channel.name or "vip-" in channel.name:
            await channel.set_permissions(interaction.user, send_messages=True, read_messages=True)
            new_name = f"atendido-{interaction.user.name}"
            await channel.edit(name=new_name)
            
            if channel.id not in self.ticket_data:
                self.ticket_data[channel.id] = {}
            self.ticket_data[channel.id]['admin_id'] = interaction.user.id

            await interaction.response.send_message(f"{interaction.user.mention} agora está atendendo este ticket. O chat foi liberado.")
        else:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)

    @app_commands.command(name="tutorialgamepass", description="Envia o tutorial da Game Pass com cálculo.")
    @app_commands.describe(robux="Quantidade de Robux desejada.")
    async def tutorial_gamepass(self, interaction: discord.Interaction, robux: int):
        # ATUALIZAÇÃO: Converte o preço para inteiro
        preco = int(robux * 1.43)
        await interaction.response.send_message(
            f"O valor total da Game Pass para `{robux}` Robux é de **R$ {preco}**.\nSiga o tutorial abaixo para criar a Game Pass corretamente.",
            view=TutorialGamepassView()
        )

    @app_commands.command(name="calculadora", description="Calcula o valor de uma Game Pass.")
    @app_commands.describe(robux="Quantidade de Robux para calcular.")
    async def calculadora(self, interaction: discord.Interaction, robux: int):
        # ATUALIZAÇÃO: Converte o preço para inteiro
        preco = int(robux * 1.43)
        await interaction.response.send_message(f"O valor de uma Game Pass para `{robux}` Robux é **R$ {preco}**.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))
