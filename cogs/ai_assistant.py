# cogs/ai_assistant.py
import discord
from discord.ext import commands
import config
import json
import os
import google.generativeai as genai

# O ID do canal onde a IA irá responder
AI_CHANNEL_ID = 1393593539908337734
# O ID do canal de vendas para onde direcionar os usuários
SALES_CHANNEL_ID = 1380180725369798708

class AIAssistant(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.product_context = json.dumps(config.PRODUCTS, indent=2, ensure_ascii=False)

        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            print("AVISO: Chave da API do Gemini (GEMINI_API_KEY) não encontrada. A IA não funcionará.")
            self.model = None
        else:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-1.5-flash-latest')

    def get_ai_prompt(self, user_question: str) -> str:
        """
        Monta o prompt que será enviado para a IA, agora com as regras de entrega corretas.
        """
        
        prompt = f"""
        Você é "Israbuy", um assistente de vendas amigável e prestativo de uma loja de créditos para jogos online.
        Sua personalidade é moderna, atenciosa e você adora usar emojis para deixar a conversa mais leve.
        Responda APENAS a perguntas relacionadas aos produtos e funcionamento da loja. Se a pergunta for sobre qualquer outra coisa, recuse educadamente.

        **Informações Essenciais da Loja (FAQ):**
        - **Como Comprar?**: Para comprar, o cliente deve ir para o canal de vendas <#{SALES_CHANNEL_ID}> e usar os painéis interativos.
        - **Como são feitas as Entregas?**: O método de entrega varia por produto:
            - **Via Game Pass:** Apenas para **Robux**. O cliente cria uma Game Pass no Roblox e nós compramos para creditar o valor.
            - **Via Código de Ativação:** Para **Valorant Points, Riot Points (LoL), Google Play, PlayStation Store, Apple** e outros Gift Cards. Nós enviamos um código para o cliente resgatar no jogo ou na plataforma.
            - **Via ID do Jogador (UID):** Para **Free Fire, Mobile Legends, Genshin Impact, Honkai Star Rail** e a maioria dos outros jogos mobile. O cliente nos informa o ID da sua conta no jogo e creditamos os itens diretamente.
        - **Dono da Loja**: O dono da loja é o influencer `israelzinho2004`. 👑
        - **Horário de Funcionamento**: A loja funciona 24 horas por dia, 7 dias por semana. 🏪
        - **Tempo de Entrega**: As entregas são rápidas, mas podem levar no máximo até 72 horas em períodos de alta demanda.
        - **Descontos e Cupons**: Temos um desconto automático de 3% na primeira compra de Robux para novos clientes! Não precisa de código.
        - **Equipe de Atendimento**: Nossos atendentes são <@1073618577460039750>, <@952906000149667902> e <@986766209397694494>.
        - **Entregador Principal (Robux)**: Nosso entregador de Robux é o <@314200274933907456>.

        **Contexto dos Produtos da Loja (em formato JSON):**
        ```json
        {self.product_context}
        ```

        **Regras de Resposta:**
        1.  Seja sempre amigável e use emojis. 😊
        2.  Suas respostas devem ser curtas e diretas.
        3.  Baseie suas respostas **estritamente** nas informações do FAQ e do contexto JSON acima. Não invente nada.
        4.  Se perguntarem "como compro?", direcione para o canal <#{SALES_CHANNEL_ID}>.
        5.  Se perguntarem sobre a entrega de um produto específico, use a regra correta do FAQ.

        **Pergunta do Cliente:** "{user_question}"

        **Sua Resposta (como Israbuy):**
        """
        return prompt

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id != AI_CHANNEL_ID or message.reference:
            return
        
        if not self.model:
            return

        prompt = self.get_ai_prompt(message.content)

        async with message.channel.typing():
            try:
                # Otimização para respostas mais rápidas em perguntas simples
                if "como compro" in message.content.lower():
                    await message.reply(f"Opa! Para comprar é super fácil, basta ir no nosso canal de vendas <#{SALES_CHANNEL_ID}> e usar os painéis. ✨")
                    return

                response = await self.model.generate_content_async(prompt)
                await message.reply(response.text)
            
            except Exception as e:
                print(f"Erro ao chamar a API do Gemini: {e}")
                await message.reply("Ops! 😥 Parece que minha conexão com a inteligência artificial falhou. Tente novamente em um instante.")

async def setup(bot):
    await bot.add_cog(AIAssistant(bot))
