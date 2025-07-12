# cogs/ai_assistant.py
import discord
from discord.ext import commands
import config
import json

# O ID do canal onde a IA irá responder
AI_CHANNEL_ID = 1393593539908337734

class AIAssistant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Transforma o dicionário de produtos em uma string JSON para usar como contexto
        self.product_context = json.dumps(config.PRODUCTS, indent=2, ensure_ascii=False)

    def get_ai_prompt(self, user_question: str) -> str:
        """
        Monta o prompt que será enviado para a "IA".
        Ele inclui as regras, o contexto dos produtos e a pergunta do usuário.
        """
        
        prompt = f"""
        Você é "Israbuy", um assistente de vendas amigável e prestativo de uma loja de créditos para jogos online.
        Sua personalidade é moderna, atenciosa e você adora usar emojis para deixar a conversa mais leve.
        Responda APENAS a perguntas relacionadas aos produtos da loja. Se a pergunta for sobre qualquer outra coisa (como programação, o tempo, etc.), recuse educadamente dizendo que você só pode ajudar com dúvidas sobre os produtos.

        **Contexto dos Produtos da Loja (em formato JSON):**
        ```json
        {self.product_context}
        ```

        **Regras Importantes:**
        1.  Seja sempre amigável e use emojis.
        2.  Suas respostas devem ser curtas e diretas.
        3.  Baseie suas respostas **estritamente** nas informações do contexto JSON acima. Não invente produtos ou preços.
        4.  Quando mencionar preços, sempre use "R$".
        5.  Se alguém perguntar "qual o mais barato?" ou "qual o melhor?", mostre as opções sem dar uma opinião direta, deixando o cliente decidir.
        6.  Se a pergunta for vaga, como "tem robux?", responda mostrando os pacotes de Robux disponíveis e seus preços.

        **Pergunta do Cliente:** "{user_question}"

        **Sua Resposta (como Israbuy):**
        """
        return prompt

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignora mensagens de bots (incluindo a si mesmo) e fora do canal de IA
        if message.author.bot or message.channel.id != AI_CHANNEL_ID:
            return

        # Para evitar loops, ignora mensagens que são respostas a outras mensagens
        if message.reference:
            return

        # Monta o prompt para a IA
        prompt = self.get_ai_prompt(message.content)

        # --- SIMULAÇÃO DA CHAMADA DA IA ---
        # Em um bot real, aqui você faria uma chamada para uma API de IA (como a do GPT, Gemini, etc.)
        # Para este exemplo, vamos criar uma resposta simulada baseada em palavras-chave.
        # Esta é a parte que você substituiria por uma integração real no futuro.
        
        async with message.channel.typing():
            # Lógica de IA Simulada (pode ser substituída por uma API real)
            response_text = "Olá! 😊 Parece que você tem uma dúvida. Deixe-me ver como posso ajudar..."
            
            user_question_lower = message.content.lower()

            if "robux" in user_question_lower:
                robux_prices = config.PRODUCTS.get("Robux", {}).get("prices", {})
                if robux_prices:
                    response_text = "Claro! Nós temos vários pacotes de Robux! 💎\n\n"
                    for item, price in robux_prices.items():
                        response_text += f"• **{item}**: R$ {price:.2f}\n"
                else:
                    response_text = "Hmm, não encontrei informações sobre Robux no momento. 🤔"
            
            elif "valorant" in user_question_lower:
                vp_prices = config.PRODUCTS.get("Valorant", {}).get("prices", {})
                if vp_prices:
                    response_text = "Opa! Temos sim Valorant Points! 💢 Aqui estão nossos pacotes:\n\n"
                    for item, price in vp_prices.items():
                        response_text += f"• **{item}**: R$ {price:.2f}\n"
                else:
                    response_text = "Não achei os preços de Valorant Points agora, desculpe! 😥"

            elif "free fire" in user_question_lower or "dima" in user_question_lower:
                ff_prices = config.PRODUCTS.get("Free Fire", {}).get("prices", {})
                if ff_prices:
                    response_text = "Temos Dimas para Free Fire, sim! 🔥 Confira os pacotes:\n\n"
                    for item, price in ff_prices.items():
                        response_text += f"• **{item}**: R$ {price:.2f}\n"
                else:
                    response_text = "Puxa, não encontrei os pacotes de Free Fire. 😕"
            
            # Se não for uma pergunta sobre os produtos, recusa educadamente.
            elif len(user_question_lower) > 25 and not any(game.lower() in user_question_lower for game in config.PRODUCTS.keys()):
                 response_text = "Olá! 👋 Eu sou a Israbuy, assistente de vendas. No momento, só consigo ajudar com dúvidas sobre os produtos da nossa loja. Como posso te ajudar com isso?"

            # Responde mencionando o usuário
            await message.reply(response_text)

async def setup(bot):
    await bot.add_cog(AIAssistant(bot))
