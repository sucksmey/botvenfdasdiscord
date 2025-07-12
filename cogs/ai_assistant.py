# cogs/ai_assistant.py
import discord
from discord.ext import commands
import config
import json
import os
import google.generativeai as genai

# O ID do canal onde a IA irá responder
AI_CHANNEL_ID = 1393593539908337734

class AIAssistant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Transforma o dicionário de produtos em uma string JSON para usar como contexto
        self.product_context = json.dumps(config.PRODUCTS, indent=2, ensure_ascii=False)

        # --- CONFIGURAÇÃO DA API DO GEMINI ---
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            print("AVISO: Chave da API do Gemini (GEMINI_API_KEY) não encontrada. A IA não funcionará.")
            self.model = None
        else:
            genai.configure(api_key=GEMINI_API_KEY)
            # Usando o modelo Flash, que é rápido e eficiente
            self.model = genai.GenerativeModel('gemini-1.5-flash-latest')

    def get_ai_prompt(self, user_question: str) -> str:
        """
        Monta o prompt que será enviado para a IA.
        """
        return f"""
        Você é "Israbuy", um assistente de vendas amigável e prestativo de uma loja de créditos para jogos online.
        Sua personalidade é moderna, atenciosa e você adora usar emojis para deixar a conversa mais leve.
        Responda APENAS a perguntas relacionadas aos produtos da loja. Se a pergunta for sobre qualquer outra coisa (como programação, o tempo, etc.), recuse educadamente dizendo que você só pode ajudar com dúvidas sobre os produtos.

        **Contexto dos Produtos da Loja (em formato JSON):**
        ```json
        {self.product_context}
        ```

        **Regras Importantes:**
        1.  Seja sempre amigável e use emojis. 😊
        2.  Suas respostas devem ser curtas e diretas.
        3.  Baseie suas respostas **estritamente** nas informações do contexto JSON acima. Não invente produtos ou preços.
        4.  Quando mencionar preços, sempre use "R$".
        5.  Se alguém perguntar "qual o mais barato?" ou "qual o melhor?", mostre as opções sem dar uma opinião direta, deixando o cliente decidir.
        6.  Se a pergunta for vaga, como "tem robux?", responda mostrando os pacotes de Robux disponíveis e seus preços.

        **Pergunta do Cliente:** "{user_question}"

        **Sua Resposta (como Israbuy):**
        """

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignora mensagens de bots, fora do canal de IA ou respostas
        if message.author.bot or message.channel.id != AI_CHANNEL_ID or message.reference:
            return
        
        # Verifica se o modelo de IA foi carregado corretamente
        if not self.model:
            return

        prompt = self.get_ai_prompt(message.content)

        async with message.channel.typing():
            try:
                # --- CHAMADA REAL À API DO GEMINI ---
                response = await self.model.generate_content_async(prompt)
                
                # Responde mencionando o usuário
                await message.reply(response.text)
            
            except Exception as e:
                print(f"Erro ao chamar a API do Gemini: {e}")
                await message.reply("Ops! 😥 Parece que minha conexão com a inteligência artificial falhou. Tente novamente em um instante.")

async def setup(bot):
    await bot.add_cog(AIAssistant(bot))
