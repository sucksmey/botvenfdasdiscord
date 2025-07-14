# cogs/loyalty.py
import discord
from discord import app_commands
from discord.ext import commands
import config
import traceback

LOYALTY_TIERS = {
    10: {"name": "Cliente Fiel 🥉", "reward": "1.000 Robux por R$35 na sua próxima compra!", "role_id": config.LOYALTY_ROLE_10, "emoji": "🥉"},
    20: {"name": "Cliente Bronze II", "reward": "100 Robux grátis na sua próxima compra!", "role_id": None, "emoji": "🎯"},
    30: {"name": "Cliente Prata 🥈", "reward": "Desconto vitalício de R$1 em pacotes acima de 500 Robux!", "role_id": None, "emoji": "🥈"},
    40: {"name": "Cliente Prata II", "reward": "300 Robux grátis na sua próxima compra!", "role_id": None, "emoji": "🎯"},
    50: {"name": "Cliente Ouro 🥇", "reward": "Um pacote de 1.000 Robux por R$30 (uso único)!", "role_id": config.LOYALTY_ROLE_50, "emoji": "🥇"},
    60: {"name": "Cliente Diamante 💎", "reward": "Acesso ao 'Clube VIP Fidelidade' (entregas prioritárias, mimos mensais e cargo especial)!", "role_id": None, "emoji": "👑"},
    70: {"name": "Cliente Mestre 🔥", "reward": "Combo especial: 500 + 300 Robux por apenas R$25!", "role_id": None, "emoji": "🔥"},
    100: {"name": "Lenda da Israbuy 🏆", "reward": "Mural dos Deuses, 1.000 Robux grátis e acesso permanente a promoções VIP!", "role_id": config.LOYALTY_ROLE_100, "emoji": "🏆"}
}

class Loyalty(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="beneficiosfidelidade", description="Mostra os benefícios do nosso programa de fidelidade.")
    async def show_benefits(self, interaction: discord.Interaction):
        # 1. Responde imediatamente para evitar o timeout
        await interaction.response.defer(ephemeral=True)
        
        purchase_count = 0
        try:
            # 2. Tenta buscar os dados do banco de dados
            async with self.bot.pool.acquire() as conn:
                # Adicionado um timeout de 10 segundos para a consulta
                purchase_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM purchases WHERE user_id = $1 AND admin_id IS NOT NULL",
                    interaction.user.id,
                    timeout=10.0
                )
        except Exception as e:
            # 3. Se a busca falhar, avisa o usuário e loga o erro
            print(f"Erro ao consultar o banco de dados no comando /beneficiosfidelidade: {e}")
            await interaction.followup.send("😕 Não consegui consultar seu histórico de compras no momento. Por favor, tente novamente mais tarde.", ephemeral=True)
            return

        # 4. Se a busca for bem-sucedida, monta e envia a mensagem completa
        embed = discord.Embed(
            title="🌟 Programa de Fidelidade Israbuy 🌟",
            description=f"Obrigado por ser um cliente especial! Quanto mais você compra, mais benefícios exclusivos você desbloqueia.\n\n**Você tem atualmente `{purchase_count or 0}` compras verificadas.**",
            color=discord.Color.gold()
        )

        for count, data in LOYALTY_TIERS.items():
            embed.add_field(
                name=f"{data['emoji']} {count} Compras: {data['name']}",
                value=data['reward'],
                inline=False
            )
        
        embed.set_footer(text="As recompensas são aplicadas automaticamente ao atingir a meta.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def check_loyalty_milestones(self, interaction: discord.Interaction, customer: discord.Member):
        try:
            guild = interaction.guild
            notification_channel = guild.get_channel(config.LOYALTY_NOTIFICATION_CHANNEL_ID)

            async with self.bot.pool.acquire() as conn:
                purchase_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM purchases WHERE user_id = $1 AND admin_id IS NOT NULL",
                    customer.id
                )
            
            if purchase_count in LOYALTY_TIERS:
                tier_data = LOYALTY_TIERS[purchase_count]
                if notification_channel:
                    notif_embed = discord.Embed(
                        title="🎉 Meta de Fidelidade Atingida! 🎉",
                        description=f"O cliente {customer.mention} atingiu a marca de **{purchase_count} compras**!",
                        color=discord.Color.green()
                    )
                    notif_embed.add_field(name="Recompensa Desbloqueada", value=f"**{tier_data['name']}**: {tier_data['reward']}")
                    notif_embed.set_thumbnail(url=customer.display_avatar.url)
                    await notification_channel.send(embed=notif_embed)

                ai_cog = self.bot.get_cog("AIAssistant")
                if ai_cog and ai_cog.model:
                    prompt = f"Você é a Israbuy. O cliente {customer.display_name} acabou de atingir a marca de {purchase_count} compras! Envie uma mensagem de parabéns super amigável e com emojis para ele em sua DM, explicando o novo benefício incrível que ele desbloqueou: '{tier_data['reward']}'."
                    response = await ai_cog.model.generate_content_async(prompt)
                    try:
                        await customer.send(response.text)
                    except discord.Forbidden:
                        print(f"Não foi possível enviar DM de fidelidade para {customer.name}.")

                if tier_data['role_id']:
                    role_to_add = guild.get_role(tier_data['role_id'])
                    if role_to_add:
                        await customer.add_roles(role_to_add, reason=f"Atingiu {purchase_count} compras.")
        except Exception as e:
            print(f"Erro ao verificar milestones de fidelidade para {customer.name}: {e}")

async def setup(bot):
    await bot.add_cog(Loyalty(bot))
