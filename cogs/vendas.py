# cogs/vendas.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
import math
import re
from datetime import datetime
from config import *

# A classe GamepassConfirmationView continua a mesma que já funcionava
class GamepassConfirmationView(discord.ui.View):
    def __init__(self, robux_amount: int):
        super().__init__(timeout=300)
        self.robux_amount = robux_amount

    @discord.ui.button(label="Sim, já sei criar", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        gamepass_value = math.ceil(self.robux_amount / 0.7)
        embed = discord.Embed(
            title="💎 Calculadora de Game Pass",
            description=(
                f"Para receber **{self.robux_amount} Robux**, você precisa criar uma Game Pass no valor de **{gamepass_value} Robux**.\n\n"
                "**Importante:** Ao criar, **NÃO** marque a opção de preços regionais.\n\n"
                "Por favor, envie o link da sua Game Pass aqui no chat."
            ),
            color=ROSE_COLOR
        )
        await interaction.response.send_message(embed=embed)
        if interaction.channel.id in ONGOING_SALES_DATA:
            ONGOING_SALES_DATA[interaction.channel.id]['status'] = 'awaiting_gamepass_link'

    @discord.ui.button(label="Não, preciso de ajuda", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        gamepass_value = math.ceil(self.robux_amount / 0.7)
        embed = discord.Embed(
            title="📄 Tutorial e Cálculo da Game Pass",
            description=(
                f"Sem problemas! Assista a este vídeo para aprender a criar sua Game Pass:\n{TUTORIAL_GAMEPASS_URL}\n\n"
                f"Após assistir, crie uma Game Pass de **{gamepass_value} Robux** e envie o link dela aqui no chat."
            ),
            color=ROSE_COLOR
        )
        await interaction.response.send_message(embed=embed)
        if interaction.channel.id in ONGOING_SALES_DATA:
            ONGOING_SALES_DATA[interaction.channel.id]['status'] = 'awaiting_gamepass_link'


# A função de cálculo de Robux foi aprimorada
def calculate_robux_price(amount: int) -> float:
    if amount <= 0:
        return 0.0
    
    if f"{amount} Robux" in PRODUCTS_DATA["Robux"]["prices"]:
        return PRODUCTS_DATA["Robux"]["prices"][f"{amount} Robux"]

    thousands = amount // 1000
    remainder = amount % 1000
    price = thousands * PRODUCTS_DATA["Robux"]["prices"]["1000 Robux"]
    
    if remainder > 0:
        closest_hundred = math.ceil(remainder / 100) * 100
        if f"{closest_hundred} Robux" in PRODUCTS_DATA["Robux"]["prices"]:
            price += PRODUCTS_DATA["Robux"]["prices"][f"{closest_hundred} Robux"]
        else:
            price += remainder * ROBUX_PRICE_PER_UNIT
    return round(price, 2)


class Vendas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="calculadora", description="Calcula o valor de uma Game Pass para receber uma quantia de Robux.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def calculadora(self, interaction: discord.Interaction, robux: int):
        if robux <= 0:
            await interaction.response.send_message("Por favor, insira um valor de Robux maior que zero.", ephemeral=True)
            return
        
        gamepass_value = math.ceil(robux / 0.7)
        embed = discord.Embed(
            title="🧮 Calculadora de Game Pass",
            description=f"Para o comprador receber **{robux} Robux**, ele precisa criar uma Game Pass no valor de **{gamepass_value} Robux**.",
            color=ROSE_COLOR
        )
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not isinstance(message.channel, discord.TextChannel) or not message.guild:
            return

        ticket_data = ONGOING_SALES_DATA.get(message.channel.id)
        if not ticket_data:
            return

        status = ticket_data.get("status")
        # Ignora mensagens se um admin estiver atendendo
        if status == 'being_attended_by_human':
            return

        # Lógica de pagamento (sem alteração)
        if status == "awaiting_payment" and message.attachments:
            # ... (seu código de pagamento continua aqui) ...
            return

        # Lógica da gamepass (sem alteração)
        if status == "awaiting_gamepass_link" and ("roblox.com/game-pass/" in message.content or "ro.blox.com/Ebh5" in message.content):
            # ... (seu código da gamepass continua aqui) ...
            return

        # ALTERADO: Lógica unificada para Robux
        if status == "awaiting_robux_choice":
            user_input = message.content.strip()
            # Tenta encontrar um pacote padrão primeiro
            matched_item_price = PRODUCTS_DATA["Robux"]["prices"].get(f"{user_input} Robux")

            if matched_item_price:
                price = matched_item_price
                item_name = f"{user_input} Robux"
            else:
                # Se não for um pacote, tenta calcular um valor customizado
                try:
                    amount = int(re.sub(r'[^0-9]', '', user_input))
                    if amount <= 0: raise ValueError()
                    price = calculate_robux_price(amount)
                    item_name = f"{amount} Robux"
                except (ValueError, TypeError):
                    await message.channel.send("Não entendi o valor. Por favor, digite um dos pacotes da lista ou um número (ex: `9500`).")
                    return

            ticket_data.update({"status": "awaiting_payment", "final_price": price, "item_name": item_name})
            await message.channel.send(f"Ótima escolha! O valor para **{item_name}** é de **R$ {price:.2f}**.")
            pix_embed = discord.Embed(title="Pagamento via PIX", description="Use o QR Code acima ou a chave **Copia e Cola** enviada abaixo.", color=ROSE_COLOR).set_footer(text="Após pagar, por favor, envie o comprovante neste chat.").set_image(url=QR_CODE_URL)
            await message.channel.send(embed=pix_embed)
            await message.channel.send(f"`{PIX_KEY_MANUAL}`")
            return

        # Lógica para outros produtos (sem alteração)
        if status == "awaiting_product_choice":
            # ... (seu código para outros produtos continua aqui) ...
            return


    @app_commands.command(name="setupvendas", description="Envia o painel de abertura de tickets de venda.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def setupvendas(self, interaction: discord.Interaction):
        
        class ProductSelect(discord.ui.Select):
            # ... (código do __init__ do ProductSelect continua o mesmo) ...

            async def callback(self, select_interaction: discord.Interaction):
                # ... (lógica de criar ticket continua a mesma) ...
                
                # ALTERADO: Lógica de mensagem inicial foi aprimorada
                if selected_product == "Robux":
                    prices_text = "\n".join([f"**{item}**: R$ {price:.2f}" for item, price in product_info["prices"].items()])
                    embed.description = (f"Você selecionou **{selected_product}** {product_info['emoji']}.\n\n"
                                       f"Confira nossos pacotes abaixo ou **digite qualquer valor que desejar** (ex: `2500`).")
                    embed.add_field(name="Pacotes Padrão", value=prices_text, inline=False)
                    status = "awaiting_robux_choice"
                elif product_info.get("prices"):
                    # ... (lógica para outros produtos continua a mesma) ...
                else:
                    # ... (lógica para produtos sem preço continua a mesma) ...

                # ... (resto do código do callback continua o mesmo) ...

        # ALTERADO: A View agora tem o botão de ver preços
        class SetupView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                self.add_item(ProductSelect())

            @discord.ui.button(label="Ver Tabela de Preços", style=discord.ButtonStyle.secondary, custom_id="show_all_prices")
            async def show_prices_callback(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                embed = discord.Embed(
                    title="📋 Tabela de Preços Completa - Israbuy",
                    description="Aqui estão os preços de todos os nossos produtos.",
                    color=ROSE_COLOR
                )
                for product, data in PRODUCTS_DATA.items():
                    if data.get("prices"):
                        price_list = [f"**{item}**: R$ {price:.2f}" for item, price in data["prices"].items()]
                        embed.add_field(name=f"{data['emoji']} {product}", value="\n".join(price_list), inline=True)
                
                embed.set_footer(text="Para comprar, selecione uma opção no menu acima.")
                await button_interaction.response.send_message(embed=embed, ephemeral=True)
        
        embed = discord.Embed(
            title="✨ Bem-vindo(a) à Loja Israbuy!",
            description="Pronto para a melhor experiência de compra?\n\nSelecione um jogo ou serviço no menu abaixo para abrir um ticket ou clique no botão para ver todos os preços.",
            color=ROSE_COLOR
        )
        embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
        await interaction.response.send_message(embed=embed, view=SetupView())

async def setup(bot: commands.Bot):
    await bot.add_cog(Vendas(bot))
