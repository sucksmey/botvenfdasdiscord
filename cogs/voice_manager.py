# cogs/voice_manager.py
import discord
from discord.ext import commands, tasks
import config
import asyncio

class VoiceManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ensure_voice_connection.start()

    def cog_unload(self):
        self.ensure_voice_connection.cancel()

    @tasks.loop(seconds=60)
    async def ensure_voice_connection(self):
        """Verifica a cada 60 segundos se o bot está no canal de voz correto."""
        try:
            target_channel = self.bot.get_channel(config.PERMANENT_VOICE_CHANNEL_ID)
            if not isinstance(target_channel, discord.VoiceChannel):
                print(f"ERRO: O ID {config.PERMANENT_VOICE_CHANNEL_ID} não é de um canal de voz válido.")
                return

            guild = self.bot.get_guild(config.GUILD_ID)
            vc = discord.utils.get(self.bot.voice_clients, guild=guild)

            if vc and vc.is_connected():
                if vc.channel.id != target_channel.id:
                    await vc.move_to(target_channel)
            else:
                await target_channel.connect()
        except Exception as e:
            print(f"Erro ao tentar conectar ao canal de voz: {e}")

    @ensure_voice_connection.before_loop
    async def before_ensure_voice_connection(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(VoiceManager(bot))
