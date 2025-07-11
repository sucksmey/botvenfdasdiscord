# cogs/helpers.py
import discord
import config

async def get_current_discount(pool):
    """Busca o percentual de desconto atual no banco de dados."""
    async with pool.acquire() as conn:
        discount = await conn.fetchval("SELECT percentage FROM discount WHERE id = 1;")
    return float(discount) if discount else 0.0

async def apply_discount(category_name, price, discount_percentage):
    """Aplica o desconto a um preço, SOMENTE SE a categoria for 'Robux'."""
    if discount_percentage > 0 and category_name == "Robux":
        return price * (1 - discount_percentage / 100)
    return price

async def generate_pix_embed(total_price):
    """Cria o embed de pagamento PIX usando o link da imagem estática."""
    embed = discord.Embed(
        title="Pagamento via PIX",
        description=f"O total da sua compra é **R$ {total_price:.2f}**.\n\n"
                    f"**Chave PIX (E-mail):**\n`{config.PIX_KEY_MANUAL}`\n\n"
                    f"Use o QR Code abaixo ou a chave para pagar. Após o pagamento, **envie o comprovante** neste canal.",
        color=discord.Color.blurple()
    )
    # Define a imagem para a URL estática
    embed.set_image(url="https://gorgeous-crisp-dc1e5e.netlify.app/image.png")
    return embed
