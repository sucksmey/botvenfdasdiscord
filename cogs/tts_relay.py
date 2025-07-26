# cogs/tts_relay.py
import discord
from discord.ext import commands
import config
from gtts import gTTS
import io

class TTSRelay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Continua seguindo o usuário alvo
        if member.id != config.TTS_TARGET_USER_ID:
            return

        guild = member.guild
        vc = discord.utils.get(self.bot.voice_clients, guild=guild)

        try:
            if after.channel and (not before.channel or before.channel.id != after.channel.id):
                if vc and vc.is_connected():
                    await vc.move_to(after.channel)
                else:
                    await after.channel.connect()

            elif not after.channel and before.channel:
                if vc and vc.is_connected():
                    await vc.disconnect()
        except Exception as e:
            print(f"Erro no on_voice_state_update (TTS): {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id != config.TTS_TEXT_CHANNEL_ID:
            return

        guild = message.guild
        vc = discord.utils.get(self.bot.voice_clients, guild=guild)
        target_user = guild.get_member(config.TTS_TARGET_USER_ID)

        # --- NOVA LÓGICA ---
        # 1. Verifica se o usuário alvo está em um canal de voz
        if not target_user or not target_user.voice:
            return # Se o usuário principal não está em call, não faz nada.

        target_vc = target_user.voice.channel

        # 2. Se o bot não estiver conectado, ele se conecta ao canal do usuário alvo
        if not vc or not vc.is_connected():
            try:
                vc = await target_vc.connect()
            except Exception as e:
                print(f"Erro ao tentar conectar via on_message (TTS): {e}")
                return
        
        # 3. Se o bot estiver em um canal diferente, ele se move
        elif vc.channel.id != target_vc.id:
            await vc.move_to(target_vc)

        # Se já estiver tocando, espera
        if vc.is_playing():
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
    await bot.add_cog(TTSRelay(bot))
