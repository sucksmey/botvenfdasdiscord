# cogs/vendas.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
import math
import re
from datetime import datetime

# Importa todas as nossas configurações e a lista de tickets
from config import *

# --- Views (Menus e Botões) ---

# View para confirmar se o usuário sabe criar a Gamepass
class GamepassConfirmationView(discord.ui.View):
    def __init__(self, robux_amount: int):
        super().__init__(timeout=300) # Timeout de 5 minutos
        self.robux_amount = robux_amount

    @discord.ui.button(label="Sim, já sei criar", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)

        gamepass_value = math.ceil(self.robux_amount / 0.7)
        embed = discord.Embed(
            title="💎 Calculadora de Game Pass",
            description=(
                f"Para receber **{self.robux_amount} Robux**, você precisa criar uma Game Pass no valor de **{gamepass_value} Robux**.\n\n"
                "**Importante:** Ao criar, **NÃO** marque a opção de preços regionais.\n\n"
                "Por favor, envie o link da sua Game Pass aqui no chat."
            ),
            color=ROSE_COLOR
        )
        await interaction.response.send_message(embed=embed)
        ONGOING_SALES_DATA[interaction.channel.id]['status'] = 'awaiting_gamepass_link'

    @discord.ui.button(label="Não, preciso de ajuda", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button): # <-- CORREÇÃO: Removido o ponto duplo daqui
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)

        gamepass_value = math.ceil(self.robux_amount / 0.7)
        embed = discord.Embed(
            title="📄 Tutorial e Cálculo da Game Pass",
            description=(
                f"Sem problemas! Assista a este vídeo para aprender a criar sua Game Pass:\n{TUTORIAL_GAMEPASS_URL}\n\n"
                f"Após assistir, crie uma Game Pass de **{gamepass_value} Robux** e envie o link dela aqui no chat."
            ),
            color=ROSE_COLOR
        )
        await interaction.response.send_message(embed=embed)
        ONGOING_SALES_DATA[interaction.channel.id]['status'] = 'awaiting_gamepass_link'


# --- Cog Principal de Vendas ---

class Vendas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Listener para processar as mensagens dentro dos tickets
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        ticket_data = ONGOING_SALES_DATA.get(message.channel.id)
        if not ticket_data:
            return

        status = ticket_data.get("status")

        # Etapa 1: Cliente envia o comprovante de pagamento
        if status == "awaiting_payment" and message.attachments:
            await message.channel.send(f"Obrigado, {message.author.mention}! Seu comprovante foi recebido e está sendo processado.")
            
            try:
                client_role = message.guild.get_role(CLIENT_ROLE_ID)
                if client_role: await message.author.add_roles(client_role, reason="Iniciou uma compra.")
            except Exception as e:
                logging.error(f"Não foi possível adicionar o cargo de cliente: {e}")

            # Se for Robux, pede a gamepass
            if ticket_data.get("product_name") == "Robux":
                # Tenta extrair o valor do Robux do nome do item
                item_name = ""
                # Itera sobre os preços para encontrar o item correspondente
                for p_name, p_value in PRODUCTS_DATA["Robux"]["prices"].items():
                    if p_value == ticket_data.get("final_price"):
                        item_name = p_name
                        break
                
                if item_name:
                    robux_amount = int(re.sub(r'[^0-9]', '', item_name))
                    embed = discord.Embed(title="Entrega de Robux", description="Para a entrega, precisamos que você crie uma Game Pass. Você já sabe como fazer isso?", color=ROSE_COLOR)
                    await message.channel.send(embed=embed, view=GamepassConfirmationView(robux_amount=robux_amount))
                    ticket_data["status"] = "awaiting_gamepass_info" # Status intermediário
                else:
                    await message.channel.send("Não consegui determinar a quantidade de Robux. Um admin irá te ajudar.")
                    ticket_data["status"] = "delivery_pending"
            else:
                await message.channel.send(f"Sua compra de **{ticket_data.get('item_name')}** está em processamento. Um <@&{ADMIN_ROLE_ID}> irá finalizar a entrega em breve.")
                ticket_data["status"] = "delivery_pending"
            return

        # Etapa 2: Cliente envia o link da Gamepass
        if status == "awaiting_gamepass_link" and ("roblox.com/game-pass/" in message.content or "ro.blox.com/Ebh5" in message.content):
            delivery_user = self.bot.get_user(ROBUX_DELIVERY_USER_ID)
            mention = delivery_user.mention if delivery_user else f"<@{ROBUX_DELIVERY_USER_ID}>"
            
            await message.channel.send(f"Link da Game Pass recebido! O responsável pela entrega, {mention}, foi notificado e fará a compra em breve.")
            
            try:
                await message.channel.edit(name=f"entregar-{message.author.name}")
                ticket_data["status"] = "delivery_pending"
            except Exception as e:
                logging.error(f"Não foi possível renomear o canal {message.channel.id}: {e}")
            return

        # Etapa 0: Cliente digita o item que quer comprar
        if status == "awaiting_product_choice":
            product_category = ticket_data.get("product_name")
            product_info = PRODUCTS_DATA.get(product_category)
            if not product_info: return

            user_choice = message.content.strip()
            
            # Procura o item exato na lista de preços
            matched_item = None
            for item_name, price in product_info["prices"].items():
                if user_choice.lower() == item_name.lower():
                    matched_item = item_name
                    break
            
            if matched_item:
                is_vip = ticket_data.get("is_vip", False)
                price = product_info["prices"][matched_item]
                
                if product_category == "Robux" and is_vip and matched_item in product_info.get("vip_discount", {}):
                    price -= product_info["vip_discount"][matched_item]
                
                ticket_data.update({"status": "awaiting_payment", "final_price": price, "item_name": matched_item})
                
                await message.channel.send(f"Ótima escolha! O valor para **{matched_item}** é de **R$ {price:.2f}**.")
                pix_embed = discord.Embed(title="Pagamento via PIX", description="Use o QR Code acima ou a chave **Copia e Cola** enviada abaixo.", color=ROSE_COLOR).set_footer(text="Após pagar, por favor, envie o comprovante neste chat.").set_image(url=QR_CODE_URL)
                await message.channel.send(embed=pix_embed)
                await message.channel.send(f"`{PIX_KEY_MANUAL}`")
            else:
                await message.channel.send("Não encontrei este item. Por favor, digite o nome exatamente como está na tabela (ex: `1000 Robux`).")
            return


    # Comando /setupvendas para iniciar o painel de vendas
    @app_commands.command(name="setupvendas", description="Envia o painel de abertura de tickets de venda.")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.has_role(ADMIN_ROLE_ID)
    async def setupvendas(self, interaction: discord.Interaction):
        
        # O menu dropdown de seleção de produtos
        class ProductSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=name, emoji=data["emoji"]) for name, data in PRODUCTS_DATA.items()
                ]
                super().__init__(placeholder="Escolha um jogo ou serviço para comprar...", options=options)

            async def callback(self, select_interaction: discord.Interaction):
                await select_interaction.response.defer(ephemeral=True, thinking=True)
                
                selected_product = self.values[0]
                user = select_interaction.user
                guild = select_interaction.guild

                for channel_id, data in ONGOING_SALES_DATA.items():
                    if data.get("client_id") == user.id:
                        channel = guild.get_channel(channel_id)
                        if channel:
                            await select_interaction.followup.send(f"Você já possui um ticket aberto em {channel.mention}!", ephemeral=True)
                            return
                
                is_vip = any(role.id == VIP_ROLE_ID for role in user.roles)
                category_id = CATEGORY_VENDAS_VIP_ID if is_vip else CATEGORY_VENDAS_ID
                category = discord.utils.get(guild.categories, id=category_id)
                admin_role = guild.get_role(ADMIN_ROLE_ID)

                if not category or not admin_role:
                    await select_interaction.followup.send("Erro de configuração do servidor. Contate um administrador.", ephemeral=True)
                    return

                ticket_num = int(datetime.now().timestamp()) % 10000
                channel_name = f"ticket-{user.name}-{ticket_num:04d}"
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
                    admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
                new_channel = await guild.create_text_channel(
                    name=channel_name, category=category, overwrites=overwrites,
                    topic=f"Ticket de {user.display_name} | Produto: {selected_product} | ID: {user.id}"
                )

                product_info = PRODUCTS_DATA[selected_product]
                price_list = []
                for item, price in product_info.get("prices", {}).items():
                    final_price = price
                    if selected_product == "Robux" and is_vip and item in product_info.get("vip_discount", {}):
                        final_price -= product_info["vip_discount"][item]
                        price_list.append(f"**{item}**: R$ {final_price:.2f} (Preço VIP ✨)")
                    else:
                        price_list.append(f"**{item}**: R$ {final_price:.2f}")

                embed_title = f"Bem-vindo(a) ao seu ticket, {user.display_name}!"
                prices_text = "\n".join(price_list)
                
                embed = discord.Embed(title=embed_title, color=ROSE_COLOR)
                embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
                
                if prices_text:
                    embed.description = f"Você selecionou **{selected_product}** {product_info['emoji']}.\n\nConfira nossos preços abaixo e **digite o nome exato do item** que você deseja (ex: `100 Robux`)."
                    embed.add_field(name="Tabela de Preços", value=prices_text, inline=False)
                    status = "awaiting_product_choice"
                else:
                    embed.description = f"Você selecionou **{selected_product}** {product_info['emoji']}.\n\nUm de nossos atendentes irá te ajudar em breve para fazer o orçamento."
                    status = "awaiting_human"

                await new_channel.send(content=f"Olá {user.mention}! <@&{ADMIN_ROLE_ID}>", embed=embed)

                ONGOING_SALES_DATA[new_channel.id] = {
                    "client_id": user.id, "product_name": selected_product,
                    "status": status, "is_vip": is_vip
                }
                
                await select_interaction.followup.send(f"Seu ticket foi criado com sucesso em {new_channel.mention}!", ephemeral=True)

        class SetupView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                self.add_item(ProductSelect())

        embed = discord.Embed(
            title="✨ Bem-vindo(a) à Loja Israbuy!",
            description="Pronto para a melhor experiência de compra?\n\nSelecione um jogo ou serviço no menu abaixo para abrir um ticket de atendimento!",
            color=ROSE_COLOR
        )
        embed.set_thumbnail(url=IMAGE_URL_FOR_EMBEDS)
        embed.set_footer(text="Ao selecionar, um canal privado será criado para você.")
        await interaction.response.send_message(embed=embed, view=SetupView())


# Função obrigatória para o bot carregar este cog
async def setup(bot: commands.Bot):
    await bot.add_cog(Vendas(bot))
