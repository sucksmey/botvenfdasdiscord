# cogs/tickets.py
import discord
from discord import app_commands
from discord.ext import commands
import config
import re
from .views import GamepassCheckView, TutorialGamepassView, GameSelectionView

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_data = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if message.channel.id == config.COMPRE_AQUI_CHANNEL_ID:
            content = message.content.strip()
            if content.isdigit():
                number_amount = int(content)
                view = GameSelectionView(self.bot, number_amount, message)
                await message.reply("Detectei um valor! Para qual jogo você gostaria de comprar?", view=view)
                return

        channel_name = message.channel.name.lower()
        if not (channel_name.startswith("ticket-") or channel_name.startswith("atendido-")):
            return
        
        try:
            name_parts = message.channel.name.split('-')
            customer_id_from_name = int(name_parts[-1])
        except (ValueError, IndexError):
            return

        if message.author.id != customer_id_from_name:
            return

        ticket_info = self.ticket_data.get(message.channel.id, {})
        robux_amount = ticket_info.get('robux_amount', 0)

        if robux_amount > 0:
            if message.attachments:
                view = GamepassCheckView(robux_amount=robux_amount)
                await message.channel.send(f"{message.author.mention}, recebemos seu comprovante! Por favor, responda abaixo:", view=view)
                return

            match = re.search(r'(?:game-pass/|)(\d{8,})', message.content)
            if match:
                from .views import RegionalPricingCheckView
                view = RegionalPricingCheckView()
                await message.reply("Ótimo! Detectei o link/ID da sua Game Pass. Antes de finalizar, por favor confirme se você **DESATIVOU** os preços regionais:", view=view)
    
    @app_commands.command(name="minhascompras", description="Ver seu histórico de compras.")
    async def minhas_compras(self, interaction: discord.Interaction):
        await interaction.response.send_message("Use o painel do cliente para ver suas compras.", ephemeral=True)

    @app_commands.command(name="atender", description="[Admin] Libera o chat para atendimento manual no ticket.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def atender(self, interaction: discord.Interaction):
        channel = interaction.channel
        if channel.name.startswith("ticket-") or channel.name.startswith("vip-"):
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
            f"Para você receber `{robux}` Robux, a Game Pass precisa ser criada com o valor de **{gamepass_value} Robux** (para cobrir a taxa de 30% do Roblox).\nSiga o tutorial abaixo.",
            view=TutorialGamepassView()
        )

    @app_commands.command(name="calculadora", description="Calcula o valor de uma Game Pass para receber uma quantia de Robux.")
    @app_commands.describe(robux="A quantidade de Robux que você quer RECEBER.")
    async def calculadora(self, interaction: discord.Interaction, robux: int):
        gamepass_value = int((robux / 0.7) + 0.99)
        await interaction.response.send_message(f"Para receber `{robux}` Robux, a Game Pass deve ser de **{gamepass_value} Robux**.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))
