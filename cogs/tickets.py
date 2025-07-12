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
        # Armazena {channel_id: {'product': str, 'price': float, 'admin_id': int, 'purchase_id': int, 'robux_amount': int}}
        self.ticket_data = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        channel_name = message.channel.name.lower()
        
        # --- CORREÇÃO APLICADA AQUI ---
        # Agora verifica se o canal começa com "ticket-" OU "atendido-"
        if not (channel_name.startswith("ticket-") or channel_name.startswith("atendido-")):
            return

        # O fluxo de Robux só deve ser acionado em canais de robux
        # O nome original (ticket-robux-...) é preservado mesmo após renomear para atendido- a nível de ID e objeto
        # Uma verificação mais segura seria por dados armazenados, mas por nome é mais simples.
        # Vamos assumir que se o admin atendeu, ele sabe o contexto.

        ticket_info = self.ticket_data.get(message.channel.id, {})
        robux_amount = ticket_info.get('robux_amount', 0)

        # 1. Detecta comprovante (qualquer anexo)
        if message.attachments and robux_amount > 0: # Só aciona o fluxo de gamepass se for uma compra de robux
            view = GamepassCheckView(robux_amount=robux_amount)
            await message.channel.send(
                f"{message.author.mention}, nós entregamos por Gamepass. Você já sabe criar a gamepass?",
                view=view
            )
            return

        # 2. Detecta link de gamepass
        if robux_amount > 0: # Só aciona o fluxo de gamepass se for uma compra de robux
            match = re.search(r'(?:game-pass/|)(\d{8,})', message.content)
            if match:
                from .views import RegionalPricingCheckView
                view = RegionalPricingCheckView()
                await message.reply(
                    "Ótimo! Detectei o link/ID da sua Game Pass. Antes de finalizar, por favor confirme se você **DESATIVOU** os preços regionais:",
                    view=view
                )

    @app_commands.command(name="minhascompras", description="Ver seu histórico de compras.")
    async def minhas_compras(self, interaction: discord.Interaction):
        # A lógica principal deste comando está na ClientPanelView em cogs/views.py
        await interaction.response.send_message("Use o painel do cliente para ver suas compras.", ephemeral=True)

    @app_commands.command(name="atender", description="[Admin] Libera o chat para atendimento manual no ticket.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def atender(self, interaction: discord.Interaction):
        channel = interaction.channel
        if channel.name.startswith("ticket-") or channel.name.startswith("vip-"):
            # Renomeia o canal mantendo o ID do cliente para referência futura
            original_name_parts = channel.name.split('-')
            customer_id = original_name_parts[-1]
            new_name = f"atendido-{interaction.user.name}-{customer_id}"

            await channel.set_permissions(interaction.user, send_messages=True, read_messages=True)
            await channel.edit(name=new_name)
            
            if channel.id not in self.ticket_data:
                self.ticket_data[channel.id] = {}
            self.ticket_data[channel.id]['admin_id'] = interaction.user.id

            await interaction.response.send_message(f"{interaction.user.mention} agora está atendendo este ticket. O chat foi liberado.")
        else:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)

    @app_commands.command(name="tutorialgamepass", description="Calcula o valor que a Game Pass deve ter (inclui taxa de 30%).")
    @app_commands.describe(robux="A quantidade de Robux que você quer RECEBER.")
    async def tutorial_gamepass(self, interaction: discord.Interaction, robux: int):
        gamepass_value = int((robux / 0.7) + 0.99)
        await interaction.response.send_message(
            f"Para você receber `{robux}` Robux, a Game Pass precisa ser criada com o valor de **{gamepass_value} Robux** (para cobrir a taxa de 30% do Roblox).\nSiga o tutorial abaixo para criar a Game Pass corretamente.",
            view=TutorialGamepassView()
        )

    @app_commands.command(name="calculadora", description="Calcula o valor de uma Game Pass para receber uma quantia de Robux.")
    @app_commands.describe(robux="A quantidade de Robux que você quer RECEBER.")
    async def calculadora(self, interaction: discord.Interaction, robux: int):
        gamepass_value = int((robux / 0.7) + 0.99)
        await interaction.response.send_message(f"Para receber `{robux}` Robux, a Game Pass deve ser de **{gamepass_value} Robux**.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))
