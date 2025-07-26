# cogs/ai_assistant.py
import discord
from discord.ext import commands
import config
import json
import os
import google.generativeai as genai

class AIAssistant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.product_context = json.dumps(config.PRODUCTS_CONTEXT, indent=2, ensure_ascii=False)

        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            print("AVISO: Chave da API do Gemini (GEMINI_API_KEY) não encontrada. A IA não funcionará.")
            self.model = None
        else:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-1.5-flash-latest')

    def get_ai_prompt(self, user_question: str) -> str:
        return f"""
        Você é "Israbuy", um assistente de vendas amigável e prestativo de uma loja de créditos para jogos online.
        Sua personalidade é moderna e atenciosa. Use emojis para deixar a conversa mais leve.
        Responda APENAS a perguntas relacionadas aos produtos da loja. Se a pergunta for sobre outra coisa, recuse educadamente.

        **Contexto dos Produtos da Loja:**
        ```json
        {self.product_context}
        ```

        **Regras de Resposta:**
        1.  Seja sempre amigável e use emojis. 😊
        2.  Suas respostas devem ser curtas e diretas.
        3.  Baseie suas respostas **estritamente** nas informações do contexto acima.
        4.  Se alguém perguntar "como comprar?", explique que para comprar o usuário deve ir ao canal <#{config.SALES_CHANNEL_ID}>.

        **Pergunta do Cliente:** "{user_question}"

        **Sua Resposta (como Israbuy):**
        """

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id != config.AI_CHANNEL_ID or message.reference:
            return
        
        if not self.model: return

        prompt = self.get_ai_prompt(message.content)
        async with message.channel.typing():
            try:
                response = await self.model.generate_content_async(prompt)
                await message.reply(response.text)
            except Exception as e:
                print(f"Erro ao chamar a API do Gemini: {e}")
                await message.reply("Ops! 😥 Minha conexão com a inteligência artificial falhou. Tente novamente.")

async def setup(bot):
    await bot.add_cog(AIAssistant(bot))
