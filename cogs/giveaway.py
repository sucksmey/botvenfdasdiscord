# cogs/giveaway.py
import discord
from discord import app_commands
from discord.ext import commands, tasks
import config
import random
import traceback

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites = {}
        self.bot.loop.create_task(self.load_invites())
        self.update_invite_giveaway_message.start()

    def cog_unload(self):
        self.update_invite_giveaway_message.cancel()

    async def load_invites(self):
        await self.bot.wait_until_ready()
        try:
            guild = self.bot.get_guild(config.GUILD_ID)
            if guild: self.invites[guild.id] = await guild.invites()
        except discord.Forbidden:
            print("AVISO: Permissão para ver convites negada. Sorteio por convites não funcionará.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != config.GUILD_ID or member.bot: return
        try:
            invites_after = await member.guild.invites()
            inviter = None
            for invite in self.invites[member.guild.id]:
                found = discord.utils.get(invites_after, code=invite.code)
                if found and found.uses > invite.uses:
                    inviter = invite.inviter
                    break
            self.invites[member.guild.id] = invites_after
            if inviter:
                async with self.bot.pool.acquire() as conn:
                    gw = await conn.fetchrow("SELECT message_id FROM giveaways WHERE gw_type = 'invites' AND is_active = TRUE")
                    if gw:
                        await conn.execute("""
                            INSERT INTO giveaway_participants (giveaway_message_id, user_id, progress_count) VALUES ($1, $2, 1)
                            ON CONFLICT (giveaway_message_id, user_id) DO UPDATE SET progress_count = giveaway_participants.progress_count + 1;
                        """, gw['message_id'], inviter.id)
        except Exception as e:
            print(f"Erro no on_member_join (giveaway): {e}")

    async def update_sales_giveaway(self, user_id: int):
        async with self.bot.pool.acquire() as conn:
            gw = await conn.fetchrow("SELECT message_id, channel_id, prize, goal, current_progress FROM giveaways WHERE gw_type = 'purchases' AND is_active = TRUE")
            if not gw: return

            new_progress = gw['current_progress'] + 1
            await conn.execute("UPDATE giveaways SET current_progress = $1 WHERE message_id = $2", new_progress, gw['message_id'])
            await conn.execute("""
                INSERT INTO giveaway_participants (giveaway_message_id, user_id, progress_count) VALUES ($1, $2, 1)
                ON CONFLICT (giveaway_message_id, user_id) DO UPDATE SET progress_count = giveaway_participants.progress_count + 1;
            """, gw['message_id'], user_id)

            channel = self.bot.get_channel(gw['channel_id'])
            if not channel: return
            
            try:
                msg = await channel.fetch_message(gw['message_id'])
                embed = msg.embeds[0]
                embed.set_field_at(1, name="Como Participar?", value=f"Sorteio válido até atingirmos **{gw['goal']}** vendas!\n**Restam: `{gw['goal'] - new_progress}` vendas!**", inline=False)
                await msg.edit(embed=embed)

                if new_progress >= gw['goal']:
                    await self.end_giveaway_logic(channel, gw['message_id'])
            except discord.NotFound:
                await conn.execute("UPDATE giveaways SET is_active = FALSE WHERE message_id = $1", gw['message_id'])

    @tasks.loop(minutes=5)
    async def update_invite_giveaway_message(self):
        async with self.bot.pool.acquire() as conn:
            gw = await conn.fetchrow("SELECT message_id, channel_id, goal FROM giveaways WHERE gw_type = 'invites' AND is_active = TRUE")
        if not gw: return

        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild: return

        channel = self.bot.get_channel(gw['channel_id'])
        if not channel: return
        
        try:
            msg = await channel.fetch_message(gw['message_id'])
            embed = msg.embeds[0]
            embed.set_field_at(1, name="Como Participar?", value=f"Convide no mínimo 3 pessoas (não-bots).\n**Progresso: `{guild.member_count} / {gw['goal']}` membros!**", inline=False)
            await msg.edit(embed=embed)
        except discord.NotFound:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("UPDATE giveaways SET is_active = FALSE WHERE message_id = $1", gw['message_id'])

    sorteio_group = app_commands.Group(name="sorteio", description="Comandos para gerenciar sorteios.", guild_ids=[config.GUILD_ID])

    @sorteio_group.command(name="iniciar_vendas", description="[Admin] Inicia um sorteio por 20 vendas.")
    async def start_sales_giveaway(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🛍️ Sorteio por Vendas Ativo! 🛍️", description="Corra para garantir sua participação antes que acabe!", color=0x3498DB)
        embed.add_field(name="Prêmio", value="**2.000 Robux**", inline=False)
        embed.add_field(name="Como Participar?", value="Sorteio válido até atingirmos **20** vendas!\n**Restam: `20` vendas!**", inline=False)
        gw_message = await interaction.channel.send("@everyone", embed=embed)
        async with self.bot.pool.acquire() as conn:
            await conn.execute("INSERT INTO giveaways (message_id, channel_id, prize, gw_type, goal, current_progress) VALUES ($1, $2, '2.000 Robux', 'purchases', 20, 0)", gw_message.id, interaction.channel.id)
        await interaction.followup.send("Sorteio por vendas iniciado!", ephemeral=True)

    @sorteio_group.command(name="iniciar_convites", description="[Admin] Inicia um sorteio por convites até 1000 membros.")
    async def start_invite_giveaway(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="📈 Sorteio por Indicação Ativo! 📈", description="Quanto mais você convida, mais chances tem de ganhar!", color=discord.Color.purple())
        embed.add_field(name="Prêmio", value="**1.000 Robux**", inline=False)
        embed.add_field(name="Como Participar?", value=f"Convide no mínimo 3 pessoas (não-bots).\n**Progresso: `{interaction.guild.member_count} / 1000` membros!**", inline=False)
        embed.add_field(name="Ingressos", value="A cada 3 convidados você ganha 1 ingresso. Use `/ingresso` para ver os seus.", inline=False)
        gw_message = await interaction.channel.send("@everyone", embed=embed)
        async with self.bot.pool.acquire() as conn:
            await conn.execute("INSERT INTO giveaways (message_id, channel_id, prize, gw_type, goal) VALUES ($1, $2, '1.000 Robux', 'invites', 1000)", gw_message.id, interaction.channel.id)
        await interaction.followup.send("Sorteio por convites iniciado!", ephemeral=True)

    @app_commands.command(name="ingresso", description="Verifica quantos ingressos você tem para o sorteio de convites.")
    async def check_tickets(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with self.bot.pool.acquire() as conn:
            gw = await conn.fetchrow("SELECT message_id FROM giveaways WHERE gw_type = 'invites' AND is_active = TRUE")
            if not gw: return await interaction.followup.send("Não há um sorteio por convites ativo no momento.", ephemeral=True)
            
            progress = await conn.fetchval("SELECT progress_count FROM giveaway_participants WHERE giveaway_message_id = $1 AND user_id = $2", gw['message_id'], interaction.user.id) or 0
        
        tickets = progress // 3
        await interaction.followup.send(f"Você convidou **{progress}** pessoas e tem **{tickets}** ingresso(s) para o sorteio de convites. Continue convidando!", ephemeral=True)

    @sorteio_group.command(name="terminar", description="[Admin] Termina um sorteio e sorteia o vencedor (se a meta foi atingida).")
    @app_commands.checks.has_role(config.ADMIN_ROLE_ID)
    async def end_giveaway(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.end_giveaway_logic(interaction.channel, None, interaction)

    async def end_giveaway_logic(self, channel, message_id=None, interaction=None):
        """Lógica central para terminar um sorteio."""
        async with self.bot.pool.acquire() as conn:
            gw_data = await conn.fetchrow("SELECT message_id, prize, gw_type, goal FROM giveaways WHERE channel_id = $1 AND is_active = TRUE", channel.id)
            if not gw_data:
                if interaction: await interaction.followup.send("Nenhum sorteio ativo encontrado neste canal.", ephemeral=True)
                return

            if gw_data['gw_type'] == 'invites' and channel.guild.member_count < gw_data['goal']:
                if interaction: await interaction.followup.send(f"O sorteio não pode ser encerrado. A meta de {gw_data['goal']} membros ainda não foi atingida.", ephemeral=True)
                return

            requirement = 3 if gw_data['gw_type'] == 'invites' else 1
            participants_data = await conn.fetch("SELECT user_id, progress_count FROM giveaway_participants WHERE giveaway_message_id = $1 AND progress_count >= $2", gw_data['message_id'], requirement)
            
            winner_text = ""
            if not participants_data:
                winner_text = f"Que pena! Ninguém cumpriu os requisitos para o sorteio de **{gw_data['prize']}**. O sorteio foi encerrado sem um vencedor."
            else:
                # Cria uma lista ponderada com base nos ingressos
                weighted_list = []
                for p in participants_data:
                    tickets = p['progress_count'] // requirement
                    weighted_list.extend([p['user_id']] * tickets)
                
                if not weighted_list:
                    winner_text = f"Ninguém conseguiu ingressos suficientes para o sorteio de **{gw_data['prize']}**. Encerrado sem vencedor."
                else:
                    winner_id = random.choice(weighted_list)
                    winner_text = f"O sorteio de **{gw_data['prize']}** terminou!\n\nParabéns ao grande vencedor: <@{winner_id}>! 🥳🎉"

            await conn.execute("UPDATE giveaways SET is_active = FALSE WHERE message_id = $1", gw_data['message_id'])
        
        if interaction:
            await interaction.followup.send(winner_text, allowed_mentions=discord.AllowedMentions(users=True))
        else:
            await channel.send(winner_text, allowed_mentions=discord.AllowedMentions(users=True))
        
async def setup(bot):
    await bot.add_cog(Giveaway(bot))
