# cogs/voice_manager.py
import discord
from discord.ext import commands, tasks
import config
from gtts import gTTS
import io

class VoiceManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ensure_voice_connection.start()

    def cog_unload(self):
        self.ensure_voice_connection.cancel()

    @tasks.loop(seconds=30)
    async def ensure_voice_connection(self):
        """Verifica e gerencia a conexão de voz do bot com base na nova lógica unificada."""
        try:
            guild = self.bot.get_guild(config.GUILD_ID)
            if not guild: return

            target_user = guild.get_member(config.TTS_TARGET_USER_ID)
            permanent_channel = guild.get_channel(config.PERMANENT_VOICE_CHANNEL_ID)
            
            target_channel = None

            # Prioridade 1: Seguir o usuário alvo
            if target_user and target_user.voice and target_user.voice.channel:
                target_channel = target_user.voice.channel
            # Prioridade 2: Ficar no canal permanente se o usuário não estiver em call
            elif permanent_channel:
                target_channel = permanent_channel
            
            if not target_channel:
                return # Não há um destino, então não faz nada

            vc = guild.voice_client
            if vc:
                if vc.channel.id != target_channel.id:
                    await vc.move_to(target_channel)
            else:
                await target_channel.connect()

        except Exception as e:
            print(f"Erro na tarefa de conexão de voz: {e}")

    @ensure_voice_connection.before_loop
    async def before_ensure_voice_connection(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Lógica de TTS que agora vive aqui."""
        if message.author.bot or message.channel.id != config.TTS_TEXT_CHANNEL_ID:
            return

        guild = message.guild
        vc = guild.voice_client

        if not (vc and vc.is_connected() and not vc.is_playing()):
            return

        try:
            fp = io.BytesIO()
            tts = gTTS(text=message.clean_content, lang='pt-br')
            tts.write_to_fp(fp)
            fp.seek(0)
            
            vc.play(discord.FFmpegPCMAudio(fp, pipe=True))
        except Exception as e:
            print(f"Erro ao tentar reproduzir TTS: {e}")

async def setup(bot):
    await bot.add_cog(VoiceManager(bot))
