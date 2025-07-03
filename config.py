# config.py

import discord
import pytz

# --- IDs e Constantes Principais ---
GUILD_ID = 897650833888534588
ADMIN_ROLE_ID = 1379126175317622965
VIP_ROLE_ID = 1070823913308827678
CLIENT_ROLE_ID = 1380201405691727923

# --- IDs de Canais e Categorias ---
CATEGORY_VENDAS_ID = 1382399986725163140
CATEGORY_VENDAS_VIP_ID = 1382399986725163140
LOGS_COMPRAS_CHANNEL_ID = 1382340441579720846

# --- Configurações de Negócio e Aparência ---
ROBUX_DELIVERY_USER_ID = 314200274933907456
SITE_URL = "https://gorgeous-crisp-dc1e5e.netlify.app"
PIX_KEY_MANUAL = "d0092175-40d1-460b-b32c-114030c2ed24"
QR_CODE_URL = "https://gorgeous-crisp-dc1e5e.netlify.app/image.png"
IMAGE_URL_FOR_EMBEDS = "https://cdn.discordapp.com/attachments/1124738722588524606/1387468915268915260/standard.gif?ex=6697ee54&is=66969cd4&hm=088f1181829e0a64983a5494d6e9197c36b46187763d33235b91b65e8a5b6f4e&"
TUTORIAL_GAMEPASS_URL = "http://www.youtube.com/watch?v=B-LQU3J24pI"
FOOTER_TEXT = "Israbuy - Atendimento via Ticket"
ROSE_COLOR = discord.Color.from_rgb(255, 105, 180)
BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

# NOVO: Constante para cálculo de Robux customizado
# Usamos o preço do pacote de 1000 como base para o cálculo (41.00 / 1000 = 0.041 por Robux)
# Isso pode ser ajustado conforme sua estratégia de preço
ROBUX_PRICE_PER_UNIT = 0.041

# --- Banco de Dados de Produtos e Preços ---
PRODUCTS_DATA = {
    "Robux": {"emoji": "💎", "prices": {"100 Robux": 4.50, "200 Robux": 8.10, "300 Robux": 12.70, "400 Robux": 17.60, "500 Robux": 21.50, "600 Robux": 25.40, "700 Robux": 29.30, "800 Robux": 33.20, "900 Robux": 37.10, "1000 Robux": 41.00}, "vip_discount": {"1000 Robux": 5.00}},
    # ... O resto dos seus produtos continua igual
}

# --- Gerenciamento de Estado (Temporário) ---
ONGOING_SALES_DATA = {}
