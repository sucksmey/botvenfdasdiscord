# cogs/vendas.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
import math
import re
from datetime import datetime
from config import *

# --- VIEWS PERSISTENTES ---
# A view do painel de vendas precisa ser definida fora da classe do Cog para ser importada no main.py

class ProductSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=name, emoji=data["emoji"]) for name, data in PRODUCTS_DATA.items()]
        super().__init__(placeholder="Escolha um jogo ou serviço para comprar...", options=options, custom_id="persistent_product_select")

    async def callback(self, select_interaction: discord.Interaction):
        await select_interaction.response.defer(ephemeral=True, thinking=True)
        selected_product = self.values[0]
        user = select_interaction.user
        guild = select_interaction.guild

        for channel_id, data in ONGOING_SALES_DATA.items():
            if data.get("client_id") == user.id:
                channel = guild.get_channel(channel_id)
                if channel:
                    await select_interaction.followup.send(f"Você já possui um ticket aberto em {channel.mention}!", ephemeral=True)
                    return
        
        is_vip = any(role.id == VIP_ROLE_ID for role in user.roles)
        category_id = CATEGORY_VENDAS_VIP_ID if is_vip else CATEGORY_VENDAS_ID
        category = discord.utils.get(guild.categories, id=category_id)
        admin_role = guild.get_role(ADMIN_ROLE_ID)
        if not category or not admin_role:
            await select_interaction.followup.send("Erro de configuração do servidor. Contate um administrador.", ephemeral=True)
            return

        ticket_num = int(datetime.now().timestamp()) % 10000
        channel_name = f"ticket-{user.name}-{ticket_num:04d}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        new_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, topic=f"Ticket de {user.display_name} | Produto: {selected_product} | ID: {user.id}")

        product_info = PRODUCTS_DATA[selected_product]
        embed = discord.Embed(title=f"Bem-vindo(a) ao seu ticket, {user.display_name}!", color=ROSE_COLOR)
        embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
        status = "unknown"

        if selected_product == "Robux":
            prices_text = "\n".join([f"**{item}**: R$ {price:.2f}" for item, price in product_info["prices"].items()])
            embed.description = (f"Você selecionou **{selected_product}** {product_info['emoji']}.\n\n"
                               f"Confira nossos pacotes abaixo ou **digite qualquer valor que desejar** (ex: `2500`).")
            embed.add_field(name="Pacotes Padrão", value=prices_text, inline=False)
            status = "awaiting_robux_choice"
        elif product_info.get("prices"):
            price_list = [f"**{item}**: R$ {price:.2f}" for item, price in product_info["prices"].items()]
            prices_text = "\n".join(price_list)
            embed.description = f"Você selecionou **{selected_product}** {product_info['emoji']}.\n\nConfira nossos preços abaixo e **digite o nome exato ou o valor numérico do item** que você deseja."
            embed.add_field(name="Tabela de Preços", value=prices_text, inline=False)
            status = "awaiting_product_choice"
        else:
            embed.description = f"Você selecionou **{selected_product}** {product_info['emoji']}.\n\nUm de nossos atendentes irá te ajudar em breve para fazer o orçamento."
            status = "awaiting_human"
        
        await new_channel.send(content=f"Olá {user.mention}! <@&{ADMIN_ROLE_ID}>", embed=embed)
        ONGOING_SALES_DATA[new_channel.id] = {"client_id": user.id, "product_name": selected_product, "status": status, "is_vip": is_vip}
        await select_interaction.followup.send(f"Seu ticket foi criado com sucesso em {new_channel.mention}!", ephemeral=True)

class SetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ProductSelect())

    @discord.ui.button(label="Ver Tabela de Preços", style=discord.ButtonStyle.secondary, custom_id="show_all_prices_button")
    async def show_prices_callback(self, button_interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="📋 Tabela de Preços Completa - Israbuy", description="Aqui estão os preços de todos os nossos produtos.", color=ROSE_COLOR)
        for product, data in PRODUCTS_DATA.items():
            if data.get("prices"):
                price_list = [f"**{item}**: R$ {price:.2f}" for item, price in data["prices"].items()]
                embed.add_field(name=f"{data['emoji']} {product}", value="\n".join(price_list), inline=True)
        
        embed.set_footer(text="Para comprar, selecione uma opção no menu acima.")
        await button_interaction.response.send_message(embed=embed, ephemeral=True)

# --- OUTRAS VIEWS E FUNÇÕES ---

class GamepassConfirmationView(discord.ui.View):
    # ... (código da GamepassConfirmationView que já funcionava) ...

def calculate_robux_price(amount: int) -> float:
    # ... (código da calculate_robux_price que já funcionava) ...


# --- CLASSE DO COG ---

class Vendas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setupvendas", description="Envia o painel de vendas permanente no canal.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def setupvendas(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✨ Bem-vindo(a) à Loja Israbuy!",
            description="Pronto para a melhor experiência de compra?\n\nSelecione um jogo ou serviço no menu abaixo para abrir um ticket ou clique no botão para ver todos os preços.",
            color=ROSE_COLOR
        )
        embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
        
        # Responde de forma 'invisível' e envia o painel publicamente
        await interaction.response.send_message("Painel de vendas enviado!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=SetupView())


    @app_am_commands.command(name="calculadora", description="Calcula o valor de uma Game Pass para receber uma quantia de Robux.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def calculadora(self, interaction: discord.Interaction, robux: int):
        # ... (código da calculadora que já funcionava) ...

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ... (código do on_message que já funcionava) ...

async def setup(bot: commands.Bot):
    await bot.add_cog(Vendas(bot))
