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
        
        await interaction.response.send_message("Painel de vendas enviado!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=SetupView())

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
        if status == 'being_attended_by_human':
            return

        if status == "awaiting_payment" and message.attachments:
            await message.channel.send(f"Obrigado, {message.author.mention}! Seu comprovante foi recebido e está sendo processado.")
            try:
                client_role = message.guild.get_role(CLIENT_ROLE_ID)
                if client_role: await message.author.add_roles(client_role, reason="Iniciou uma compra.")
            except Exception as e:
                logging.error(f"Não foi possível adicionar o cargo de cliente: {e}")

            if ticket_data.get("product_name") == "Robux":
                item_name = ticket_data.get("item_name", "0 Robux")
                robux_amount = int(re.sub(r'[^0-9]', '', item_name))
                if robux_amount > 0:
                    embed = discord.Embed(title="Entrega de Robux", description="Para a entrega, precisamos que você crie uma Game Pass. Você já sabe como fazer isso?", color=ROSE_COLOR)
                    await message.channel.send(embed=embed, view=GamepassConfirmationView(robux_amount=robux_amount))
                    ticket_data["status"] = "awaiting_gamepass_info"
                else:
                    await message.channel.send(f"<@&{ADMIN_ROLE_ID}>, não consegui determinar a quantidade de Robux. Por favor, assuma.")
                    ticket_data["status"] = "delivery_pending"
            else:
                await message.channel.send(f"Sua compra de **{ticket_data.get('item_name')}** está em processamento. Um <@&{ADMIN_ROLE_ID}> irá finalizar a entrega em breve.")
                ticket_data["status"] = "delivery_pending"
            return

        if status == "awaiting_gamepass_link" and ("roblox.com/game-pass/" in message.content or "ro.blox.com/Ebh5" in message.content):
            delivery_user = self.bot.get_user(ROBUX_DELIVERY_USER_ID)
            mention = delivery_user.mention if delivery_user else f"<@{ROBUX_DELIVERY_USER_ID}>"
            await message.channel.send(f"Link da Game Pass recebido! O responsável pela entrega, {mention}, foi notificado e fará a compra em breve.")
            try:
                await message.channel.edit(name=f"entregar-{message.author.name}")
                ticket_data["status"] = "delivery_pending"
            except Exception as e:
                logging.error(f"Não foi possível renomear o canal {message.channel.id}: {e}")
            return

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

        if status == "awaiting_product_choice":
            product_category = ticket_data.get("product_name")
            product_info = PRODUCTS_DATA.get(product_category, {})
            user_choice = message.content.strip()
            user_choice_num = re.sub(r'[^0-9]', '', user_choice)
            matched_item = None
            for item_name, price in product_info.get("prices", {}).items():
                item_name_num = re.sub(r'[^0-9]', '', item_name)
                if user_choice.lower() == item_name.lower() or (user_choice_num and user_choice_num == item_name_num):
                    matched_item = item_name
                    break
            
            if matched_item:
                is_vip = ticket_data.get("is_vip", False)
                price = product_info["prices"][matched_item]
                if product_category == "Robux" and is_vip and matched_item in product_info.get("vip_discount", {}):
                    price -= product_info["vip_discount"][matched_item]
                ticket_data.update({"status": "awaiting_payment", "final_price": price, "item_name": matched_item})
                await message.channel.send(f"Ótima escolha! O valor para **{matched_item}** é de **R$ {price:.2f}**.")
                pix_embed = discord.Embed(title="Pagamento via PIX", description="Use o QR Code acima ou a chave **Copia e Cola** enviada abaixo.", color=ROSE_COLOR).set_footer(text="Após pagar, por favor, envie o comprovante neste chat.").set_image(url=QR_CODE_URL)
                await message.channel.send(embed=pix_embed)
                await message.channel.send(f"`{PIX_KEY_MANUAL}`")
            else:
                await message.channel.send("Não encontrei este item. Por favor, digite o nome ou o valor exatamente como está na tabela (ex: `1000 Robux` ou `1000`).")
            return

async def setup(bot: commands.Bot):
    await bot.add_cog(Vendas(bot))
