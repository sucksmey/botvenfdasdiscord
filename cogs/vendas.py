# cogs/vendas.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
import math
import re
from datetime import datetime
from config import *

# ... (A classe GamepassConfirmationView continua a mesma) ...

# NOVO: Função para calcular o preço de Robux customizado
def calculate_robux_price(amount: int) -> float:
    if amount <= 0:
        return 0.0
    
    # Preços fixos para valores comuns para dar um "desconto"
    if amount in [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]:
        return PRODUCTS_DATA["Robux"]["prices"][f"{amount} Robux"]

    # Lógica de cálculo para valores customizados
    thousands = amount // 1000
    remainder = amount % 1000
    
    price = thousands * PRODUCTS_DATA["Robux"]["prices"]["1000 Robux"]
    
    # Encontra o pacote mais próximo para o restante
    if remainder > 0:
        # Arredonda o restante para a centena mais próxima
        closest_hundred = math.ceil(remainder / 100) * 100
        if f"{closest_hundred} Robux" in PRODUCTS_DATA["Robux"]["prices"]:
            price += PRODUCTS_DATA["Robux"]["prices"][f"{closest_hundred} Robux"]
        else: # Se não houver, calcula pelo preço unitário
            price += remainder * ROBUX_PRICE_PER_UNIT

    return round(price, 2)

class Vendas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # NOVO: Comando /calculadora
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


    # Listener foi ATUALIZADO com as novas lógicas
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ... (código inicial do listener continua o mesmo) ...

        # ATUALIZADO: Lógica para escolha de produto
        if status == "awaiting_product_choice":
            # ... (código para outros produtos continua o mesmo) ...
            # ATUALIZADO: Fuzzy matching para encontrar o item
            user_choice_num = re.sub(r'[^0-9]', '', message.content)
            matched_item = None
            for item_name in product_info["prices"]:
                item_name_num = re.sub(r'[^0-9]', '', item_name)
                # Verifica se o nome é igual OU se os números são iguais
                if user_choice.lower() == item_name.lower() or (user_choice_num and user_choice_num == item_name_num):
                    matched_item = item_name
                    break
            # ... (resto da lógica de escolha de produto) ...

        # NOVO: Lógica para receber quantidade customizada de Robux
        if status == "awaiting_robux_amount":
            try:
                amount = int(re.sub(r'[^0-9]', '', message.content))
                if amount <= 0:
                    await message.channel.send("Por favor, digite um valor válido e positivo.")
                    return
                
                price = calculate_robux_price(amount)
                item_name = f"{amount} Robux (Custom)"
                
                ticket_data.update({"status": "awaiting_payment", "final_price": price, "item_name": item_name})
                
                await message.channel.send(f"Certo! O valor para **{amount} Robux** é de **R$ {price:.2f}**.")
                pix_embed = discord.Embed(title="Pagamento via PIX", # ...
                # ... (resto da mensagem do pix)
            except (ValueError, TypeError):
                await message.channel.send("Não entendi o valor. Por favor, digite apenas a quantidade de Robux que você deseja (ex: `9400`).")

    # Comando /setupvendas foi ATUALIZADO
    @app_commands.command(name="setupvendas", description="Envia o painel de abertura de tickets de venda.")
    # ...
    # ATUALIZADO: Lógica dentro do callback do ProductSelect
    async def callback(self, select_interaction: discord.Interaction):
        # ... (lógica de criar o ticket continua a mesma) ...

        # ATUALIZADO: Mensagem para Robux é diferente agora
        if selected_product == "Robux":
            embed.description = f"Você selecionou **{selected_product}** {product_info['emoji']}.\n\nPor favor, **digite a quantidade de Robux que você deseja comprar** (ex: 2500)."
            status = "awaiting_robux_amount"
        elif prices_text:
            # ... (lógica para outros produtos continua a mesma) ...
        # ... (resto da lógica do callback) ...

# ... (resto do arquivo e a função setup continuam os mesmos) ...
