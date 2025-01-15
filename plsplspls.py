import discord
import pytesseract
from PIL import Image, ImageOps
import json
from tabulate import tabulate  # For pretty table formatting
import re
from concurrent.futures import ThreadPoolExecutor
import asyncio
import numpy as np
import pickle
from os import path
import os
from datetime import datetime

# Set up Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'  

# Initialize client
intents = discord.Intents.default()
intents.message_content = True  # To read message content and attachments
client = discord.Client(intents=intents)

# File paths for points table and player stats
POINTS_TABLE_FILE = "points_table.json"
PLAYER_STATS_FILE = "player_stats.json"

# Load or initialize points table
try:
    with open(POINTS_TABLE_FILE, "r") as f:
        points_table = json.load(f)
except FileNotFoundError:
    points_table = {}

# Load or initialize player stats
try:
    with open(PLAYER_STATS_FILE, "r") as f:
        player_stats = json.load(f)
        # If the data is a list, convert it to a dictionary
        if isinstance(player_stats, list):
            player_stats = {player["name"]: player["stats"] for player in player_stats}
except FileNotFoundError:
    player_stats = {}


def get_normalized_ocr_read(image_path):
    image = Image.open(image_path)
    grayscale_image = ImageOps.grayscale(image)  # Convert to grayscale for OCR
    threshold_image = grayscale_image.point(lambda p: p > 150 and 255)  # Simple binarization

    # Perform OCR to extract raw text
    text:str = pytesseract.image_to_string(threshold_image)

    # Clean up and split the text into lines
    with open('nomalizer.txt','w') as fp:
        fp.write(text)

    input("Nomalize Text:")

    with open('nomalizer.txt','r') as fp:
        text = fp.read()
    return text

def get_batter_from_str(line):
    if not line.strip():
        return None
    splited = line.split(' ')
    curr_data = {}
    last_flag = 'batter'
    has_runs = False
    for word in splited:
        if word == '': 
            continue
        if word.isnumeric():
            curr_data['balls' if has_runs else 'runs'] = float(word)
            has_runs = True
            continue
        if word in ('c','b','lbw'):
            last_flag = word
            continue
        curr_data[last_flag] = word+' ' if last_flag not in curr_data else curr_data[last_flag]+word+' '

    curr_data['batting_fpl'] = 0  # Changed to batting_fpl
    curr_data['fpl'] = 0  # Keep total fpl for compatibility

    # Calculate fantasy points
    runs = curr_data.get('runs', 0)
    balls = curr_data.get('balls', 0)

    # Points for runs
    curr_data['batting_fpl'] += runs

    # Strike rate calculation and bonus
    if balls >= 10:  # Strike rate bonus only applies if balls faced >= 10
        strike_rate = (runs / balls) * 100 if balls > 0 else 0
        if 50 <= strike_rate < 75:
            curr_data['batting_fpl'] -= 2
        elif 140 <= strike_rate < 180:
            curr_data['batting_fpl'] += 5
        elif strike_rate >= 180:
            curr_data['batting_fpl'] += 10

    # Milestone bonuses
    if runs >= 50.0:
        curr_data['batting_fpl'] += 10
    if runs >= 100.0:
        curr_data['batting_fpl'] += 25
        
    curr_data['fpl'] = curr_data['batting_fpl']  # Set total fpl to batting points

    return curr_data

def update_batter_stats(prev, curr):
    for i in ('runs', 'balls'):
        prev[i] += curr[i]
    # Update batting FPL separately
    prev['batting_fpl'] = curr['batting_fpl']  # Use the new batting points
    prev['fpl'] = prev.get('bowling_fpl', 0) + prev['batting_fpl']  # Total = bowling + batting
    return prev


def get_bowler_from_str(line):
    if not line.strip():
        return None
    splited = line.split(' ')
    curr_data = {}
    last_flag = 'bowler'
    STAT_KEYS = ['overs','maidens','runs','wickets','economy','fpl']
    IGNORE_STATS = ['economy']
    num_i = 0
    for word in splited:
        if word == '': 
            continue
        if word.isnumeric() or word.replace('.','').isnumeric():
            if not STAT_KEYS[num_i] in IGNORE_STATS:
                curr_data[STAT_KEYS[num_i]] = float(word)
            num_i+=1
            continue
        curr_data[last_flag] = word+' ' if last_flag not in curr_data else curr_data[last_flag]+word+' '

    curr_data['bowling_fpl'] = 0  # Changed to bowling_fpl
    curr_data['fpl'] = 0  # Keep total fpl for compatibility
    
    # Calculate fantasy points
    wickets = curr_data.get('wickets', 0)
    maidens = curr_data.get('maidens', 0)
    overs = curr_data.get('overs', 0)
    runs = curr_data.get('runs', 0)
    
    # Points for wickets
    curr_data['bowling_fpl'] += wickets * 25
    
    # Bonus for 5-wicket haul
    if wickets >= 5:
        curr_data['bowling_fpl'] += 25
    
    # Points for maidens
    curr_data['bowling_fpl'] += maidens * 10
    
    # Economy rate and bonus points (only if bowled at least 2 overs)
    if overs >= 2:
        economy_rate = runs / overs
        if economy_rate < 5.0:
            curr_data['bowling_fpl'] += 15
        elif economy_rate < 6.5:
            curr_data['bowling_fpl'] += 10
        elif economy_rate < 11.0:
            curr_data['bowling_fpl'] += 5
        elif economy_rate < 14.0:
            curr_data['bowling_fpl'] += 0
        else:
            curr_data['bowling_fpl'] -= 5

    curr_data['fpl'] = curr_data['bowling_fpl']  # Set total fpl to bowling points
    return curr_data

def update_bowler_stats(prev, curr):
    for i in ('overs', 'maidens', 'runs', 'wickets'):
        prev[i] += curr[i]
    # Update bowling FPL separately
    prev['bowling_fpl'] = curr['bowling_fpl']  # Use the new bowling points
    prev['fpl'] = prev.get('batting_fpl', 0) + prev['bowling_fpl']  # Total = batting + bowling
    return prev

# Helper function to process a scorecard with layout analysis and OCR
def process_scorecard(image_path, is_batting):
    stats_file_path = "b_stats.pkl" if is_batting else "f_stats.pkl"
    check_path = "f_stats.pkl" if is_batting else "b_stats.pkl"
    player_key = 'batter' if is_batting else 'bowler'
    check_key = 'bowler' if is_batting else 'batter'
    
    try:
        # Generate unique match ID using timestamp
        match_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Process scorecard and get player points as before
        text = get_normalized_ocr_read(image_path)
        lines = text.strip().split("\n")
        data = []

        # Load existing stats
        if path.isfile(stats_file_path):
            with open(stats_file_path, 'rb') as f:
                data = pickle.load(f)
        
        # Process new scorecard data and update stats as before
        new_entries = []
        for line in lines:
            val = (get_batter_from_str if is_batting else get_bowler_from_str)(line)
            if not val:
                continue
            new_entries.append(val)

        # Calculate match points
        match_points = {}
        
        # Update existing entries or add new ones
        for new_entry in new_entries:
            found = False
            for i in range(len(data)):
                if data[i][player_key].strip() == new_entry[player_key].strip():
                    data[i] = (update_batter_stats if is_batting else update_bowler_stats)(data[i], new_entry)
                    found = True
                    break
            if not found:
                data.append(new_entry)

            # Store match points for this player
            player_name = new_entry[player_key].strip()
            match_points[player_name] = new_entry['fpl']  # Base points

        # Load complementary stats
        complementary_data = []
        if path.isfile(check_path):
            with open(check_path, 'rb') as f:
                complementary_data = pickle.load(f)

        # Add bonus points
        for player_name, points in match_points.items():
            # Find player in data
            player_stat = next((p for p in data if p[player_key].strip() == player_name), None)
            if player_stat:
                # Individual bonuses
                if is_batting and player_stat['runs'] >= 150.0:
                    match_points[player_name] += 50
                elif not is_batting and player_stat['wickets'] > 8.0:
                    match_points[player_name] += 50

                # Combined bonuses
                for comp_stat in complementary_data:
                    if player_name == comp_stat[check_key].strip():
                        if is_batting:
                            if 100 <= player_stat['runs'] < 200 and 4 <= comp_stat['wickets'] < 8.0:
                                match_points[player_name] += 50
                            elif player_stat['runs'] >= 200.0 and comp_stat['wickets'] > 8.0:
                                match_points[player_name] += 100
                        else:
                            if 100 <= comp_stat['runs'] < 200 and 4 <= player_stat['wickets'] < 8.0:
                                match_points[player_name] += 50
                            elif comp_stat['runs'] >= 200.0 and player_stat['wickets'] > 8.0:
                                match_points[player_name] += 100

        # Save match points to separate file
        match_points_file = f'match_points_{match_id}.pkl'
        with open(match_points_file, 'wb') as f:
            pickle.dump(match_points, f)

        # Update fantasy teams with new points
        update_fantasy_teams(match_points)

        # Save main stats
        with open(stats_file_path, 'wb') as f:
            pickle.dump(data, f)
        
        return data
    
    except Exception as e:
        print(f"Error processing scorecard: {e}")
        return [], []

def update_fantasy_teams(match_points):
    """Update fantasy teams with new match points"""
    try:
        # Load existing teams
        fantasy_teams = []
        if os.path.exists('fpdbs.pkl'):
            with open('fpdbs.pkl', 'rb') as fr:
                while True:
                    try:
                        fantasy_teams.append(pickle.load(fr))
                    except EOFError:
                        break
        
        # Update points for each team
        for team in fantasy_teams:
            for player_name in team:
                if player_name == 'Team_Name':
                    continue
                if player_name.strip() in match_points:
                    team[player_name] = team[player_name] + match_points[player_name.strip()]

        # Save updated teams
        with open('fpdbs.pkl', 'wb') as fw:
            for team in fantasy_teams:
                pickle.dump(team, fw)
                
    except Exception as e:
        print(f"Error updating fantasy teams: {e}")

def save_team(tname, players):
    """Create new fantasy team"""
    # Create team with zero initial points
    team = {'Team_Name': tname}
    for player in players:
        team[player] = 0
    
    # Add up points from all previous matches
    match_files = [f for f in os.listdir() if f.startswith('match_points_') and f.endswith('.pkl')]
    
    for match_file in match_files:
        with open(match_file, 'rb') as f:
            match_points = pickle.load(f)
            for player in players:
                if player.strip() in match_points:
                    team[player] += match_points[player.strip()]
    
    # Save to file
    with open('fpdbs.pkl', 'ab') as f:
        pickle.dump(team, f)

def display_flb():
    """Display fantasy leaderboard"""
    try:
        # Read fantasy teams
        fantasy_teams = []
        with open('fpdbs.pkl', 'rb') as fr:
            while True:
                try:
                    fantasy_teams.append(pickle.load(fr))
                except EOFError:
                    break
                
        # Build output string
        out = 'Fantasy Points:\n\n'
        lb = {}

        # Process each team
        for team in fantasy_teams:
            total = 0
            out += f"Team Name: {team['Team_Name']}\n"
            
            for player_name, points in team.items():
                if player_name == 'Team_Name':
                    continue
                out += f"{player_name:<20} {points}\n"
                total += points
            
            out += f"Total = {total}\n\n"
            lb[team['Team_Name']] = total

        # Sort teams by points and display leaderboard
        sorted_teams = sorted(lb.items(), key=lambda x: x[1], reverse=True)
        out += "Fantasy Leaderboard\n\n"
        for team_name, total_points in sorted_teams:
            out += f"Team Name : {team_name:<10} Fantasy Points = {total_points}\n\n"
        
        return out
        
    except Exception as e:
        return f"Error displaying leaderboard: {e}"


# Display Player Stats
def display_player_stats():
    batting_data = []
    bowling_data = []
    if path.isfile("b_stats.pkl"):
        with open('b_stats.pkl', 'rb') as f:
            batting_data = pickle.load(f)
    if path.isfile("f_stats.pkl"):
        with open('f_stats.pkl', 'rb') as f:
            bowling_data = pickle.load(f)
    
    # Create a player points dictionary to keep track of total points
    player_points = {}
    
    # Add batting points
    for player in batting_data:
        player_name = player['batter'].strip()
        player_points[player_name] = player_points.get(player_name, 0) + player.get('batting_fpl', 0)
    
    # Add bowling points
    for player in bowling_data:
        player_name = player['bowler'].strip()
        player_points[player_name] = player_points.get(player_name, 0) + player.get('bowling_fpl', 0)
    
    count = 1
    out = "Most Runs:\n"
    for i in sorted(batting_data, reverse=True, key=lambda x: x['runs']):
        try:
            if count > 10:
                break
            player_name = i['batter'].strip()
            total_points = player_points.get(player_name, 0)  # Get total points including both batting and bowling
            out += f"{player_name:<40} {int(i['runs']):<10} {round(i['runs']*100/i['balls'],2):<10} {total_points}\n"
            count += 1
        except:
            count += 1
            break

    count = 1
    out += "\nMost Wickets:\n"
    for i in sorted(bowling_data, reverse=True, key=lambda x: x['wickets']):
        if count > 10:
            break
        player_name = i['bowler'].strip()
        total_points = player_points.get(player_name, 0)  # Get total points including both batting and bowling
        out += f"{player_name:<40} {int(i['wickets']):<10} {round((i['runs']*6)/((int(i['overs'])*6)+(int((i['overs'] % 1) * 10))),2):<10}  {total_points}\n"
        count += 1
    
    return out

# Discord bot events
@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!pr"):
        # if len(message.attachments) < 2:
        #     await message.channel.send("❌ Please upload **both innings scorecard images** to process the match.")
        #     return

        # Save attachments locally
        image_paths = []
        for i, attachment in enumerate(message.attachments):
            image_path = f"innings_{i + 1}.png"
            await attachment.save(image_path)
            image_paths.append(image_path)

        # Process both innings
        innings_data = []
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            for i, image_path in enumerate(image_paths):
                innings_score = await loop.run_in_executor(pool, process_scorecard, image_path, message.content.startswith('!prb'))
                if not innings_score:
                    await message.channel.send(f"❌ Failed to process innings {i + 1}. Please check the scorecard image.")
                    return
                innings_data.append(innings_score)

        # Update stats for both teams
        #team1, team2 = "Team 1", "Team 2"  # You can modify team names dynamically
        #update_stats_and_points(team1, innings_data[0], sum([runs for _, runs, _ in innings_data[0]]))
        #update_stats_and_points(team2, innings_data[1], sum([runs for _, runs, _ in innings_data[1]]))

        await message.channel.send("✅ Scorecards processed successfully. Points table and player stats updated.")


    elif message.content.startswith("!stats"):
        await message.channel.send(display_player_stats())

    elif message.content.startswith("!flb"):
        await message.channel.send(display_flb())

    elif message.content.startswith("!addteam"):
        try:
            # Extract team from the message
            players=[]
            team_string = message.content[len("!addteam "):].strip()
            for player in team_string.split(","):
                players.append(player)

            if len(players) != 11:
                await message.channel.send("❌ Please provide exactly 11 players, separated by commas.")
                return

            team_name = f"{message.author.name}"  # Example unique identifier per user
            save_team(team_name, players)

            await message.channel.send(f"✅ Team added successfully: {', '.join(players)}")
        except Exception as e:
            await message.channel.send("❌ Failed to add team. Ensure the format is correct: `!addteam <player1>,<player2>,...,<player11>`")

    elif message.content.startswith("!about"):
    # Create an embed message
        embed = discord.Embed(
            title="📋 Bot Commands",
            description="Here is the list of commands you can use:",
            color=discord.Color.blue()
        )
        
        # Add fields for each command
        embed.add_field(
            name="1. `!pr` - Process the cricket match scorecard images",
            value=(
                "- **Batting Scorecard of an Inning**\n"
                "  - **Syntax:** `!prb [batting scorecard attachment]`\n"
                "- **Bowling Scorecard of an Inning**\n"
                "  - **Syntax:** `!prf [bowling scorecard attachment]`"
            ),
            inline=False
        )
        embed.add_field(
            name="2. `!stats` - Shows Leaderboard",
            value="**Syntax:** `!stats`",
            inline=False
        )
        embed.add_field(
            name="3. `!addteam` - Create and save a team consisting of 11 players",
            value=(
                "- **Syntax:** `!addteam <player1>,<player2>,<player3>,...,<player11>`\n"
                "- `<player1>, <player2>, ... <player11>`: List of 11 player names separated by commas. Add a space after each comma."
            ),
            inline=False
        )
        embed.add_field(
            name="4. `!flb` - Show Fantasy Team Leaderboard",
            value="**Syntax:** `!flb`",
            inline=False
        )
        embed.add_field(
            name="5. `!about` - Show this message",
            value="Displays the list of available commands.",
            inline=False
        )

        # Footer with developer credit
        embed.set_footer(text="Developed by PR 😉")

        # Send the embed message
        await message.channel.send(embed=embed)


# Run the bot
client.run("MTMyNjE5MDEyNDg1MzM2Njc4NA.Geyvif.NxvS2-qZbSSfdMJyhK5-IMLF3Ci5YuUrWTjX-8")