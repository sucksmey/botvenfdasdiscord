# cogs/helpers.py
import discord
import config

async def get_discount_info(pool):
    """Busca as informações de desconto do banco de dados."""
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT percentage, apply_to_all FROM discount WHERE id = 1;")

async def apply_discount(member: discord.Member, category_name: str, price: float, discount_info):
    """Aplica o desconto a um preço com base nas novas regras."""
    if not discount_info or category_name != "Robux":
        return price, False # Retorna preço original e se o desconto foi aplicado

    client_role = member.guild.get_role(config.CLIENT_ROLE_ID)
    percentage = discount_info['percentage']
    apply_to_all = discount_info['apply_to_all']

    # Se o desconto for para todos, ou se não for para todos E o usuário não tiver o cargo de cliente
    if apply_to_all or (not apply_to_all and client_role not in member.roles):
        final_price = price * (1 - float(percentage) / 100)
        return final_price, True
    
    return price, False

async def generate_pix_embed(total_price):
    embed = discord.Embed(
        title="Pagamento via PIX",
        description=f"O total da sua compra é **R$ {total_price:.2f}**.\n\n"
                    f"**Chave PIX (E-mail):**\n`{config.PIX_KEY_MANUAL}`\n\n"
                    f"Use o QR Code abaixo ou a chave para pagar. Após o pagamento, **envie o comprovante** neste canal.",
        color=discord.Color.blurple()
    )
    embed.set_image(url="https://gorgeous-crisp-dc1e5e.netlify.app/image.png")
    return embed
