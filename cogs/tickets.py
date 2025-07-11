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
        # Verifica se a mensagem está em um canal de ticket de Robux
        if "ticket-robux" in channel_name:
            # 1. Detecta comprovante (qualquer anexo)
            if message.attachments:
                view = GamepassCheckView()
                await message.channel.send(
                    f"{message.author.mention}, recebemos seu comprovante! Por favor, responda abaixo:",
                    view=view
                )
                return # Evita que a mesma mensagem seja processada duas vezes

            # 2. Detecta link de gamepass
            match = re.search(r'(?:game-pass/|)(\d{8,})', message.content)
            if match:
                from .views import RegionalPricingCheckView # Evita importação circular
                view = RegionalPricingCheckView()
                await message.reply(
                    "Ótimo! Detectei o link/ID da sua Game Pass. Antes de finalizar, por favor confirme:",
                    view=view
                )

    @app_commands.command(name="minhascompras", description="Ver seu histórico de compras.")
    async def minhas_compras(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with self.bot.pool.acquire() as conn:
            purchases = await conn.fetch(
                "SELECT product_name, product_price, purchase_date FROM purchases WHERE user_id = $1 ORDER BY purchase_date DESC",
                interaction.user.id
            )
        
        if not purchases:
            await interaction.followup.send("Você ainda não fez nenhuma compra.", ephemeral=True)
            return
        
        embed = discord.Embed(title=f"Histórico de Compras de {interaction.user.name}", color=discord.Color.green())
        description = ""
        for p in purchases:
            description += f"**Produto:** {p['product_name']}\n"
            description += f"**Valor:** R$ {p['product_price']:.2f}\n"
            description += f"**Data:** {p['purchase_date'].strftime('%d/%m/%Y %H:%M')}\n---\n"
        
        embed.description = description[:4096]
        await interaction.followup.send(embed=embed, ephemeral=True)

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
        preco = robux * 1.43
        await interaction.response.send_message(
            f"O valor total da Game Pass para `{robux}` Robux é de **R$ {preco:.2f}**.\nSiga o tutorial abaixo para criar a Game Pass corretamente.",
            view=TutorialGamepassView()
        )

    @app_commands.command(name="calculadora", description="Calcula o valor de uma Game Pass.")
    @app_commands.describe(robux="Quantidade de Robux para calcular.")
    async def calculadora(self, interaction: discord.Interaction, robux: int):
        preco = robux * 1.43
        await interaction.response.send_message(f"O valor de uma Game Pass para `{robux}` Robux é **R$ {preco:.2f}**.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))
