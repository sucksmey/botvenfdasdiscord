# cogs/tickets.py
import discord
from discord import app_commands
from discord.ext import commands
import config
from .views import TutorialGamepassView

# --- Funções Auxiliares ---

async def get_current_discount(pool):
    async with pool.acquire() as conn:
        discount = await conn.fetchval("SELECT percentage FROM discount WHERE id = 1;")
    return float(discount) if discount else 0.0

async def apply_discount(price, discount_percentage):
    if discount_percentage > 0:
        return price * (1 - discount_percentage / 100)
    return price

async def generate_pix_embed(total_price):
    # VERSÃO ATUALIZADA: Usa o link da imagem estática
    embed = discord.Embed(
        title="Pagamento via PIX",
        description=f"O total da sua compra é **R$ {total_price:.2f}**.\n\n"
                    f"**Chave PIX (E-mail):**\n`{config.PIX_KEY_MANUAL}`\n\n"
                    f"Use o QR Code abaixo ou a chave para pagar. Após o pagamento, **envie o comprovante** neste canal.",
        color=discord.Color.blurple()
    )
    # Define a imagem para a URL que você forneceu
    embed.set_image(url="https://gorgeous-crisp-dc1e5e.netlify.app/image.png")
    return embed

# --- Cog Principal de Tickets ---

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_data = {}

    @app_commands.command(name="minhascompras", description="Ver seu histórico de compras.")
    async def minhas_compras(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with self.bot.pool.acquire() as conn:
            purchases = await conn.fetch("SELECT product_name, product_price, purchase_date FROM purchases WHERE user_id = $1 ORDER BY purchase_date DESC", interaction.user.id)
        
        if not purchases:
            await interaction.followup.send("Você ainda não fez nenhuma compra.", ephemeral=True)
            return
        
        embed = discord.Embed(title=f"Histórico de Compras de {interaction.user.name}", color=discord.Color.green())
        description = ""
        for p in purchases:
            description += f"**Produto:** {p['product_name']}\n"
            description += f"**Valor:** R$ {p['product_price']:.2f}\n"
            description += f"**Data:** {p['purchase_date'].strftime('%d/%m/%Y %H:%M')}\n---\n"
        
        embed.description = description[:4096]
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="atender", description="[Admin] Libera o chat para atendimento manual no ticket.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def atender(self, interaction: discord.Interaction):
        channel = interaction.channel
        if "ticket-" in channel.name or "vip-" in channel.name:
            await channel.set_permissions(interaction.user, send_messages=True, read_messages=True)
            new_name = f"atendido-{interaction.user.name}"
            await channel.edit(name=new_name)
            
            self.ticket_data[channel.id] = self.ticket_data.get(channel.id, {})
            self.ticket_data[channel.id]['admin_id'] = interaction.user.id

            await interaction.response.send_message(f"{interaction.user.mention} agora está atendendo este ticket. O chat foi liberado.", ephemeral=False)
        else:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)

    @app_commands.command(name="aprovar", description="[Admin] Aprova a compra do cliente.")
    @app_codes.describe(produto="(Opcional) Nome do produto se o bot reiniciou.", valor="(Opcional) Valor do produto se o bot reiniciou.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def aprovar(self, interaction: discord.Interaction, produto: str = None, valor: float = None):
        channel = interaction.channel
        ticket_info = self.ticket_data.get(channel.id, {})

        try:
            user_id = int(channel.name.split('-')[-1])
            customer = await self.bot.fetch_user(user_id)
        except (ValueError, IndexError):
            await interaction.response.send_message("Não consegui identificar o cliente pelo nome do canal. Use os parâmetros `produto` e `valor`.", ephemeral=True)
            return

        product_name = produto or ticket_info.get('product')
        product_price = valor or ticket_info.get('price')
        admin_id = ticket_info.get('admin_id', interaction.user.id)
        
        if not product_name or not product_price:
            await interaction.response.send_message("Informações da compra não encontradas. O bot pode ter reiniciado. Por favor, use os parâmetros `produto` e `valor`.", ephemeral=True)
            return

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO purchases (user_id, admin_id, product_name, product_price, is_vip_purchase) VALUES ($1, $2, $3, $4, $5)",
                customer.id, admin_id, product_name, product_price, False
            )

        guild = interaction.guild
        member = await guild.fetch_member(customer.id)
        client_role = guild.get_role(config.CLIENT_ROLE_ID)
        if client_role and client_role not in member.roles:
            await member.add_roles(client_role, reason="Primeira compra aprovada.")

        entregues_category = guild.get_channel(config.CATEGORY_ENTREGUES_ID)
        if entregues_category:
            await channel.edit(category=entregues_category, name=f"entregue-{customer.name}")
        
        await channel.set_permissions(member, send_messages=True)
        
        log_channel = guild.get_channel(config.LOGS_COMPRAS_CHANNEL_ID)
        embed_log = discord.Embed(title="✅ Compra Aprovada", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed_log.add_field(name="Cliente", value=f"{customer.mention} (`{customer.id}`)", inline=False)
        embed_log.add_field(name="Produto", value=product_name, inline=True)
        embed_log.add_field(name="Valor", value=f"R$ {product_price:.2f}", inline=True)
        embed_log.add_field(name="Aprovado por", value=f"{interaction.user.mention}", inline=False)
        if log_channel:
            await log_channel.send(embed=embed_log)

        try:
            await customer.send(f"🎉 Sua compra de **{product_name}** foi aprovada! Agradecemos a preferência.")
        except discord.Forbidden:
            pass

        from .views import ReviewModal # Importa aqui para evitar dependência circular
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Avaliar Atendimento", style=discord.ButtonStyle.green, custom_id="review_button"))
        await channel.send(f"Compra de {customer.mention} aprovada! Obrigado por comprar conosco.", view=view)

        await interaction.response.send_message("Compra aprovada com sucesso!", ephemeral=True)
        if channel.id in self.ticket_data:
            del self.ticket_data[channel.id]
            
    @app_commands.command(name="aprovarvip", description="[Admin] Aprova a compra de VIP de um membro.")
    @app_commands.describe(membro="O membro que comprou o VIP.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def aprovar_vip(self, interaction: discord.Interaction, membro: discord.Member):
        guild = interaction.guild
        vip_role = guild.get_role(config.VIP_ROLE_ID)
        vip_price = 49.90

        if vip_role:
            await membro.add_roles(vip_role, reason="Compra de VIP aprovada.")

        async with self.bot.pool.acquire() as conn:
             await conn.execute(
                "INSERT INTO purchases (user_id, admin_id, product_name, product_price, is_vip_purchase) VALUES ($1, $2, $3, $4, $5)",
                membro.id, interaction.user.id, "Assinatura VIP", vip_price, True
            )
        
        log_channel = guild.get_channel(config.LOGS_COMPRAS_CHANNEL_ID)
        embed_log = discord.Embed(title="⭐ Compra de VIP Aprovada", color=discord.Color.gold())
        embed_log.add_field(name="Cliente", value=membro.mention)
        embed_log.add_field(name="Aprovado por", value=interaction.user.mention)
        if log_channel:
            await log_channel.send(embed=embed_log)

        try:
            await membro.send("Parabéns! Sua assinatura VIP foi ativada. Você agora tem acesso a benefícios exclusivos.")
        except discord.Forbidden:
            pass
        
        if "vip-" in interaction.channel.name:
            entregues_category = guild.get_channel(config.CATEGORY_ENTREGUES_ID)
            if entregues_category:
                await interaction.channel.edit(category=entregues_category, name=f"entregue-vip-{membro.name}")

        await interaction.response.send_message(f"VIP aprovado para {membro.mention}!", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "review_button":
            from .views import ReviewModal
            await interaction.response.send_modal(ReviewModal(self.bot))

    @app_commands.command(name="pix", description="Envia as informações de pagamento PIX no ticket.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def pix(self, interaction: discord.Interaction, valor: float):
        if "ticket-" not in interaction.channel.name and "vip-" not in interaction.channel.name:
            await interaction.response.send_message("Este comando só pode ser usado em um canal de ticket.", ephemeral=True)
            return

        embed = await generate_pix_embed(valor)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="tutorialgamepass", description="Envia o tutorial da Game Pass com cálculo.")
    @app_commands.describe(robux="Quantidade de Robux desejada.")
    async def tutorial_gamepass(self, interaction: discord.Interaction, robux: int):
        preco = robux * 1.43
        await interaction.response.send_message(
            f"O valor total da Game Pass para `{robux}` Robux é de **R$ {preco:.2f}**.\nSiga o tutorial abaixo para criar a Game Pass corretamente.",
            view=TutorialGamepassView()
        )

    @app_commands.command(name="calculadora", description="Calcula o valor de uma Game Pass.")
    @app_commands.describe(robux="Quantidade de Robux para calcular.")
    async def calculadora(self, interaction: discord.Interaction, robux: int):
        preco = robux * 1.43
        await interaction.response.send_message(f"O valor de uma Game Pass para `{robux}` Robux é **R$ {preco:.2f}**.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))
