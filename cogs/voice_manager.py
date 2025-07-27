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

    @tasks.loop(seconds=30)  # Verificação mais frequente para garantir a conexão
    async def ensure_voice_connection(self):
        """Verifica a cada 30 segundos se o bot está no canal de voz correto."""
        try:
            guild = self.bot.get_guild(config.GUILD_ID)
            if not guild:
                return

            target_channel = guild.get_channel(config.PERMANENT_VOICE_CHANNEL_ID)
            if not isinstance(target_channel, discord.VoiceChannel):
                print(f"ERRO: O ID {config.PERMANENT_VOICE_CHANNEL_ID} não é de um canal de voz válido.")
                return

            # Verifica se o bot já está conectado em algum canal de voz neste servidor
            vc = guild.voice_client

            if vc:
                # Se já está conectado, mas no canal errado, move
                if vc.channel.id != target_channel.id:
                    await vc.move_to(target_channel)
                    print(f"Bot movido para o canal de voz correto: {target_channel.name}")
            else:
                # Se não está conectado, conecta
                await target_channel.connect()
                print(f"Bot conectado ao canal de voz: {target_channel.name}")

        except Exception as e:
            print(f"Erro ao tentar conectar ao canal de voz: {e}")

    @ensure_voice_connection.before_loop
    async def before_ensure_voice_connection(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(VoiceManager(bot))
