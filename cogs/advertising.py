# cogs/advertising.py
import discord
from discord import app_commands
from discord.ext import commands, tasks
import config
import traceback
import random

# --- Textos das Propagandas (com a primeira mensagem ATUALIZADA) ---
AD_MESSAGES = [
    {
        "content": "🎉 Sua primeira compra na **ISRABUY** tem presente!",
        "embed": discord.Embed(
            description="## Você ganha **3% de DESCONTO** na sua primeira compra de Robux! 💎\n\nBasta iniciar um ticket de compra que o desconto será aplicado **automaticamente** no seu pedido.",
            color=0xFF69B4  # Cor Rosinha
        )
    },
    {
        "content": "Cansou de estar afundado no Bronze ou no Prata no Valorant? Nós subimos você! <:PandaDevil:1240881900405624832>",
        "embed": discord.Embed(
            description="## Fazemos elojob de Valorant!\n\nConfira nossos preços clicando em \"escolha um jogo ou serviço para comprar...\"",
            color=0xE91E63
        )
    },
    {
        "content": "",
        "embed": discord.Embed(
            title="💎 Dimas no Free Fire tá baratinho em!",
            description="Perde essa oportunidade não!",
            color=0xF1C40F
        )
    },
    {
        "content": "",
        "embed": discord.Embed(
            title="💥 Valorant Points e Riot Points baratinhos!",
            description="Pra te deixar com skin poderosa!",
            color=0x3498DB
        )
    },
    {
        "content": "",
        "embed": discord.Embed(
            title="🌈 Genshin Impact é pay-to-win demais!",
            description="Aqui na Israbuy os preços são bem baratinhos pra te ajudar nessa jornada.",
            color=0x9B59B6
        )
    }
]

class Advertising(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_ad_message.start()

    def cog_unload(self):
        self.update_ad_message.cancel()

    async def handle_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Ocorreu um erro no comando de propaganda:")
        traceback.print_exc()
        error_message = f"😕 Ocorreu um erro.\n**Detalhe:** `{str(error)}`"
        if interaction.response.is_done():
            await interaction.followup.send(error_message, ephemeral=True)
        else:
            await interaction.response.send_message(error_message, ephemeral=True)

    propaganda_group = app_commands.Group(name="propaganda", description="Gerencia a mensagem de propaganda automática.", guild_ids=[config.GUILD_ID])

    @propaganda_group.command(name="iniciar", description="Envia e inicia a propaganda automática em um canal.")
    @app_commands.describe(canal="O canal onde a propaganda será enviada.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def start_ad(self, interaction: discord.Interaction, canal: discord.TextChannel):
        try:
            await interaction.response.defer(ephemeral=True)
            first_ad = AD_MESSAGES[0]
            ad_message = await canal.send(content=first_ad.get("content", ""), embed=first_ad.get("embed"))

            async with self.bot.pool.acquire() as conn:
                await conn.execute("DELETE FROM ad_message WHERE id = 1;")
                await conn.execute(
                    "INSERT INTO ad_message (id, channel_id, message_id, current_index) VALUES (1, $1, $2, 0);",
                    canal.id, ad_message.id
                )
            
            await interaction.followup.send(f"✅ Sistema de propaganda iniciado no canal {canal.mention}!", ephemeral=True)

        except Exception as e:
            await self.handle_error(interaction, e)

    @propaganda_group.command(name="parar", description="Para a atualização e deleta a mensagem de propaganda.")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def stop_ad(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            async with self.bot.pool.acquire() as conn:
                ad_data = await conn.fetchrow("SELECT channel_id, message_id FROM ad_message WHERE id = 1;")
                if ad_data:
                    try:
                        channel = self.bot.get_channel(ad_data['channel_id'])
                        message = await channel.fetch_message(ad_data['message_id'])
                        await message.delete()
                    except (discord.NotFound, discord.Forbidden, AttributeError):
                        pass
                    await conn.execute("DELETE FROM ad_message WHERE id = 1;")
            await interaction.followup.send("🗑️ Sistema de propaganda parado.", ephemeral=True)

        except Exception as e:
            await self.handle_error(interaction, e)

    @tasks.loop(hours=1)
    async def update_ad_message(self):
        try:
            async with self.bot.pool.acquire() as conn:
                ad_data = await conn.fetchrow("SELECT channel_id, message_id, current_index FROM ad_message WHERE id = 1;")
            
            if not ad_data: return

            channel_id, message_id, current_index = ad_data['channel_id'], ad_data['message_id'], ad_data['current_index']
            next_index = (current_index + 1) % len(AD_MESSAGES)
            next_ad = AD_MESSAGES[next_index]

            channel = self.bot.get_channel(channel_id)
            if not channel: return

            message = await channel.fetch_message(message_id)
            await message.edit(content=next_ad.get("content", ""), embed=next_ad.get("embed"))

            async with self.bot.pool.acquire() as conn:
                await conn.execute("UPDATE ad_message SET current_index = $1 WHERE id = 1;", next_index)

        except (discord.NotFound, discord.Forbidden):
             print(f"Não foi possível encontrar/editar a msg de propaganda. Removendo do DB.")
             async with self.bot.pool.acquire() as conn:
                await conn.execute("DELETE FROM ad_message WHERE id = 1;")
        except Exception as e:
            print(f"Erro na tarefa de propaganda: {e}")

    @update_ad_message.before_loop
    async def before_update_ad_message(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Advertising(bot))
