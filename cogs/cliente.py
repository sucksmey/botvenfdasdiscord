# cogs/cliente.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import *
import database

# --- Função Helper para buscar histórico ---
async def show_purchase_history(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        async with database.engine.connect() as conn:
            query = database.transactions.select().where(database.transactions.c.user_id == interaction.user.id).order_by(database.transactions.c.timestamp.desc())
            result = await conn.execute(query)
            user_purchases = result.fetchall()

        if not user_purchases:
            await interaction.followup.send("Você ainda não possui nenhuma compra registrada em nosso sistema.", ephemeral=True)
            return

        embed = discord.Embed(title=f"📜 Histórico de Compras de {interaction.user.name}", color=ROSE_COLOR)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        description_lines = []
        total_spent = 0.0
        for purchase in user_purchases[:10]: # Limita a 10 compras para não sobrecarregar
            purchase_date = purchase.timestamp.strftime('%d/%m/%Y às %H:%M')
            description_lines.append(
                f"**Produto:** {purchase.product_name}\n"
                f"**Valor:** R$ {purchase.price:.2f}\n"
                f"**Data:** {purchase_date} (UTC)\n"
                f"--------------------"
            )
            total_spent += purchase.price
        
        embed.description = "\n".join(description_lines)
        embed.set_footer(text=f"Total gasto: R$ {total_spent:.2f} | Mostrando as últimas {len(user_purchases[:10])} de {len(user_purchases)} compras.")

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logging.error(f"Erro ao buscar histórico de compras para {interaction.user.id}: {e}")
        await interaction.followup.send("Ocorreu um erro ao tentar buscar seu histórico. Por favor, tente novamente mais tarde.", ephemeral=True)


# --- View Persistente para o Painel do Cliente ---
class CustomerAreaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ver Minhas Compras", style=discord.ButtonStyle.primary, custom_id="view_my_purchases_button", emoji="📜")
    async def view_purchases_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_purchase_history(interaction)


# --- Cog do Cliente ---
class Cliente(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="minhascompras", description="Mostra o seu histórico de compras na loja.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def minhascompras(self, interaction: discord.Interaction):
        await show_purchase_history(interaction)

    @app_commands.command(name="setuppainelcliente", description="[Admin] Envia o painel da Área do Cliente.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def setup_customer_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👤 Área do Cliente - Israbuy",
            description="Bem-vindo(a) à sua área de cliente!\n\nClique no botão abaixo para ver seu histórico de compras de forma privada.",
            color=ROSE_COLOR
        )
        embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
        await interaction.response.send_message("Painel do cliente criado!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=CustomerAreaView())


async def setup(bot: commands.Bot):
    await bot.add_cog(Cliente(bot))
