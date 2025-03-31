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
from datetime import datetime, time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'  

# Initialize client
intents = discord.Intents.default()
intents.message_content = True  # To read message content and attachments
intents.members = True  # Add this if you need member-related functionality
client = discord.Client(intents=intents)

# Admin user ID (replace with your Discord user ID)
ADMIN_USER_ID = 796665468664021012  # Replace this with your actual Discord user ID

def is_admin(user):
    """Check if the user is an admin"""
    return user.id == ADMIN_USER_ID

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
        
        if not fantasy_teams:
            out = "New Season Starting Soon!\n"
        return out
        
    except Exception as e:
        return f"Error displaying leaderboard: {e}"

def display_player_stats():
    batting_data = []
    bowling_data = []
    try:
        if path.isfile("b_stats.pkl"):
            with open('b_stats.pkl', 'rb') as f:
                try:
                    batting_data = pickle.load(f)
                except EOFError:
                    batting_data = []
                    
        if path.isfile("f_stats.pkl"):
            with open('f_stats.pkl', 'rb') as f:
                try:
                    bowling_data = pickle.load(f)
                except EOFError:
                    bowling_data = []
    except Exception as e:
        return f"Error loading stats files: {e}"
    
    # Create a player points dictionary to keep track of total points
    player_points = {}
    
    # Add batting points from all matches
    match_files = [f for f in os.listdir() if f.startswith('match_points_') and f.endswith('.pkl')]
    
    # Process all match files to get cumulative points
    for match_file in match_files:
        try:
            with open(match_file, 'rb') as f:
                try:
                    match_points = pickle.load(f)
                    for player_name, points in match_points.items():
                        player_points[player_name] = player_points.get(player_name, 0) + points
                except EOFError:
                    continue
        except Exception as e:
            print(f"Error reading match file {match_file}: {e}")
            continue
    
    count = 1
    out = "Top 10 Run Scorers:\n"
    # Sort by runs (descending) and then by strike rate (descending)
    for i in sorted(batting_data, reverse=True, key=lambda x: (x['runs'], (x['runs']*100/x['balls'] if x['balls'] > 0 else 0))):
        try:
            if count > 10:
                break
            player_name = i['batter'].strip()
            total_points = player_points.get(player_name, 0)  # Get cumulative points from all matches
            out += f"{player_name:<40} {int(i['runs']):<10} {round(i['runs']*100/i['balls'],2):<10} {total_points}\n"
            count += 1
        except Exception as e:
            print(f"Error processing batting stats: {e}")
            count += 1
            continue

    count = 1
    out += "\nTop 10 Wicket Takers:\n"
    # Sort by wickets (descending) and then by economy rate (ascending)
    for i in sorted(bowling_data, reverse=True, key=lambda x: (x['wickets'], -1 * (x['runs']*6/((int(x['overs'])*6)+(int((x['overs'] % 1) * 10))) if x['overs'] > 0 else float('inf')))):
        if count > 10:
            break
        try:
            player_name = i['bowler'].strip()
            total_points = player_points.get(player_name, 0)  # Get cumulative points from all matches
            out += f"{player_name:<40} {int(i['wickets']):<10} {round((i['runs']*6)/((int(i['overs'])*6)+(int((i['overs'] % 1) * 10))),2):<10}  {total_points}\n"
            count += 1
        except Exception as e:
            print(f"Error processing bowling stats: {e}")
            count += 1
            continue

    if not batting_data and not bowling_data:
        out = "New Season Starting Soon!\n"
    
    return out

def display_archived_stats(season, stat_type=None):
    """Display archived stats from a specific season"""
    try:
        # Map season numbers to file names
        season_files = {
            1: {},
            2: {
                'batting': 'b_statsS2.pkl',
                'bowling': 'f_statsS2.pkl',
                'fantasy': 'fpdbsS2.pkl'
            }
        }
        
        if season not in season_files:
            return [f"❌ Season {season} stats unavailable yet."]
        
        if season == 1:
            with open ('StatsS1.txt','r',encoding='utf-8') as fp:
                x=fp.read()
                return [f"{x}"]

            
        files = season_files[season]
        batting_data = []
        bowling_data = []
        fantasy_data = []
        
        # Load batting stats
        if path.isfile(files['batting']):
            with open(files['batting'], 'rb') as f:
                batting_data = pickle.load(f)
                
        # Load bowling stats
        if path.isfile(files['bowling']):
            with open(files['bowling'], 'rb') as f:
                bowling_data = pickle.load(f)
                
        # Load fantasy stats
        if path.isfile(files['fantasy']):
            with open(files['fantasy'], 'rb') as f:
                while True:
                    try:
                        fantasy_data.append(pickle.load(f))
                    except EOFError:
                        break
        
        # Split output into multiple messages
        messages = []
        
        # If stat_type is specified, show all stats for that type
        if stat_type == 'batting':
            out = f"🏏 Season {season} - All Batting Stats 🏏\n\n"
            out += "Player Name" + " " * 30 + "Runs" + " " * 5 + "SR\n"
            out += "-" * 70 + "\n"
            current_message = out
            # Sort by runs (descending) and then by strike rate (descending)
            for i in sorted(batting_data, reverse=True, key=lambda x: (x['runs'], (x['runs']*100/x['balls'] if x['balls'] > 0 else 0))):
                player_name = i['batter'].strip()
                # Handle case where balls faced is 0
                strike_rate = round(i['runs']*100/i['balls'], 2) if i['balls'] > 0 else 0
                player_line = f"{player_name:<40} {int(i['runs']):<10} {strike_rate:<10}\n"
                
                # If adding this player would exceed Discord's limit, start a new message
                if len(current_message + player_line) > 1900:  # Using 1900 to be safe
                    messages.append(current_message)
                    current_message = "Player Name" + " " * 30 + "Runs" + " " * 5 + "SR\n"
                    current_message += "-" * 70 + "\n" + player_line
                else:
                    current_message += player_line
            
            # Add the last message if it's not empty
            if current_message:
                messages.append(current_message)
            
        elif stat_type == 'bowling':
            out = f"🏏 Season {season} - All Bowling Stats 🏏\n\n"
            out += "Player Name" + " " * 30 + "Wickets" + " " * 5 + "Econ\n"
            out += "-" * 70 + "\n"
            current_message = out
            # Sort by wickets (descending) and then by economy rate (ascending)
            for i in sorted(bowling_data, reverse=True, key=lambda x: (x['wickets'], -1 * (x['runs']*6/((int(x['overs'])*6)+(int((x['overs'] % 1) * 10))) if x['overs'] > 0 else float('inf')))):
                player_name = i['bowler'].strip()
                # Handle case where overs is 0
                economy = round((i['runs']*6)/((int(i['overs'])*6)+(int((i['overs'] % 1) * 10))), 2) if i['overs'] > 0 else 0
                player_line = f"{player_name:<40} {int(i['wickets']):<10} {economy:<10}\n"
                
                # If adding this player would exceed Discord's limit, start a new message
                if len(current_message + player_line) > 1900:  # Using 1900 to be safe
                    messages.append(current_message)
                    current_message = "Player Name" + " " * 30 + "Wickets" + " " * 5 + "Econ\n"
                    current_message += "-" * 70 + "\n" + player_line
                else:
                    current_message += player_line
            
            # Add the last message if it's not empty
            if current_message:
                messages.append(current_message)
            
        else:
            # First message: Season header and batting stats
            out = f"🏏 Season {season} Stats 🏏\n\n"
            out += "Top 10 Run Scorers:\n"
            out += "Player Name" + " " * 30 + "Runs" + " " * 5 + "SR\n"
            out += "-" * 70 + "\n"
            count = 1
            # Sort by runs (descending) and then by strike rate (descending)
            for i in sorted(batting_data, reverse=True, key=lambda x: (x['runs'], (x['runs']*100/x['balls'] if x['balls'] > 0 else 0))):
                if count > 10:
                    break
                player_name = i['batter'].strip()
                # Handle case where balls faced is 0
                strike_rate = round(i['runs']*100/i['balls'], 2) if i['balls'] > 0 else 0
                out += f"{player_name:<40} {int(i['runs']):<10} {strike_rate:<10}\n"
                count += 1
            messages.append(out)
            
            # Second message: Bowling stats
            out = "\nTop 10 Wicket Takers:\n"
            out += "Player Name" + " " * 30 + "Wickets" + " " * 5 + "Econ\n"
            out += "-" * 70 + "\n"
            count = 1
            # Sort by wickets (descending) and then by economy rate (ascending)
            for i in sorted(bowling_data, reverse=True, key=lambda x: (x['wickets'], -1 * (x['runs']*6/((int(x['overs'])*6)+(int((x['overs'] % 1) * 10))) if x['overs'] > 0 else float('inf')))):
                if count > 10:
                    break
                player_name = i['bowler'].strip()
                # Handle case where overs is 0
                economy = round((i['runs']*6)/((int(i['overs'])*6)+(int((i['overs'] % 1) * 10))), 2) if i['overs'] > 0 else 0
                out += f"{player_name:<40} {int(i['wickets']):<10} {economy:<10}\n"
                count += 1
            messages.append(out)
            
            # Third message: Fantasy teams header
            messages.append("\nFantasy Leaderboard:")
            
            # Split fantasy teams into separate messages if needed
            current_message = ""
            for team in fantasy_data:
                team_text = f"\nTeam Name: {team['Team_Name']}\n"
                for player_name, points in team.items():
                    if player_name == 'Team_Name':
                        continue
                    team_text += f"{player_name:<20} {points}\n"
                team_text += f"Total = {sum(points for name, points in team.items() if name != 'Team_Name')}\n"
                
                # If adding this team would exceed Discord's limit, start a new message
                if len(current_message + team_text) > 1900:  # Using 1900 to be safe
                    messages.append(current_message)
                    current_message = team_text
                else:
                    current_message += team_text
            
            # Add the last fantasy teams message if it's not empty
            if current_message:
                messages.append(current_message)
            
        return messages
        
    except Exception as e:
        return [f"Error displaying archived stats: {e}"]

# Discord bot events
@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!pr"):
        # Check if user is admin
        if not is_admin(message.author):
            await message.channel.send("❌ This command is restricted to admin users only.")
            return

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

        await message.channel.send("✅ Scorecards processed successfully. Points table and player stats updated.")

    elif message.content.startswith("!stats"):
        await message.channel.send(display_player_stats())

    elif message.content.startswith("!archive"):
        try:
            # Split the command into parts
            parts = message.content[len("!archive "):].strip().split()
            if not parts:
                await message.channel.send("❌ Please specify a season number: `!archive <season_number> [batting/bowling]`")
                return
                
            season = int(parts[0])
            stat_type = parts[1].lower() if len(parts) > 1 else None
            
            # Validate stat_type if provided
            if stat_type and stat_type not in ['batting', 'bowling']:
                await message.channel.send("❌ Invalid stat type. Use 'batting' or 'bowling'")
                return
                
            messages = display_archived_stats(season, stat_type)
            # Send each message part
            for msg in messages:
                await message.channel.send(msg)
        except ValueError:
            await message.channel.send("❌ Please specify a valid season number: `!archive <season_number> [batting/bowling]`")

    elif message.content.startswith("!flb"):
        await message.channel.send(display_flb())

    elif message.content.startswith("!addteam"):
        # Check if user is admin
        if not is_admin(message.author):
            await message.channel.send("❌ This command is restricted to admin users only.")
            return

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
            title="📋 Available Commands",
            description="Here is the list of commands you can use:",
            color=discord.Color.blue()
        )
        
        # Add fields for regular commands
        embed.add_field(
            name="Regular Commands",
            value="These commands are available to all users:",
            inline=False
        )
        embed.add_field(
            name="1. `!stats <username>`",
            value="Show player statistics",
            inline=False
        )
        embed.add_field(
            name="2. `!win <username> <match_number>`",
            value="Add 1 point to a user for winning a match",
            inline=False
        )
        embed.add_field(
            name="3. `!d11`",
            value="Show Dream11 leaderboard and match winners log",
            inline=False
        )
        embed.add_field(
            name="4. `!tdy`",
            value="Show today's scheduled matches",
            inline=False
        )
        embed.add_field(
            name="5. `!about`",
            value="Show this help message",
            inline=False
        )
        
        # Add separator
        embed.add_field(
            name="\u200b",  # Zero-width space for visual separation
            value="\u200b",
            inline=False
        )
        
        # Add fields for admin commands
        embed.add_field(
            name="Admin Commands",
            value="These commands are restricted to admin users only:",
            inline=False
        )
        embed.add_field(
            name="1. `!undo`",
            value="Undo last point change",
            inline=False
        )
        embed.add_field(
            name="2. `!clearpoints`",
            value="Clear all points",
            inline=False
        )
        embed.add_field(
            name="3. `!adminlog`",
            value="Show detailed match results log",
            inline=False
        )
        embed.add_field(
            name="4. `!add <username> <points>`",
            value="Add points to a user",
            inline=False
        )
        embed.add_field(
            name="5. `!sub <username> <points>`",
            value="Subtract points from a user",
            inline=False
        )
        embed.add_field(
            name="6. `!set <username> <points>`",
            value="Set points for a user",
            inline=False
        )
        embed.add_field(
            name="7. `!reset`",
            value="Reset all points to 0",
            inline=False
        )

        # Footer with developer credit
        embed.set_footer(text="Developed by Pr😉")

        # Send the embed message
        await message.channel.send(embed=embed)

# Run the bot
client.run(os.getenv('CGT_STATS_BOT_TOKEN'))