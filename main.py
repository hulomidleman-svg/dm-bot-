
import os
import json
import random
import asyncio
import discord

from discord import app_commands
from discord.ext import commands

TOKEN = os.environ["DISCORD_TOKEN"]

DATA_FILE = "bot_data.json"

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

data = {
    "message": "Hallo! 👋",
    "subscribers": {},
    "running": False,
    "sent": {}
}


def load_data():
    global data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
            data.update(saved)
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as error:
        print(f"Fehler beim Laden: {error}")


def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as error:
        print(f"Fehler beim Speichern: {error}")


def is_admin(interaction: discord.Interaction):
    return (
        interaction.guild is not None
        and interaction.user.guild_permissions.administrator
    )


@bot.event
async def on_ready():
    load_data()

    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} Slash Commands synchronisiert.")
    except Exception as error:
        print(f"Sync-Fehler: {error}")

    print(f"Eingeloggt als {bot.user}")


@bot.tree.command(
    name="text",
    description="Legt die DM-Nachricht fest"
)
@app_commands.describe(nachricht="Der Text, den der Bot senden soll")
async def text_command(
    interaction: discord.Interaction,
    nachricht: str
):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "Du brauchst Administratorrechte.",
            ephemeral=True
        )
        return

    if len(nachricht) > 1800:
        await interaction.response.send_message(
            "Der Text darf maximal 1800 Zeichen lang sein.",
            ephemeral=True
        )
        return

    data["message"] = nachricht
    save_data()

    await interaction.response.send_message(
        "Nachricht wurde gespeichert.",
        ephemeral=True
    )


@bot.tree.command(
    name="subscribe",
    description="Melde dich für Bot-Direktnachrichten an"
)
async def subscribe(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "Nutze diesen Befehl in einem Server.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    user_id = interaction.user.id

    subscribers = data["subscribers"].setdefault(guild_id, [])

    if user_id not in subscribers:
        subscribers.append(user_id)
        save_data()

    await interaction.response.send_message(
        "Du hast dich für Direktnachrichten angemeldet.",
        ephemeral=True
    )


@bot.tree.command(
    name="unsubscribe",
    description="Melde dich von Bot-Direktnachrichten ab"
)
async def unsubscribe(interaction: discord.Interaction):
    if interaction.guild is not None:
        guild_id = str(interaction.guild.id)
        user_id = interaction.user.id

        subscribers = data["subscribers"].setdefault(guild_id, [])
        data["subscribers"][guild_id] = [
            uid for uid in subscribers if uid != user_id
        ]
        save_data()

    await interaction.response.send_message(
        "Du bist abgemeldet.",
        ephemeral=True
    )


@bot.tree.command(
    name="start",
    description="Startet den DM-Versand"
)
async def start(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "Du brauchst Administratorrechte.",
            ephemeral=True
        )
        return

    if data["running"]:
        await interaction.response.send_message(
            "Der Versand läuft bereits.",
            ephemeral=True
        )
        return

    if interaction.guild is None:
        await interaction.response.send_message(
            "Nutze diesen Befehl in einem Server.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    subscribers = list(data["subscribers"].get(guild_id, []))

    if not subscribers:
        await interaction.response.send_message(
            "Noch keine angemeldeten Mitglieder. Nutze /subscribe.",
            ephemeral=True
        )
        return

    data["running"] = True
    save_data()

    await interaction.response.send_message(
        f"Versand an {len(subscribers)} angemeldete Mitglieder gestartet.",
        ephemeral=True
    )

    random.shuffle(subscribers)

    try:
        for user_id in subscribers:
            if not data["running"]:
                break

            # Abmeldung während des Versands beachten
            current = data["subscribers"].get(guild_id, [])
            if user_id not in current:
                continue

            try:
                user = await bot.fetch_user(user_id)
                await user.send(data["message"])

                data["sent"][str(user_id)] = (
                    data["sent"].get(str(user_id), 0) + 1
                )
                save_data()

            except discord.Forbidden:
                print(f"DM für Nutzer {user_id} nicht verfügbar.")

            except discord.HTTPException as error:
                print(f"Discord-Fehler für {user_id}: {error}")

            await asyncio.sleep(3)

    finally:
        data["running"] = False
        save_data()

    print("Versand beendet.")


@bot.tree.command(
    name="stop",
    description="Stoppt den laufenden Versand"
)
async def stop(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "Du brauchst Administratorrechte.",
            ephemeral=True
        )
        return

    if not data["running"]:
        await interaction.response.send_message(
            "Es läuft gerade kein Versand.",
            ephemeral=True
        )
        return

    data["running"] = False
    save_data()

    await interaction.response.send_message(
        "Versand wird gestoppt.",
        ephemeral=True
    )


@bot.tree.command(
    name="status",
    description="Zeigt den Bot-Status"
)
async def status(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "Du brauchst Administratorrechte.",
            ephemeral=True
        )
        return

    guild_id = str(interaction.guild_id)
    count = len(data["subscribers"].get(guild_id, []))

    await interaction.response.send_message(
        f"**Status:** {'Läuft' if data['running'] else 'Gestoppt'}\n"
        f"**Angemeldete Mitglieder:** {count}\n"
        f"**Nachricht:** {data['message']}\n"
        f"**Gesendete DMs:** {sum(data['sent'].values())}",
        ephemeral=True
    )


load_data()
bot.run(TOKEN)
