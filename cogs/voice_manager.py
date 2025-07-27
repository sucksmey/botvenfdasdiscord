# cogs/voice_manager.py
import discord
from discord.ext import commands, tasks
import config
import asyncio
import aiohttp
import io
import traceback
import urllib.parse # <-- Biblioteca correta para codificar a URL

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

            if target_user and target_user.voice and target_user.voice.channel:
                target_channel = target_user.voice.channel
            else:
                for channel in guild.voice_channels:
                    if channel.members and any(not m.bot for m in channel.members):
                        target_channel = channel
                        break
            
            if target_channel:
                if vc:
                    if vc.channel.id != target_channel.id: await vc.move_to(target_channel)
                else:
                    await target_channel.connect()
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

        vc = discord.utils.get(self.bot.voice_clients, guild=message.guild)
        if not (vc and vc.is_connected()):
            return
        
        await message.add_reaction("💬")

        while vc.is_playing():
            await asyncio.sleep(0.5)

        try:
            # --- CORREÇÃO APLICADA AQUI ---
            # Usa urllib.parse.quote em vez de discord.utils.quote
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
