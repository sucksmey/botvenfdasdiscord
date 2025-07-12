# cogs/helpers.py
import discord
import config

async def get_discount_info(pool):
    """Busca as informações de desconto promocional do banco de dados."""
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT percentage, apply_to_all FROM discount WHERE id = 1;")

async def apply_discount(member: discord.Member, category_name: str, price: float):
    """
    Aplica o desconto de 3% para a primeira compra de Robux.
    Esta função agora tem a regra fixa e não depende mais do banco de dados.
    """
    if category_name != "Robux":
        return price, False # Retorna preço original se não for Robux

    client_role = member.guild.get_role(config.CLIENT_ROLE_ID)
    
    # Se o usuário NÃO tiver o cargo de cliente, é a primeira compra de Robux dele.
    if client_role and client_role not in member.roles:
        final_price = price * 0.97  # Aplica 3% de desconto
        return final_price, True
    
    # Se já for cliente, retorna o preço normal.
    return price, False

async def generate_pix_embed(total_price):
    """Cria o embed de pagamento PIX usando o link da imagem estática."""
    embed = discord.Embed(
        title="Pagamento via PIX",
        description=f"O total da sua compra é **R$ {total_price:.2f}**.\n\n"
                    f"**Chave PIX (E-mail):**\n`{config.PIX_KEY_MANUAL}`\n\n"
                    f"Use o QR Code abaixo ou a chave para pagar. Após o pagamento, **envie o comprovante** neste canal.",
        color=discord.Color.blurple()
    )
    embed.set_image(url="https://gorgeous-crisp-dc1e5e.netlify.app/image.png")
    return embed
