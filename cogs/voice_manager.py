# cogs/voice_manager.py
import discord
from discord.ext import commands, tasks
import config
import asyncio
import aiohttp
import io
import traceback
import urllib.parse

class VoiceManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ensure_voice_connection.start()

    def cog_unload(self):
        self.ensure_voice_connection.cancel()

    @tasks.loop(seconds=30)
    async def ensure_voice_connection(self):
        """Verifica a cada 30 segundos e garante que o bot esteja no canal de voz permanente."""
        try:
            guild = self.bot.get_guild(config.GUILD_ID)
            if not guild:
                return

            # O canal de destino é sempre o canal fixo definido no config
            target_channel = guild.get_channel(config.PERMANENT_VOICE_CHANNEL_ID)
            if not isinstance(target_channel, discord.VoiceChannel):
                print(f"ERRO: O ID {config.PERMANENT_VOICE_CHANNEL_ID} não é de um canal de voz válido.")
                return

            vc = guild.voice_client

            # Se o bot estiver conectado, mas no canal errado, ele se move.
            if vc and vc.is_connected():
                if vc.channel.id != target_channel.id:
                    await vc.move_to(target_channel)
            # Se o bot não estiver conectado em lugar nenhum, ele conecta.
            else:
                await target_channel.connect()

        except Exception as e:
            print(f"Erro na tarefa de conexão de voz: {e}")

    @ensure_voice_connection.before_loop
    async def before_ensure_voice_connection(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # A lógica de TTS continua funcionando normalmente
        if message.author.bot or message.channel.id != config.TTS_TEXT_CHANNEL_ID:
            return

        vc = discord.utils.get(self.bot.voice_clients, guild=message.guild)
        if not (vc and vc.is_connected()):
            return
        
        # O resto da lógica de TTS...
        if vc.is_playing():
            return

        await message.add_reaction("💬")

        try:
            encoded_text = urllib.parse.quote(message.clean_content)
            url = f"https://api.streamelements.com/kappa/v2/speech?voice=Vitoria&text={encoded_text}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise Exception(f"API de TTS retornou status {resp.status}")
                    
                    audio_data = await resp.read()
                    vc.play(discord.PCMAudio(io.BytesIO(audio_data)))

            while vc.is_playing():
                await asyncio.sleep(0.5)

            await message.remove_reaction("💬", self.bot.user)
            await message.add_reaction("✅")
            await asyncio.sleep(2)
            await message.delete()

        except Exception as e:
            print(f"Erro ao tentar reproduzir TTS (API Externa):")
            traceback.print_exc()
            await message.reply(f"❌ Ocorreu um erro ao tentar reproduzir a fala: `{str(e)}`")
            try:
                await message.remove_reaction("💬", self.bot.user)
            except discord.NotFound:
                pass
            await message.add_reaction("❌")

async def setup(bot):
    await bot.add_cog(VoiceManager(bot))
