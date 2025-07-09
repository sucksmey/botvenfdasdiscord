# cogs/cliente.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import *
import database
from sqlalchemy import update, select
from datetime import datetime

# --- FUNÇÃO HELPER PARA ENVIAR A AVALIAÇÃO FINAL ---
async def post_review_embed(interaction: discord.Interaction, transaction_id: int):
    async with database.engine.connect() as conn:
        query = database.transactions.select().where(database.transactions.c.id == transaction_id)
        result = await conn.execute(query)
        transaction = result.first()
    
    if not transaction or not transaction.review_rating:
        return

    review_channel = interaction.client.get_channel(REVIEW_CHANNEL_ID)
    if not review_channel:
        logging.error("Canal de avaliação (REVIEW_CHANNEL_ID) não encontrado.")
        return

    try:
        user = await interaction.client.fetch_user(transaction.user_id)
        handler = await interaction.client.fetch_user(transaction.handler_admin_id) if transaction.handler_admin_id else interaction.user
        delivery = await interaction.client.fetch_user(transaction.delivery_admin_id) if transaction.delivery_admin_id else interaction.user
    except discord.NotFound:
        logging.error("Não foi possível encontrar um dos usuários para postar a avaliação.")
        user = handler = delivery = "Usuário não encontrado"

    embed = discord.Embed(title="🌟 Nova Avaliação de Cliente!", color=discord.Color.gold(), timestamp=datetime.now(BR_TIMEZONE))
    embed.set_author(name=user.name if isinstance(user, discord.User) else user, icon_url=user.display_avatar.url if isinstance(user, discord.User) else None)
    
    embed.add_field(name="Cliente", value=user.mention if isinstance(user, discord.User) else user, inline=True)
    embed.add_field(name="Atendente", value=handler.mention if isinstance(handler, discord.User) else handler, inline=True)
    embed.add_field(name="Entregador", value=delivery.mention if isinstance(delivery, discord.User) else delivery, inline=True)
    
    embed.add_field(name="Produto Comprado", value=transaction.product_name, inline=True)
    embed.add_field(name="Método de Pagamento", value=transaction.payment_method or "PIX", inline=True)
    embed.add_field(name="Nota", value=f"**{transaction.review_rating} / 10** ✨", inline=True)

    if transaction.review_text and transaction.review_text != "Nenhum comentário.":
        embed.add_field(name="Comentário do Cliente", value=f"```{transaction.review_text}```", inline=False)
        
    await review_channel.send(embed=embed)


# --- MODAL PARA ESCREVER A AVALIAÇÃO ---
class ReviewModal(discord.ui.Modal, title="Deixe seu Feedback"):
    def __init__(self, transaction_id: int):
        super().__init__()
        self.transaction_id = transaction_id

    comment = discord.ui.TextInput(
        label="Qual nota você daria para o atendimento?",
        style=discord.TextStyle.short,
        placeholder="Digite sua nota de 1 a 10...",
        required=True,
        max_length=2
    )

    feedback = discord.ui.TextInput(
        label="Deixe um comentário (opcional)",
        style=discord.TextStyle.paragraph,
        placeholder="Gostei muito do atendimento, foi rápido e...",
        required=False,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rating = int(self.comment.value)
            if not 1 <= rating <= 10:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Por favor, insira uma nota válida de 1 a 10.", ephemeral=True)
            return

        review_text = self.feedback.value or "Nenhum comentário."
        
        async with database.engine.connect() as conn:
            query = update(database.transactions).where(database.transactions.c.id == self.transaction_id).values(
                review_rating=rating,
                review_text=review_text
            )
            await conn.execute(query)
            await conn.commit()
            
        await interaction.response.send_message("Sua avaliação foi enviada com sucesso! Muito obrigado.", ephemeral=True)
        await post_review_embed(interaction, self.transaction_id)
        
        original_message = await interaction.original_response()
        view = discord.ui.View.from_message(original_message)
        for child in view.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
                break
        await original_message.edit(view=view)


# --- VIEW PARA INICIAR A AVALIAÇÃO ---
class StartReviewView(discord.ui.View):
    def __init__(self, transaction_id: int):
        super().__init__(timeout=None)
        self.transaction_id = transaction_id
        # Define um custom_id único para o botão para que o bot possa encontrá-lo
        self.children[0].custom_id = f"start_review_button_{transaction_id}"

    @discord.ui.button(label="⭐ Avaliar Atendimento", style=discord.ButtonStyle.primary)
    async def start_review_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with database.engine.connect() as conn:
            query = select(database.transactions.c.user_id).where(database.transactions.c.id == self.transaction_id)
            result = await conn.execute(query)
            owner_id = result.scalar_one_or_none()

        if interaction.user.id != owner_id:
            await interaction.response.send_message("Apenas o cliente que realizou esta compra pode avaliá-la.", ephemeral=True)
            return
            
        await interaction.response.send_modal(ReviewModal(transaction_id=self.transaction_id))


# --- ÁREA DO CLIENTE E VIP ---

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
        for purchase in user_purchases[:10]:
            purchase_date = discord.utils.format_dt(purchase.timestamp, style='f')
            description_lines.append(f"**Produto:** {purchase.product_name}\n**Valor:** R$ {purchase.price:.2f}\n**Data:** {purchase_date}\n--------------------")
            total_spent += purchase.price
        
        embed.description = "\n".join(description_lines)
        embed.set_footer(text=f"Total gasto: R$ {total_spent:.2f} | Mostrando as últimas {len(user_purchases[:10])} de {len(user_purchases)} compras.")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Erro ao buscar histórico de compras para {interaction.user.id}: {e}")
        await interaction.followup.send("Ocorreu um erro ao tentar buscar seu histórico. Por favor, tente novamente mais tarde.", ephemeral=True)

class CustomerAreaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ver Minhas Compras", style=discord.ButtonStyle.primary, custom_id="view_my_purchases_button", emoji="📜")
    async def view_purchases_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_purchase_history(interaction)

class VipPurchaseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✨ Tornar-se VIP!", style=discord.ButtonStyle.success, custom_id="purchase_vip_button")
    async def purchase_vip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        user = interaction.user
        guild = interaction.guild
        vip_role = guild.get_role(VIP_ROLE_ID)
        if vip_role and vip_role in user.roles:
            await interaction.followup.send("Você já é um membro VIP!", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, id=CATEGORY_VENDAS_VIP_ID)
        admin_role = guild.get_role(ADMIN_ROLE_ID)
        if not category or not admin_role:
            await interaction.followup.send("Erro de configuração do servidor.", ephemeral=True)
            return

        channel_name = f"vip-{user.name}"
        overwrites = { guild.default_role: discord.PermissionOverwrite(read_messages=False), user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True), admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        new_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, topic=f"Ticket VIP de {user.display_name} | ID: {user.id}")
        
        ONGOING_SALES_DATA[new_channel.id] = {"client_id": user.id, "product_name": "Assinatura VIP", "status": "awaiting_vip_payment", "final_price": VIP_PRICE}
        await interaction.followup.send(f"Seu ticket para comprar VIP foi criado em {new_channel.mention}!", ephemeral=True)
        
        embed = discord.Embed(title="💎 Compra de Assinatura VIP", description=f"Olá {user.mention}! Para se tornar VIP, o valor é de **R$ {VIP_PRICE:.2f}**.", color=ROSE_COLOR)
        embed.add_field(name="Benefícios", value="- Descontos exclusivos em Robux\n- Acesso a canais especiais\n- Sorteios e muito mais!", inline=False)
        pix_embed = discord.Embed(title="Pagamento via PIX", description="Use o QR Code acima ou a chave **Copia e Cola** enviada abaixo.", color=ROSE_COLOR).set_footer(text="Após pagar, por favor, envie o comprovante neste chat.").set_image(url=QR_CODE_URL)
        
        await new_channel.send(content=f"<@&{ADMIN_ROLE_ID}>, um novo pedido de VIP foi iniciado.", embed=embed)
        await new_channel.send(embed=pix_embed)
        await new_channel.send(f"`{PIX_KEY_MANUAL}`")

class Cliente(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="avaliacao", description="[Admin] Envia o pedido de avaliação para o cliente neste ticket.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def request_review(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not channel.name.startswith("entregue-"):
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket arquivado.", ephemeral=True)
            return
        
        async with database.engine.connect() as conn:
            query = select(database.transactions.c.id).where(database.transactions.c.channel_id == channel.id).order_by(database.transactions.c.id.desc()).limit(1)
            result = await conn.execute(query)
            transaction_id = result.scalar_one_or_none()

        if not transaction_id:
            await interaction.response.send_message("Não encontrei uma compra registrada para este ticket.", ephemeral=True)
            return
        
        review_embed = discord.Embed(
            title="⭐ Avalie sua Compra!",
            description=f"Sua opinião é muito importante para nós. Por favor, clique no botão abaixo para deixar uma nota e um comentário sobre sua experiência.",
            color=ROSE_COLOR
        )
        view = StartReviewView(transaction_id=transaction_id)
        
        await interaction.response.send_message(embed=review_embed, view=view)

    @app_commands.command(name="minhascompras", description="Mostra o seu histórico de compras na loja.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def minhascompras(self, interaction: discord.Interaction):
        await show_purchase_history(interaction)

    @app_commands.command(name="setuppainelcliente", description="[Admin] Envia o painel da Área do Cliente.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def setup_customer_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(title="👤 Área do Cliente - Israbuy", description="Bem-vindo(a) à sua área de cliente!\n\nClique no botão abaixo para ver seu histórico de compras de forma privada.", color=ROSE_COLOR)
        embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
        await interaction.response.send_message("Painel do cliente criado!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=CustomerAreaView())

    @app_commands.command(name="setupvip", description="[Admin] Envia o painel para compra de VIP.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def setup_vip_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(title="💎 Torne-se um Membro VIP!", description=(f"Tenha acesso a benefícios exclusivos em nossa loja!\n\n**Vantagens:**\n- Descontos em pacotes de Robux\n- Acesso a canais e sorteios exclusivos\n- Atendimento prioritário\n\nClique no botão abaixo para iniciar a compra da sua assinatura por **R$ {VIP_PRICE:.2f}**."), color=discord.Color.gold())
        embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
        await interaction.response.send_message("Painel VIP criado!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=VipPurchaseView())

async def setup(bot: commands.Bot):
    await bot.add_cog(Cliente(bot))
