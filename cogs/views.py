# cogs/views.py
import discord
from discord.ext import commands
import config
import traceback
import re
from .helpers import apply_discount, generate_pix_embed
from datetime import timedelta

# --- Modals ---
class ReviewModal(discord.ui.Modal, title="Avalie nosso Atendimento"):
    def __init__(self, bot, customer_id, admin_id):
        super().__init__()
        self.bot = bot
        self.customer_id = customer_id
        self.admin_id = admin_id
    nota = discord.ui.TextInput(label="Nota (de 1 a 10)", placeholder="Sua nota sincera.", min_length=1, max_length=2, required=True)
    descricao = discord.ui.TextInput(label="Descrição da Avaliação (Opcional)", style=discord.TextStyle.long, placeholder="Deixe seu comentário aqui!", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        review_channel = self.bot.get_channel(config.REVIEW_CHANNEL_ID)
        if not review_channel:
            return await interaction.followup.send("Canal de avaliações não configurado.", ephemeral=True)
        try:
            nota_int = int(self.nota.value)
            if not 0 <= nota_int <= 10: raise ValueError()
        except ValueError:
            return await interaction.followup.send("Por favor, insira uma nota válida de 0 a 10.", ephemeral=True)
        customer = await self.bot.fetch_user(self.customer_id)
        admin = await self.bot.fetch_user(self.admin_id) if self.admin_id else "N/A"
        embed = discord.Embed(
            title="⭐ Nova Avaliação de Cliente!",
            description=f"**Nota:** {self.nota.value}/10\n\n**Comentário:**\n>>> {self.descricao.value or 'Nenhum comentário.'}",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"Avaliação de {customer.display_name}", icon_url=customer.display_avatar.url)
        embed.add_field(name="Cliente", value=customer.mention, inline=True)
        embed.add_field(name="Atendente", value=admin.mention if isinstance(admin, discord.User) else admin, inline=True)
        embed.add_field(name="Entregador", value=f"<@{config.ROBUX_DELIVERY_USER_ID}>", inline=True)
        await review_channel.send(embed=embed)
        await interaction.followup.send("✅ Sua avaliação foi enviada com sucesso! Muito obrigado!", ephemeral=True)

class ReviewView(discord.ui.View):
    def __init__(self, bot, purchase_id, customer_id, admin_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.purchase_id = purchase_id
        self.customer_id = customer_id
        self.admin_id = admin_id

    @discord.ui.button(label="⭐ Avaliar Compra", style=discord.ButtonStyle.success, custom_id="review_purchase")
    async def review_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.customer_id:
            return await interaction.response.send_message("Apenas o cliente que fez a compra pode deixar uma avaliação.", ephemeral=True)
        modal = ReviewModal(self.bot, self.customer_id, self.admin_id)
        await interaction.response.send_modal(modal)

# --- Views para Fluxo de Gamepass ---
class RegionalPricingCheckView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Sim, desativei", style=discord.ButtonStyle.success, custom_id="regional_yes")
    async def sim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(
            content=f"Perfeito! O entregador <@{config.ROBUX_DELIVERY_USER_ID}> foi notificado e fará a entrega em breve.",
            view=self
        )

    @discord.ui.button(label="Não, ainda não", style=discord.ButtonStyle.danger, custom_id="regional_no")
    async def nao_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Por favor, desative os preços regionais para que a entrega possa ser feita. Assim que desativar, clique no 'Sim' acima.",
            view=self
        )

class GamepassCheckView(discord.ui.View):
    def __init__(self, robux_amount: int):
        super().__init__(timeout=None)
        self.robux_amount = robux_amount

    @discord.ui.button(label="Sim, sei criar", style=discord.ButtonStyle.primary, custom_id="gp_yes")
    async def sim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(content="Ótimo! Por favor, envie o **link** ou **ID** da sua Game Pass no chat.", view=self)

    @discord.ui.button(label="Não, preciso de ajuda", style=discord.ButtonStyle.secondary, custom_id="gp_no")
    async def nao_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        gamepass_value = int((self.robux_amount / 0.7) + 0.99)
        description = (
            "Siga os passos no vídeo para criar sua Game Pass corretamente.\n\n"
            f"**IMPORTANTE:** Você deve criar a Game Pass com o valor de **`{gamepass_value}` Robux** para receber a quantia correta.\n\n"
            "Lembre-se também de **DESATIVAR** os preços regionais. Após criar, envie o link ou ID dela aqui no chat."
        )
        tutorial_embed = discord.Embed(title="Tutorial - Criando uma Game Pass", description=description, color=discord.Color.blue())
        tutorial_embed.add_field(name="Link do Tutorial", value="[Clique aqui para assistir](http://www.youtube.com/watch?v=B-LQU3J24pI)")
        await interaction.response.edit_message(embed=tutorial_embed, view=self)

# --- View de Pagamento ---
class PaymentMethodView(discord.ui.View):
    def __init__(self, bot, product, price, original_price, discount_applied):
        super().__init__(timeout=None)
        self.bot = bot
        self.price = price
        initial_message = f"Você selecionou: **{product}**\n"
        if discount_applied:
            initial_message += f"Preço Original: `R$ {original_price:.2f}`\n"
            initial_message += f"**Preço com Desconto (1ª Compra): `R$ {price:.2f}`**\n\n"
        else:
            initial_message += f"**Preço Final: `R$ {price:.2f}`**\n\n"
        initial_message += "Por favor, escolha uma forma de pagamento:"
        self.initial_message = initial_message

    @discord.ui.button(label="PIX (Automático)", style=discord.ButtonStyle.success, emoji="📲", custom_id="pay_pix")
    async def pix_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        pix_embed = await generate_pix_embed(self.price)
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(content="", embed=pix_embed, view=self)

    @discord.ui.button(label="Boleto / Cartão", style=discord.ButtonStyle.secondary, emoji="💳", custom_id="pay_manual")
    async def manual_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(content=f"Para pagamento com Boleto ou Cartão, o <@{config.ROBUX_DELIVERY_USER_ID}> irá te atender em instantes.", view=self)

# --- View para Atalho de Venda ---
class GameSelectionView(discord.ui.View):
    def __init__(self, bot, number_amount: int, original_message: discord.Message):
        super().__init__(timeout=120)
        self.bot = bot
        self.number_amount = number_amount
        self.original_message = original_message

    async def create_ticket_and_cleanup(self, interaction: discord.Interaction, category: str):
        product_name = f"{self.number_amount} {category}"
        base_price = None
        if category == "Robux":
            prices = config.PRODUCTS.get("Robux", {}).get("prices", {})
            for name, price in prices.items():
                if str(self.number_amount) in name:
                    product_name = name
                    base_price = price
                    break
        if base_price is None:
            await interaction.response.send_message(f"Não encontrei um produto exato para `{self.number_amount} {category}`. Por favor, use o painel principal.", ephemeral=True)
            return

        for item in self.children: item.disabled = True
        await interaction.response.edit_message(content=f"Ok! Criando ticket para `{product_name}`...", view=self)
        try:
            final_price, was_discounted = await apply_discount(interaction.user, category, base_price)
            async with self.bot.pool.acquire() as conn:
                purchase_id = await conn.fetchval("INSERT INTO purchases (user_id, product_name, product_price) VALUES ($1, $2, $3) RETURNING id", interaction.user.id, product_name, final_price)
            guild = interaction.guild
            category_channel = guild.get_channel(config.CATEGORY_VENDAS_ID)
            overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True), guild.get_role(config.ADMIN_ROLE_ID): discord.PermissionOverwrite(read_messages=True)}
            channel_name_prefix = "robux" if category == "Robux" else "geral"
            ticket_channel = await guild.create_text_channel(name=f"ticket-{channel_name_prefix}-{interaction.user.name}-{interaction.user.id}", category=category_channel, overwrites=overwrites)
            tickets_cog = self.bot.get_cog("Tickets")
            if tickets_cog:
                ticket_payload = {'product': product_name, 'price': final_price, 'purchase_id': purchase_id, 'robux_amount': self.number_amount if category == "Robux" else 0}
                tickets_cog.ticket_data[ticket_channel.id] = ticket_payload
            payment_view = PaymentMethodView(self.bot, product_name, final_price, base_price, was_discounted)
            await ticket_channel.send(f"Olá {interaction.user.mention}!", embed=discord.Embed(description=payment_view.initial_message, color=0x36393F), view=payment_view)
            await self.original_message.delete()
            await interaction.message.delete()
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"😕 Ocorreu um erro ao criar o ticket: `{str(e)}`", ephemeral=True)

    @discord.ui.button(label="Robux", style=discord.ButtonStyle.primary, emoji="💎")
    async def robux_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket_and_cleanup(interaction, "Robux")
    
    @discord.ui.button(label="Valorant", style=discord.ButtonStyle.secondary, emoji="💢")
    async def valorant_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Atalho para Valorant ainda não implementado. Por favor, use o painel.", ephemeral=True)

    @discord.ui.button(label="Outro Jogo", style=discord.ButtonStyle.secondary, emoji="🎮")
    async def other_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Para outros jogos, por favor, use o painel de vendas principal.", ephemeral=True)

# --- Views de Setup e Fluxo Inicial ---
class SalesPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        options = [discord.SelectOption(label=category, emoji=details.get("emoji", "⚫")) for category, details in config.PRODUCTS.items() if details.get("prices")]
        if options:
            select_menu = discord.ui.Select(custom_id="category_select", placeholder="Escolha um jogo ou serviço para comprar...", options=options)
            select_menu.callback = self.select_callback
            self.add_item(select_menu)
        price_button = discord.ui.Button(label="Ver Tabela de Preços", style=discord.ButtonStyle.secondary, custom_id="price_table_button")
        price_button.callback = self.price_table_callback
        self.add_item(price_button)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=ProductSelectView(self.bot, interaction.user, interaction.data['values'][0]), ephemeral=True)

    async def price_table_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=PriceTableView(self.bot), ephemeral=True)

class ProductSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.Member, category: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.category = category
        vip_role = user.guild.get_role(config.VIP_ROLE_ID)
        is_vip = vip_role in user.roles
        all_prices = config.PRODUCTS[category].get("prices", {}).copy()
        if is_vip and "vip_prices" in config.PRODUCTS[category]:
            vip_prices = config.PRODUCTS[category].get("vip_prices", {})
            all_prices.update(vip_prices)
        options = [discord.SelectOption(label=name) for name in all_prices.keys()]
        select_menu = discord.ui.Select(custom_id="product_select_dropdown", placeholder=f"Escolha um item de {self.category}...", options=options[:25])
        select_menu.callback = self.product_select_callback
        self.add_item(select_menu)

    async def product_select_callback(self, interaction: discord.Interaction):
        product_name = interaction.data['values'][0]
        vip_role = interaction.user.guild.get_role(config.VIP_ROLE_ID)
        is_vip = vip_role in interaction.user.roles
        all_prices = config.PRODUCTS[self.category].get("prices", {}).copy()
        if is_vip and "vip_prices" in config.PRODUCTS[self.category]:
            vip_prices = config.PRODUCTS[self.category].get("vip_prices", {})
            all_prices.update(vip_prices)
        base_price = all_prices[product_name]
        view = PurchaseConfirmView(self.bot, interaction.user, self.category, product_name, base_price)
        await interaction.response.edit_message(content=f"Você selecionou **{product_name}** por **R$ {base_price:.2f}**. Clique abaixo para confirmar e abrir um ticket.", view=view)

class PurchaseConfirmView(discord.ui.View):
    def __init__(self, bot, member: discord.Member, category: str, product: str, price: float):
        super().__init__(timeout=None)
        self.bot = bot
        self.member = member
        self.category = category
        self.product = product
        self.price = price

    @discord.ui.button(label="Confirmar e Abrir Ticket", style=discord.ButtonStyle.success, custom_id="confirm_purchase")
    async def confirm_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            for item in self.children: item.disabled = True
            await interaction.response.edit_message(content="Abrindo seu ticket...", view=None)
            final_price, was_discounted = await apply_discount(self.member, self.category, self.price)
            async with self.bot.pool.acquire() as conn:
                purchase_id = await conn.fetchval("INSERT INTO purchases (user_id, product_name, product_price) VALUES ($1, $2, $3) RETURNING id", self.member.id, self.product, final_price)
            guild = interaction.guild
            category_channel = guild.get_channel(config.CATEGORY_VENDAS_ID)
            overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), self.member: discord.PermissionOverwrite(read_messages=True, send_messages=True), guild.get_role(config.ADMIN_ROLE_ID): discord.PermissionOverwrite(read_messages=True)}
            channel_name_prefix = "robux" if self.category == "Robux" else "geral"
            ticket_channel = await guild.create_text_channel(name=f"ticket-{channel_name_prefix}-{self.member.name}-{self.member.id}", category=category_channel, overwrites=overwrites)
            tickets_cog = self.bot.get_cog("Tickets")
            if tickets_cog:
                ticket_payload = {'product': self.product, 'price': final_price, 'purchase_id': purchase_id}
                if self.category == "Robux":
                    try:
                        robux_amount = int(re.search(r'\d+', self.product).group())
                        ticket_payload['robux_amount'] = robux_amount
                    except (ValueError, AttributeError): pass
                tickets_cog.ticket_data[ticket_channel.id] = ticket_payload
            payment_view = PaymentMethodView(self.bot, self.product, final_price, self.price, was_discounted)
            await ticket_channel.send(f"Olá {self.member.mention}!", embed=discord.Embed(description=payment_view.initial_message, color=0x36393F), view=payment_view)
            await interaction.edit_original_response(content=f"Ticket criado: {ticket_channel.mention}", view=None)
        except Exception as e:
            traceback.print_exc()
            error_message = f"😕 Ocorreu um erro ao criar o ticket.\n**Causa provável:** O bot não tem permissão para criar canais nesta categoria.\n\n**Erro técnico:** `{str(e)}`"
            await interaction.edit_original_response(content=error_message, view=None)

class VIPPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
    
    @discord.ui.button(label="✨ Tornar-se VIP!", style=discord.ButtonStyle.success, custom_id="become_vip_button")
    async def become_vip_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        vip_benefits = (
            "Ao se tornar VIP, você desbloqueia benefícios exclusivos:\n"
            f"• **Preço Reduzido:** Compre 1000 Robux por apenas R$ 36.90.\n"
            f"• **Limite Mensal:** Esta oferta pode ser usada até 2 vezes por mês.\n\n"
            f"O valor da assinatura VIP é **R$ {config.VIP_PRICE:.2f}**. Deseja continuar e abrir um ticket de compra?"
        )
        confirm_view = VIPConfirmView(self.bot)
        await interaction.followup.send(content=vip_benefits, view=confirm_view, ephemeral=True)

class VIPConfirmView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot

    @discord.ui.button(label="Sim, continuar", style=discord.ButtonStyle.success)
    async def confirm_vip(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            for item in self.children: item.disabled = True
            await interaction.response.edit_message(content="Criando seu ticket VIP...", view=self)
            guild = interaction.guild
            category_channel = guild.get_channel(config.CATEGORY_VENDAS_ID)
            overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True), guild.get_role(config.ADMIN_ROLE_ID): discord.PermissionOverwrite(read_messages=True)}
            ticket_channel = await guild.create_text_channel(name=f"vip-compra-{interaction.user.name}-{interaction.user.id}", category=category_channel, overwrites=overwrites)
            pix_embed = await generate_pix_embed(config.VIP_PRICE)
            await ticket_channel.send(f"Olá {interaction.user.mention}! Para concluir a compra do seu VIP, faça o pagamento de **R$ {config.VIP_PRICE:.2f}**.", embed=pix_embed)
            await interaction.edit_original_response(content=f"Ticket VIP criado em {ticket_channel.mention}", view=None)
        except Exception as e:
            traceback.print_exc()
            error_message = f"😕 Ocorreu um erro ao criar o ticket VIP.\n**Erro técnico:** `{str(e)}`"
            await interaction.edit_original_response(content=error_message, view=None)

class PriceTableView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        options = [discord.SelectOption(label=category, emoji=details.get("emoji", "⚫")) for category, details in config.PRODUCTS.items() if details.get("prices")]
        if options:
            select_menu = discord.ui.Select(custom_id="price_table_select", placeholder="Ver preços de qual categoria?", options=options)
            select_menu.callback = self.price_table_select_callback
            self.add_item(select_menu)

    async def price_table_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        category = interaction.data['values'][0]
        prices = config.PRODUCTS[category]["prices"]
        embed = discord.Embed(title=f"Tabela de Preços - {category}", color=discord.Color.random())
        description = ""
        for name, price in prices.items():
            description += f"**{name}**: R$ {price:.2f}\n"
        embed.description = description
        await interaction.followup.send(embed=embed, ephemeral=True)

class TutorialGamepassView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Ver Tutorial em Vídeo", url="http://www.youtube.com/watch?v=B-LQU3J24pI"))

class ClientPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Ver Minhas Compras", style=discord.ButtonStyle.primary, custom_id="my_purchases_button")
    async def my_purchases_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        async with self.bot.pool.acquire() as conn:
            purchases = await conn.fetch("SELECT product_name, product_price, purchase_date FROM purchases WHERE user_id = $1 ORDER BY purchase_date DESC", interaction.user.id)
        if not purchases:
            embed = discord.Embed(title="👤 Sua Área de Cliente", description="Você ainda não fez nenhuma compra.", color=0x3498DB)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(title="👤 Seu Histórico de Compras", color=0x3498DB)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        description = ""
        for p in purchases:
            purchase_date_br = p['purchase_date'] - timedelta(hours=3)
            description += f"**Produto:** {p['product_name']}\n"
            description += f"**Valor:** R$ {p['product_price']:.2f}\n"
            description += f"**Data:** {purchase_date_br.strftime('%d/%m/%Y às %H:%M')}\n---\n"
        embed.description = description[:4096]
        await interaction.followup.send(embed=embed, ephemeral=True)
