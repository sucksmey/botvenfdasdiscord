# cogs/voice_manager.py
import discord
from discord.ext import commands, tasks
import config
from gtts import gTTS
import os # Importa a biblioteca 'os' para lidar com arquivos

class VoiceManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ensure_voice_connection.start()

    def cog_unload(self):
        self.ensure_voice_connection.cancel()

    @tasks.loop(seconds=30)
    async def ensure_voice_connection(self):
        try:
            guild = self.bot.get_guild(config.GUILD_ID)
            if not guild: return
            target_user = guild.get_member(config.TTS_TARGET_USER_ID)
            permanent_channel = guild.get_channel(config.PERMANENT_VOICE_CHANNEL_ID)
            target_channel = None
            if target_user and target_user.voice and target_user.voice.channel:
                target_channel = target_user.voice.channel
            elif permanent_channel:
                target_channel = permanent_channel
            if not target_channel:
                if guild.voice_client: await guild.voice_client.disconnect()
                return
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
        if message.author.bot or message.channel.id != config.TTS_TEXT_CHANNEL_ID:
            return

        guild = message.guild
        vc = guild.voice_client

        if not (vc and vc.is_connected() and not vc.is_playing()):
            return
        
        await message.add_reaction("💬")

        try:
            # --- LÓGICA CORRIGIDA ---
            # 1. Gera o áudio e salva em um arquivo temporário
            tts = gTTS(text=message.clean_content, lang='pt-br')
            tts_file = f"temp_tts_{message.id}.mp3"
            tts.save(tts_file)

            # 2. Toca o áudio a partir do arquivo
            source = discord.FFmpegPCMAudio(tts_file)
            vc.play(source)

            while vc.is_playing():
                await asyncio.sleep(0.5)

            # 3. Remove o arquivo temporário após tocar
            os.remove(tts_file)

            await message.remove_reaction("💬", self.bot.user)
            await message.add_reaction("✅")
            await asyncio.sleep(2)
            await message.delete()

        except Exception as e:
            print(f"Erro ao tentar reproduzir TTS: {e}")
            await message.remove_reaction("💬", self.bot.user)
            await message.add_reaction("❌")
            # Garante que o arquivo temporário seja removido mesmo em caso de erro
            if 'tts_file' in locals() and os.path.exists(tts_file):
                os.remove(tts_file)

async def setup(bot):
    await bot.add_cog(VoiceManager(bot))
