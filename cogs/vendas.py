# cogs/vendas.py
import discord
from discord.ext import commands, app_commands
import logging, math, re
from datetime import datetime
import config, database

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
                if is_vip and vip_price: final_price = vip_price
            
            if config.CURRENT_DISCOUNT > 0:
                discounted_price = final_price * (1 - (config.CURRENT_DISCOUNT / 100))
                price_lines.append(f"**{item}**: ~~R$ {final_price:.2f}~~ → **R$ {discounted_price:.2f}** ({config.CURRENT_DISCOUNT}% OFF)")
            else:
                price_lines.append(f"**{item}**: R$ {final_price:.2f}" + (" (Preço VIP ✨)" if final_price != price else ""))
        prices_text = "\n".join(price_lines)
        if selected_product == "Robux":
            embed.description = ("Confira nossos pacotes ou **digite qualquer valor que desejar** (ex: `2500`).")
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

class TermsConfirmationView(discord.ui.View):
    def __init__(self, selected_product: str):
        super().__init__(timeout=None); self.selected_product = selected_product
        self.add_item(discord.ui.Button(label="Ler Termos de Serviço", style=discord.ButtonStyle.link, url=config.TERMS_URL, row=1))
        self.children[0].custom_id = f"terms_btn_{int(datetime.now().timestamp())}"
    @discord.ui.button(label="Concordo e quero prosseguir", style=discord.ButtonStyle.success, custom_id="terms_confirm_button_main")
    async def confirm_terms(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await proceed_with_sale(interaction.channel, interaction.user, self.selected_product)

class RegionalPriceConfirmationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.children[0].custom_id = f"reg_price_yes_{int(datetime.now().timestamp())}"
        self.children[1].custom_id = f"reg_price_no_{int(datetime.now().timestamp())}"
    async def proceed_to_delivery(self, interaction: discord.Interaction):
        #...
    @discord.ui.button(label="SIM, desativei", style=discord.ButtonStyle.success)
    async def confirm_yes(self, i: discord.Interaction, b: discord.ui.Button):
        for item in self.children: item.disabled = True
        await i.message.edit(view=self); await self.proceed_to_delivery(i)
    @discord.ui.button(label="NÃO, vou desativar", style=discord.ButtonStyle.danger)
    async def confirm_no(self, i: discord.Interaction, b: discord.ui.Button):
        for item in self.children: item.disabled = True
        await i.message.edit(view=self); await i.response.send_message("Ok, desative a opção e **nos envie qualquer mensagem** para prosseguirmos.")
        if i.channel.id in config.ONGOING_SALES_DATA: config.ONGOING_SALES_DATA[i.channel.id]['status'] = 'awaiting_regional_price_fixed'

class ProductSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=name, emoji=data["emoji"]) for name, data in config.PRODUCTS_DATA.items()]
        super().__init__(placeholder="Escolha um jogo ou serviço para comprar...", options=options, custom_id="persistent_product_select")
    async def callback(self, interaction: discord.Interaction):
        # ...

class SetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None); self.add_item(ProductSelect())
    @discord.ui.button(label="Ver Tabela de Preços", style=discord.ButtonStyle.secondary, custom_id="show_all_prices_button")
    async def show_prices_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ...

class GamepassConfirmationView(discord.ui.View):
    def __init__(self, robux_amount: int):
        super().__init__(timeout=300); self.robux_amount = robux_amount
    @discord.ui.button(label="Sim, já sei criar", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ...
    @discord.ui.button(label="Não, preciso de ajuda", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ...

def calculate_robux_price(amount: int, is_vip: bool = False) -> float:
    # ...

class Vendas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    @app_commands.command(name="setupvendas", description="Envia o painel de vendas permanente no canal.")
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def setupvendas(self, interaction: discord.Interaction):
        # ...
    @app_commands.command(name="calculadora", description="Calcula o valor de uma Game Pass.")
    @app_commands.guilds(discord.Object(id=config.GUILD_ID))
    async def calculadora(self, interaction: discord.Interaction, robux: int):
        # ...
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ...

async def setup(bot: commands.Bot):
    await bot.add_cog(Vendas(bot))
