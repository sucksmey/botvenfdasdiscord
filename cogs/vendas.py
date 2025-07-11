# cogs/vendas.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
import math
import re
from datetime import datetime
import config
import database

# --- FUNÇÕES HELPER ---
async def proceed_with_sale(channel: discord.TextChannel, user: discord.Member, selected_product: str):
    product_info = config.PRODUCTS_DATA[selected_product]
    embed = discord.Embed(title=f"Itens para: {selected_product} {product_info['emoji']}", color=config.ROSE_COLOR)
    embed.set_thumbnail(url=config.IMAGE_URL_FOR_EMBEDS)
    status = "unknown"
    is_vip = any(role.id == config.VIP_ROLE_ID for role in user.roles)

    price_lines = []
    if product_info.get("prices"):
        for item, price in product_info["prices"].items():
            final_price = price
            if selected_product == "Robux":
                vip_price = product_info.get("vip_prices", {}).get(item)
                if is_vip and vip_price:
                    final_price = vip_price
            
            if config.CURRENT_DISCOUNT > 0:
                discounted_price = final_price * (1 - (config.CURRENT_DISCOUNT / 100))
                price_lines.append(f"**{item}**: ~~R$ {final_price:.2f}~~ → **R$ {discounted_price:.2f}** ({config.CURRENT_DISCOUNT}% OFF)")
            else:
                price_lines.append(f"**{item}**: R$ {final_price:.2f}" + (" (Preço VIP ✨)" if final_price != price else ""))
        
        prices_text = "\n".join(price_lines)
        if selected_product == "Robux":
            embed.description = ("Confira nossos pacotes ou **digite qualquer outro valor que desejar** (ex: `2500`).")
            embed.add_field(name="Pacotes Padrão", value=prices_text, inline=False)
            status = "awaiting_robux_choice"
        else:
            embed.description = ("Confira nossos preços e **digite o nome exato ou valor do item**.")
            embed.add_field(name="Tabela de Preços", value=prices_text, inline=False)
            status = "awaiting_product_choice"
    else:
        embed.description = ("Um de nossos atendentes irá te ajudar em breve para fazer o orçamento.")
        status = "awaiting_human"
    
    embed.add_field(name="Formas de Pagamento", value="> **Pix, Boleto e Cartão de Crédito**", inline=False)
    await channel.send(embed=embed)
    if channel.id in config.ONGOING_SALES_DATA:
        config.ONGOING_SALES_DATA[channel.id].update({"status": status, "is_vip": is_vip})

def calculate_robux_price(amount: int, is_vip: bool = False) -> float:
    if amount <= 0: return 0.0
    robux_prices = config.PRODUCTS_DATA["Robux"]["prices"]
    robux_vip_prices = config.PRODUCTS_DATA["Robux"].get("vip_prices", {})
    if is_vip and f"{amount} Robux" in robux_vip_prices: return robux_vip_prices[f"{amount} Robux"]
    if f"{amount} Robux" in robux_prices: return robux_prices[f"{amount} Robux"]
    base_1k_price = robux_vip_prices.get("1000 Robux", robux_prices["1000 Robux"]) if is_vip else robux_prices["1000 Robux"]
    thousands = amount // 1000
    remainder = amount % 1000
    price = thousands * base_1k_price
    if remainder > 0:
        closest_hundred = math.ceil(remainder / 100) * 100
        remainder_price = robux_prices.get(f"{closest_hundred} Robux")
        if remainder_price: price += remainder_price
        else: price += remainder * config.ROBUX_PRICE_PER_UNIT
    return round(price, 2)

# --- VIEWS (Interfaces com Botões e Menus) ---

class PaymentMethodView(discord.ui.View):
    def __init__(self, item_name: str, price: float):
        super().__init__(timeout=None)
        self.item_name = item_name; self.price = price
        self.pix_button.custom_id = f"pix_btn_{int(datetime.now().timestamp())}"
        self.boleto_button.custom_id = f"boleto_btn_{int(datetime.now().timestamp())}"
        self.card_button.custom_id = f"card_btn_{int(datetime.now().timestamp())}"
    async def handle_pix_payment(self, interaction: discord.Interaction):
        ticket_data = config.ONGOING_SALES_DATA.get(interaction.channel.id)
        if not ticket_data: return
        ticket_data.update({"status": "awaiting_payment", "final_price": self.price, "item_name": self.item_name, "payment_method": "PIX"})
        pix_embed = discord.Embed(title="Pagamento via PIX", description="Use o QR Code acima ou a chave PIX (E-mail) enviada abaixo.", color=config.ROSE_COLOR).set_footer(text="Após pagar, envie o comprovante.").set_image(url=config.QR_CODE_URL)
        await interaction.response.send_message(embed=pix_embed)
        await interaction.channel.send(config.PIX_KEY_MANUAL)
    async def handle_manual_payment(self, interaction: discord.Interaction, method: str):
        ticket_data = config.ONGOING_SALES_DATA.get(interaction.channel.id)
        if not ticket_data: return
        ticket_data.update({"status": "awaiting_human_payment", "payment_method": method})
        handler = interaction.client.get_user(config.ROBUX_DELIVERY_USER_ID)
        mention = handler.mention if handler else f"<@{config.ROBUX_DELIVERY_USER_ID}>"
        await interaction.response.send_message(f"Certo! O atendente {mention} irá te enviar o link para **{method}** em breve.")
    @discord.ui.button(label="PIX", style=discord.ButtonStyle.primary, emoji="📲")
    async def pix_button(self, i: discord.Interaction, b: discord.ui.Button):
        for item in self.children: item.disabled = True
        await i.message.edit(view=self); await self.handle_pix_payment(i)
    @discord.ui.button(label="Boleto", style=discord.ButtonStyle.secondary, emoji="📄")
    async def boleto_button(self, i: discord.Interaction, b: discord.ui.Button):
        for item in self.children: item.disabled = True
        await i.message.edit(view=self); await self.handle_manual_payment(i, "Boleto")
    @discord.ui.button(label="Cartão de Crédito", style=discord.ButtonStyle.secondary, emoji="💳")
    async def card_button(self, i: discord.Interaction, b: discord.ui.Button):
        for item in self.children: item.disabled = True
        await i.message.edit(view=self); await self.handle_manual_payment(i, "Cartão de Crédito")

class TermsConfirmationView(discord.ui.View):
    def __init__(self, selected_product: str):
        super().__init__(timeout=None); self.selected_product = selected_product
        self.add_item(discord.ui.Button(label="Ler Termos de Serviço", style=discord.ButtonStyle.link, url=config.TERMS_URL, row=1))
    @discord.ui.button(label="Concordo e quero prosseguir", style=discord.ButtonStyle.success, custom_id="terms_confirm_button")
    async def confirm_terms(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await proceed_with_sale(interaction.channel, interaction.user, self.selected_product)

class RegionalPriceConfirmationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    async def proceed_to_delivery(self, interaction: discord.Interaction):
        ticket_data = config.ONGOING_SALES_DATA.get(interaction.channel.id)
        if not ticket_data: return
        delivery_user = interaction.client.get_user(config.ROBUX_DELIVERY_USER_ID)
        mention = delivery_user.mention if delivery_user else f"<@{config.ROBUX_DELIVERY_USER_ID}>"
        await interaction.channel.send(f"Confirmado! O responsável pela entrega, {mention}, foi notificado e fará a compra em breve.")
        try:
            member = await interaction.guild.fetch_member(ticket_data['client_id'])
            await interaction.channel.edit(name=f"entregar-{member.name.split('#')[0]}")
            ticket_data["status"] = "delivery_pending"
        except Exception as e:
            logging.error(f"Não foi possível renomear o canal {interaction.channel.id}: {e}")
    @discord.ui.button(label="SIM, desativei", style=discord.ButtonStyle.success, custom_id=f"reg_price_yes_{int(datetime.now().timestamp())}")
    async def confirm_yes(self, i: discord.Interaction, b: discord.ui.Button):
        for item in self.children: item.disabled = True
        await i.message.edit(view=self); await self.proceed_to_delivery(i)
    @discord.ui.button(label="NÃO, vou desativar", style=discord.ButtonStyle.danger, custom_id=f"reg_price_no_{int(datetime.now().timestamp())}")
    async def confirm_no(self, i: discord.Interaction, b: discord.ui.Button):
        for item in self.children: item.disabled = True
        await i.message.edit(view=self); await i.response.send_message("Ok, desative a opção e **nos envie qualquer mensagem** para prosseguirmos.")
        if i.channel.id in config.ONGOING_SALES_DATA: config.ONGOING_SALES_DATA[i.channel.id]['status'] = 'awaiting_regional_price_fixed'

class ProductSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=name, emoji=data["emoji"]) for name, data in config.PRODUCTS_DATA.items()]
        super().__init__(placeholder="Escolha um jogo ou serviço para comprar...", options=options, custom_id="persistent_product_select")
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        selected_product = self.values[0]
        user = interaction.user
        guild = interaction.guild
        for channel_id, data in config.ONGOING_SALES_DATA.items():
            if data.get("client_id") == user.id:
                channel = guild.get_channel(channel_id)
                if channel:
                    await interaction.followup.send(f"Você já possui um ticket aberto em {channel.mention}!", ephemeral=True)
                    return
        admin_role = guild.get_role(config.ADMIN_ROLE_ID)
        category_id = config.CATEGORY_VENDAS_VIP_ID if any(role.id == config.VIP_ROLE_ID for role in user.roles) else config.CATEGORY_VENDAS_ID
        category = discord.utils.get(guild.categories, id=category_id)
        if not category or not admin_role:
            await interaction.followup.send("Erro de configuração do servidor.", ephemeral=True); return
        ticket_num = int(datetime.now().timestamp()) % 10000
        channel_name = f"ticket-{user.name}-{ticket_num:04d}"
        overwrites = { guild.default_role: discord.PermissionOverwrite(read_messages=False), user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True), admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)}
        new_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, topic=f"Ticket de {user.display_name} | Produto: {selected_product} | ID: {user.id}")
        config.ONGOING_SALES_DATA[new_channel.id] = {"client_id": user.id, "product_name": selected_product}
        await interaction.followup.send(f"Seu ticket foi criado em {new_channel.mention}!", ephemeral=True)
        embed = discord.Embed(title="Termos de Serviço", description=f"Olá {user.mention}! Antes de prosseguirmos, leia nossos Termos de Serviço e clique em 'Concordo' para continuar com a compra de **{selected_product}**.", color=config.ROSE_COLOR)
        await new_channel.send(content=f"<@&{config.ADMIN_ROLE_ID}>, um novo ticket foi aberto.", embed=embed, view=TermsConfirmationView(selected_product=selected_product))

class SetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None); self.add_item(ProductSelect())
    @discord.ui.button(label="Ver Tabela de Preços", style=discord.ButtonStyle.secondary, custom_id="show_all_prices_button")
    async def show_prices_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="📋 Tabela de Preços Completa", description="Aqui estão os preços de todos os nossos produtos.", color=config.ROSE_COLOR)
        for product, data in config.PRODUCTS_DATA.items():
            if data.get("prices"):
                price_list = [f"**{item}**: R$ {price:.2f}" for item, price in data["prices"].items()]
                embed.add_field(name=f"{data['emoji']} {product}", value="\n".join(price_list), inline=True)
        embed.set_footer(text="Para comprar, selecione uma opção no menu acima.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class GamepassConfirmationView(discord.ui.View):
    def __init__(self, robux_amount: int):
        super().__init__(timeout=300); self.robux_amount = robux_amount
    @discord.ui.button(label="Sim, já sei criar", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        gamepass_value = math.ceil(self.robux_amount / 0.7)
        embed = discord.Embed(title="💎 Calculadora de Game Pass", description=f"Para receber **{self.robux_amount} Robux**, crie uma Game Pass de **{gamepass_value} Robux**.\n\n**Importante:** NÃO marque preços regionais.\n\nEnvie o link da Game Pass aqui.", color=config.ROSE_COLOR)
        await interaction.response.send_message(embed=embed)
        if interaction.channel.id in config.ONGOING_SALES_DATA: config.ONGOING_SALES_DATA[interaction.channel.id]['status'] = 'awaiting_gamepass_link'
    @discord.ui.button(label="Não, preciso de ajuda", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        gamepass_value = math.ceil(self.robux_amount / 0.7)
        embed = discord.Embed(title="📄 Tutorial e Cálculo da Game Pass", description=f"Assista a este vídeo para aprender:\n{config.TUTORIAL_GAMEPASS_URL}\n\nDepois, crie uma Game Pass de **{gamepass_value} Robux** e envie o link aqui.", color=config.ROSE_COLOR)
        await interaction.response.send_message(embed=embed)
        if interaction.channel.id in config.ONGOING_SALES_DATA: config.ONGOING_SALES_DATA[interaction.channel.id]['status'] = 'awaiting_gamepass_link'

class Vendas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    @app_commands.command(name="setupvendas", description="Envia o painel de vendas permanente no canal.")
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setupvendas(self, interaction: discord.Interaction):
        embed = discord.Embed(title="✨ Bem-vindo(a) à Loja Israbuy!", description="Pronto para a melhor experiência de compra?\n\nSelecione um jogo ou serviço no menu abaixo para abrir um ticket.", color=config.ROSE_COLOR)
        await interaction.response.send_message("Painel de vendas enviado!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=SetupView())
    @app_commands.command(name="calculadora", description="Calcula o valor de uma Game Pass.")
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    async def calculadora(self, interaction: discord.Interaction, robux: int):
        if robux <= 0:
            await interaction.response.send_message("A quantidade de Robux deve ser positiva.", ephemeral=True); return
        gamepass_value = math.ceil(robux / 0.7)
        embed = discord.Embed(title="🧮 Calculadora de Game Pass", description=f"Para receber **{robux} Robux**, crie uma Game Pass de **{gamepass_value} Robux**.", color=config.ROSE_COLOR)
        await interaction.response.send_message(embed=embed)
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not isinstance(message.channel, discord.TextChannel) or not message.guild: return
        ticket_data = config.ONGOING_SALES_DATA.get(message.channel.id)
        if not ticket_data: return
        status = ticket_data.get("status")
        if status in ['being_attended_by_human', 'awaiting_human_payment']: return
        if status == "awaiting_gamepass_link" and ("roblox.com/game-pass/" in message.content or "ro.blox.com/Ebh5" in message.content):
            ticket_data['gamepass_link'] = message.content
            ticket_data['status'] = 'awaiting_regional_price_confirm'
            embed = discord.Embed(title="⚠️ Verificação Final", description="Para garantir o valor correto, precisamos de uma última confirmação.", color=discord.Color.orange())
            embed.add_field(name="Você deixou DESATIVADO os preços regionais?", value=("Se ativados, você receberá menos Robux e a loja não se responsabiliza.\n\n'**SIM**' confirma que **DESATIVOU**."))
            await message.channel.send(embed=embed, view=RegionalPriceConfirmationView())
            return
        if status == "awaiting_regional_price_fixed":
            class MockInteraction:
                def __init__(self, channel, client, guild): self.channel, self.client, self.guild = channel, client, guild
            await RegionalPriceConfirmationView().proceed_to_delivery(MockInteraction(message.channel, self.bot, message.guild)); return
        if status == "awaiting_vip_payment" and message.attachments:
            await message.channel.send(f"Obrigado! Seu comprovante VIP foi recebido. Um <@&{config.ADMIN_ROLE_ID}> irá aprovar em breve.")
            ticket_data['status'] = 'awaiting_vip_approval'; return
        if status == "awaiting_payment" and message.attachments:
            await message.channel.send(f"Obrigado! Seu comprovante foi recebido e está sendo processado.")
            try:
                client_role = message.guild.get_role(config.CLIENT_ROLE_ID)
                if client_role: await message.author.add_roles(client_role, reason="Iniciou uma compra.")
            except Exception as e:
                logging.error(f"Não foi possível adicionar o cargo de cliente: {e}")
            if ticket_data.get("product_name") == "Robux":
                item_name = ticket_data.get("item_name", "0 Robux")
                robux_amount = int(re.sub(r'[^0-9]', '', item_name))
                if robux_amount > 0:
                    embed = discord.Embed(title="Entrega de Robux", description="Para a entrega, precisamos que crie uma Game Pass. Já sabe como fazer?", color=config.ROSE_COLOR)
                    await message.channel.send(embed=embed, view=GamepassConfirmationView(robux_amount=robux_amount))
                    ticket_data["status"] = "awaiting_gamepass_info"
                else:
                    await message.channel.send(f"<@&{config.ADMIN_ROLE_ID}>, não consegui determinar a quantidade de Robux.")
                    ticket_data["status"] = "delivery_pending"
            else:
                await message.channel.send(f"Sua compra de **{ticket_data.get('item_name')}** está em processamento. Um <@&{config.ADMIN_ROLE_ID}> irá finalizar a entrega.")
                ticket_data["status"] = "delivery_pending"
            return
        if status in ["awaiting_robux_choice", "awaiting_product_choice"]:
            is_vip = ticket_data.get("is_vip", False)
            price, item_name = None, None
            if status == "awaiting_robux_choice":
                try:
                    amount = int(re.sub(r'[^0-9]', '', message.content.strip()))
                    if amount <= 0: raise ValueError()
                    price = calculate_robux_price(amount, is_vip)
                    item_name = f"{amount} Robux"
                except (ValueError, TypeError):
                    await message.channel.send("Não entendi o valor. Por favor, digite um número (ex: `9500`)."); return
            else:
                product_category = ticket_data.get("product_name")
                product_info = config.PRODUCTS_DATA.get(product_category, {})
                user_choice, user_choice_num = message.content.strip(), re.sub(r'[^0-9]', '', message.content.strip())
                for p_name, p_price in product_info.get("prices", {}).items():
                    p_name_num = re.sub(r'[^0-9]', '', p_name)
                    if user_choice.lower() == p_name.lower() or (user_choice_num and user_choice_num == p_name_num):
                        item_name, price = p_name, p_price; break
                if not item_name: await message.channel.send("Não encontrei este item. Por favor, digite o nome ou valor da tabela."); return
            
            if config.CURRENT_DISCOUNT > 0:
                price = round(price * (1 - (config.CURRENT_DISCOUNT / 100)), 2)
                item_name += f" (c/ {config.CURRENT_DISCOUNT}% OFF)"

            ticket_data.update({"final_price": price, "item_name": item_name})
            payment_embed = discord.Embed(title=f"Produto: {item_name} | Valor Final: R$ {price:.2f}", description="Qual será a forma de pagamento?", color=config.ROSE_COLOR)
            await message.channel.send(embed=payment_embed, view=PaymentMethodView(item_name, price))
            ticket_data["status"] = "awaiting_payment_method_selection"
            return

async def setup(bot: commands.Bot):
    await bot.add_cog(Vendas(bot))
