# cogs/voice_manager.py
import discord
from discord.ext import commands, tasks
import config
from gtts import gTTS
import io
import os
import asyncio
import traceback

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
            vc = guild.voice_client
            target_channel = None

            # Prioridade 1: Seguir o usuário alvo
            if target_user and target_user.voice and target_user.voice.channel:
                target_channel = target_user.voice.channel
            else:
                # Prioridade 2: Procurar um canal com membros
                for channel in guild.voice_channels:
                    # Procura um canal que não esteja vazio (e que os membros não sejam só bots)
                    if channel.members and any(not m.bot for m in channel.members):
                        target_channel = channel
                        break # Encontrou o primeiro canal com gente, para de procurar
            
            # Se encontrou um canal de destino (seja do usuário alvo ou um canal com gente)
            if target_channel:
                if vc:
                    if vc.channel.id != target_channel.id:
                        await vc.move_to(target_channel)
                else:
                    await target_channel.connect()
            # Se não encontrou NENHUM canal de destino (servidor de voz vazio) e o bot está conectado
            elif vc:
                await vc.disconnect()

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

        while vc.is_playing():
            await asyncio.sleep(0.5)

        tts_file = f"temp_tts_{message.id}.mp3"
        try:
            tts = gTTS(text=message.clean_content, lang='pt-br')
            tts.save(tts_file)
            source = discord.FFmpegPCMAudio(tts_file)
            vc.play(source)
            while vc.is_playing():
                await asyncio.sleep(0.5)
            os.remove(tts_file)
            await message.remove_reaction("💬", self.bot.user)
            await message.add_reaction("✅")
            await asyncio.sleep(2)
            await message.delete()
        except Exception as e:
            print(f"Erro ao tentar reproduzir TTS:")
            traceback.print_exc()
            await message.reply(f"❌ Ocorreu um erro ao tentar reproduzir a fala: `{str(e)}`")
            try:
                await message.remove_reaction("💬", self.bot.user)
            except discord.NotFound:
                pass
            await message.add_reaction("❌")
            if os.path.exists(tts_file):
                os.remove(tts_file)

async def setup(bot):
    await bot.add_cog(VoiceManager(bot))
