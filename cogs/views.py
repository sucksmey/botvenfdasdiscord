# cogs/views.py
import discord
import config
from .helpers import get_current_discount, apply_discount, generate_pix_embed

# --- Modals ---

class ReviewModal(discord.ui.Modal, title="Avalie nosso Atendimento"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    rating = discord.ui.TextInput(
        label="Nota (de 1 a 10)",
        placeholder="Ex: 10",
        min_length=1,
        max_length=2,
        required=True
    )
    comment = discord.ui.TextInput(
        label="Comentário (opcional)",
        style=discord.TextStyle.long,
        placeholder="Deixe seu feedback sobre a compra...",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        review_channel = self.bot.get_channel(config.REVIEW_CHANNEL_ID)
        embed = discord.Embed(
            title="⭐ Nova Avaliação Recebida!",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar.url)
        embed.add_field(name="Nota", value=self.rating.value, inline=True)
        embed.add_field(name="Comentário", value=self.comment.value or "Nenhum comentário.", inline=False)
        
        if review_channel:
            await review_channel.send(embed=embed)
        await interaction.response.send_message("Obrigado pela sua avaliação!", ephemeral=True)

# --- Views ---

class SalesPanelView(discord.ui.View):
    # LÓGICA CORRIGIDA E ROBUSTA
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

        # 1. Gera a lista de opções de forma segura
        options = [
            discord.SelectOption(label=category, emoji=details.get("emoji", "⚫"))
            for category, details in config.PRODUCTS.items() if details.get("prices")
        ]

        # 2. SÓ ADICIONA O MENU SE A LISTA DE OPÇÕES NÃO ESTIVER VAZIA
        if options:
            select_menu = discord.ui.Select(
                custom_id="category_select",
                placeholder="Escolha um jogo ou serviço para comprar...",
                options=options
            )
            select_menu.callback = self.select_callback # Define a função de callback
            self.add_item(select_menu)

        # 3. Adiciona o botão de qualquer maneira
        price_button = discord.ui.Button(
            label="Ver Tabela de Preços",
            style=discord.ButtonStyle.secondary,
            custom_id="price_table_button"
        )
        price_button.callback = self.price_table_callback # Define a função de callback
        self.add_item(price_button)

    async def select_callback(self, interaction: discord.Interaction):
        # A resposta do defer agora é privada para não poluir o chat
        await interaction.response.defer(ephemeral=True)
        
        # Pega a categoria que o usuário selecionou no menu
        category = interaction.data['values'][0]
        product_view = ProductSelectView(self.bot, category)
        
        await interaction.followup.send("Agora, escolha o produto desejado:", view=product_view, ephemeral=True)

    async def price_table_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(view=PriceTableView(self.bot), ephemeral=True)


class VIPPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
    
    @discord.ui.button(label="✨ Tornar-se VIP!", style=discord.ButtonStyle.success, custom_id="become_vip_button")
    async def become_vip_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(config.CATEGORY_VENDAS_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.get_role(config.ADMIN_ROLE_ID): discord.PermissionOverwrite(read_messages=True)
        }
        channel_name = f"vip-{interaction.user.name}-{interaction.user.id}"
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        await interaction.response.send_message(f"Seu ticket VIP foi criado em {ticket_channel.mention}!", ephemeral=True)
        
        vip_price = 49.90
        embed_pix = await generate_pix_embed(vip_price)
        await ticket_channel.send(
            f"Olá {interaction.user.mention}! Bem-vindo ao seu ticket de compra VIP.\n"
            f"O valor da assinatura é **R$ {vip_price:.2f}**.",
            embed=embed_pix
        )


class ClientPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
    
    @discord.ui.button(label="Ver Minhas Compras", style=discord.ButtonStyle.primary, custom_id="my_purchases_button")
    async def my_purchases_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        command = self.bot.tree.get_command('minhascompras', guild=discord.Object(id=config.GUILD_ID))
        tickets_cog = self.bot.get_cog("Tickets")
        if command and tickets_cog:
            await command.callback(tickets_cog, interaction)


class ProductSelectView(discord.ui.View):
    def __init__(self, bot, category: str):
        super().__init__(timeout=180)
        self.bot = bot
        self.category = category
        
        product_prices = config.PRODUCTS[category]["prices"]
        options = [discord.SelectOption(label=name) for name in product_prices.keys()]

        select_menu = discord.ui.Select(
            custom_id="product_select_dropdown",
            placeholder=f"Escolha um item de {self.category}...",
            options=options[:25]
        )
        select_menu.callback = self.product_select_callback
        self.add_item(select_menu)

    async def product_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer() 

        product_name = interaction.data['values'][0]
        base_price = config.PRODUCTS[self.category]["prices"][product_name]
        
        discount = await get_current_discount(self.bot.pool)
        final_price = await apply_discount(self.category, base_price, discount)
        
        confirm_view = PurchaseConfirmView(
            self.bot,
            product=product_name,
            price=final_price
        )
        
        message = f"Você selecionou: **{product_name}**\nPreço: `R$ {base_price:.2f}`"
        if discount > 0 and self.category == "Robux":
            message += f"\nDesconto: `{discount}%`\n**Preço Final: `R$ {final_price:.2f}`**"
        else:
             message += f"\n**Preço Final: `R$ {final_price:.2f}`**"
            
        message += "\n\nClique em **Confirmar** para criar um ticket de compra."
        
        await interaction.edit_original_response(content=message, view=confirm_view)


class PurchaseConfirmView(discord.ui.View):
    def __init__(self, bot, product: str, price: float):
        super().__init__(timeout=180)
        self.bot = bot
        self.product = product
        self.price = price

    @discord.ui.button(label="Confirmar Compra", style=discord.ButtonStyle.success, custom_id="confirm_purchase")
    async def confirm_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        
        guild = interaction.guild
        category = guild.get_channel(config.CATEGORY_VENDAS_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.get_role(config.ADMIN_ROLE_ID): discord.PermissionOverwrite(read_messages=True)
        }
        channel_name = f"ticket-{self.product[:20]}-{interaction.user.id}"
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        tickets_cog = self.bot.get_cog("Tickets")
        if tickets_cog:
            tickets_cog.ticket_data[ticket_channel.id] = {'product': self.product, 'price': self.price}
        
        await interaction.followup.send(f"Seu ticket foi criado em {ticket_channel.mention}!", ephemeral=True)
        
        embed_pix = await generate_pix_embed(self.price)
        await ticket_channel.send(
            f"Olá {interaction.user.mention}! Você está comprando **{self.product}**.",
            embed=embed_pix
        )


class PriceTableView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=180)
        self.bot = bot
        options = [
            discord.SelectOption(label=category, emoji=details.get("emoji", "⚫"))
            for category, details in config.PRODUCTS.items() if details.get("prices")
        ]
        
        if options:
            select_menu = discord.ui.Select(
                custom_id="price_table_select",
                placeholder="Ver preços de qual categoria?",
                options=options
            )
            select_menu.callback = self.price_table_select_callback
            self.add_item(select_menu)

    async def price_table_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        category = interaction.data['values'][0]
        prices = config.PRODUCTS[category]["prices"]
        
        embed = discord.Embed(title=f"Tabela de Preços - {category}", color=discord.Color.random())
        description = ""
        for name, price in prices.items():
            description += f"**{name}**: R$ {price:.2f}\n"
        
        embed.description = description
        await interaction.edit_original_response(embed=embed, view=self)

class TutorialGamepassView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.Button(label="Ver Tutorial em Vídeo", url="http://www.youtube.com/watch?v=B-LQU3J24pI"))
