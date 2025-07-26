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
        # Verifica se a atualização é do usuário alvo
        if member.id != config.TTS_TARGET_USER_ID:
            return

        guild = member.guild
        vc = discord.utils.get(self.bot.voice_clients, guild=guild)

        try:
            # Usuário entrou ou trocou de canal de voz
            if after.channel and (not before.channel or before.channel.id != after.channel.id):
                if vc and vc.is_connected():
                    await vc.move_to(after.channel)
                else:
                    await after.channel.connect()

            # Usuário saiu de um canal de voz
            elif not after.channel and before.channel:
                if vc and vc.is_connected():
                    await vc.disconnect()
        except Exception as e:
            print(f"Erro no on_voice_state_update (TTS): {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignora mensagens de bots ou de fora do canal de texto alvo
        if message.author.bot or message.channel.id != config.TTS_TEXT_CHANNEL_ID:
            return

        guild = message.guild
        vc = discord.utils.get(self.bot.voice_clients, guild=guild)

        # Verifica se o bot está conectado a um canal de voz no servidor e não está tocando nada
        if not (vc and vc.is_connected() and not vc.is_playing()):
            return

        try:
            # Gera o áudio da mensagem em memória
            fp = io.BytesIO()
            tts = gTTS(text=message.clean_content, lang='pt-br')
            tts.write_to_fp(fp)
            fp.seek(0)
            
            # Toca o áudio no canal de voz
            vc.play(discord.FFmpegPCMAudio(fp, pipe=True))

        except Exception as e:
            print(f"Erro ao tentar reproduzir TTS: {e}")

async def setup(bot):
    await bot.add_cog(TTSRelay(bot))
