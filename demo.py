import discord
import pytesseract
from PIL import Image, ImageOps
import json
from tabulate import tabulate
import re
from concurrent.futures import ThreadPoolExecutor
import asyncio
import numpy as np
import pickle
from os import path
from datetime import datetime
from dataclasses import dataclass
from typing import List


@dataclass
class FantasyPlayer:
    name: str
    role: str  # "Batsman", "Bowler", "All-rounder", "Wicket-keeper"
    team: str
    price: int
    points: float = 0

@dataclass
class FantasyTeam:
    owner_id: str
    owner_name: str
    name: str
    players: List[str]
    total_points: float = 0
    last_updated: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Set up Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'  

# Initialize client
intents = discord.Intents.default()
intents.message_content = True  # To read message content and attachments
client = discord.Client(intents=intents)

# File paths for points table and player stats
POINTS_TABLE_FILE = "points_table.json"
PLAYER_STATS_FILE = "player_stats.json"
fantasy_teams = {}
FANTASY_FILE = "fantasy_data.json"

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

# Helper function to process a scorecard with layout analysis and OCR
def prev_process_scorecard(image_path):
    try:
        # Open image and apply preprocessing
        image = Image.open(image_path)
        grayscale_image = ImageOps.grayscale(image)  # Convert to grayscale for OCR
        threshold_image = grayscale_image.point(lambda p: p > 150 and 255)  # Simple binarization

        # Perform OCR to extract raw text
        text = pytesseract.image_to_string(threshold_image)

        # Print the raw text for debugging
        print("Raw OCR text:\n", text)

        # Clean up and split the text into lines
        lines = text.strip().split("\n")
        parsed_data = []
        wickets = []

        # Regex pattern to find valid cricket scorecard entries (runs)
        score_pattern = re.compile(r'([A-Za-z\s]+)\s+.*\s+(\d+)$')
        wicket_pattern = re.compile(r'([A-Za-z\s]+)\s+c\s+([A-Za-z\s]+)\s+b\s+([A-Za-z\s]+)')

        for line in lines:
            # Skip non-relevant lines like team names, run rates, and extras
            if "EXTRAS" in line or "RUN-RATE" in line or line.isdigit() or not line.strip():
                continue

            # Try to match for a valid player run score (name and runs)
            match = score_pattern.search(line)
            if match:
                player_name = match.group(1).strip()  # Player name
                runs = int(match.group(2))  # Runs (last number in the line)
                parsed_data.append((player_name, runs))
            
            # Try to match for wicket details
            wicket_match = wicket_pattern.search(line)
            if wicket_match:
                batsman = wicket_match.group(1).strip()  # Batsman's name
                fielder = wicket_match.group(2).strip()  # Fielder's name
                bowler = wicket_match.group(3).strip()  # Bowler's name
                wickets.append((batsman, fielder, bowler))
            
            else:
                print(f"Skipping invalid line: {line}")

        return parsed_data, wickets
    except Exception as e:
        print(f"Error processing scorecard: {e}")
        return [], []


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

        curr_data['fpl']=0
        
    return curr_data

def update_batter_stats(prev, curr):
    for i in ('runs','balls'):
        prev[i] += curr[i]
    return prev

def update_bowler_stats(prev, curr):
    for i in ('overs','maidens','runs','wickets'):
        prev[i] += curr[i]
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
    
    return curr_data

# Helper function to process a scorecard with layout analysis and OCR
def process_scorecard(image_path, is_batting):



    
    stats_file_path = "b_stats.pkl" if is_batting else "f_stats.pkl"
    player_key = 'batter' if is_batting else 'bowler'
    try:
        text = get_normalized_ocr_read(image_path)

        lines = text.strip().split("\n")

        data = []

        if path.isfile(stats_file_path):
            with open(stats_file_path, 'rb') as f:
                data = pickle.load(f)
        
        for line in lines:
            val=(get_batter_from_str if is_batting else get_bowler_from_str)(line)
            if not val:
                continue
            
            for i in range(len(data)):
                if data[i][player_key] != val[player_key]:
                    continue
                data[i] = (update_batter_stats if is_batting else update_bowler_stats)(data[i], val)
                break            
            else:
                data.append(val)
        
        print(data)

        with open(stats_file_path,'wb') as f:
            pickle.dump(data,f)

        return data
    except Exception as e:
        print(f"Error processing scorecard: {e}")
        return [], []

def update_fantasy_points(scorecard_data, is_batting=True):
        for data in scorecard_data:
            player_name = data['batter' if is_batting else 'bowler'].strip()
            points = 0
            
            if is_batting:
                runs = float(data.get('runs', 0))
                points += runs  # 1 point per run
                if runs >= 100:
                    points += 50  # Century bonus
                elif runs >= 50:
                    points += 20  # Fifty bonus
                if runs == 0:
                    points -= 10  # Duck penalty
            else:
                wickets = float(data.get('wickets', 0))
                points += wickets * 25  # 25 points per wicket
                if wickets >= 5:
                    points += 50  # 5-wicket haul bonus
                elif wickets >= 3:
                    points += 30  # 3-wicket haul bonus
                
                maidens = float(data.get('maidens', 0))
                points += maidens * 15  # 15 points per maiden
            
            # Update points for all teams containing this player
            for team in fantasy_teams.values():
                if player_name in team['players']:
                    team['total_points'] += points
                    team['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        save_fantasy_data()


# Helper function to update stats and points table
def update_stats_and_points(team, scorecard, total_score):
    if team not in points_table:
        points_table[team] = {"Matches": 0, "Wins": 0, "Losses": 0, "Points": 0, "Net Run Rate": 0}

    points_table[team]["Matches"] += 1

    for player_name, runs, balls in scorecard:
        if player_name not in player_stats:
            player_stats[player_name] = {"Runs": 0, "Balls": 0, "Wickets": 0}

        player_stats[player_name]["Runs"] += runs
        player_stats[player_name]["Balls"] += balls

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
    
    count = 1
    out = "Most Runs:\n"
    for i in sorted(batting_data,reverse=True,key=lambda x:x['runs']):
        try:
            if count>10:
                break
            out+=f"{i['batter']} {int(i['runs'])} {round(i['runs']*100/i['balls'],2)} {i['fpl']}\n"
            count+=1
        except:
            count+=1
            break

    count = 1
    out += "\nMost Wickets:\n"
    for i in sorted(bowling_data,reverse=True,key=lambda x:x['wickets']):
        if count>10:
            break
        out+=f"{i['bowler']} {int(i['wickets'])} {round((i['runs']*6)/((int(i['overs'])*6)+(int((i['overs'] % 1) * 10))),2)}\n"
        count+=1
    
    return out
        
# Helper function to display the points table
def display_points_table():
    headers = ["Team", "Matches", "Wins", "Losses", "Points", "Net Run Rate"]
    rows = [
        [team, stats["Matches"], stats["Wins"], stats["Losses"], stats["Points"], stats["Net Run Rate"]]
        for team, stats in points_table.items()
    ]
    return f"```\n{tabulate(rows, headers=headers, tablefmt='grid')}\n```"

# Save updated data to files
def save_data():
    with open(POINTS_TABLE_FILE, "w") as f:
        json.dump(points_table, f, indent=4)
    with open(PLAYER_STATS_FILE, "w") as f:
        json.dump(player_stats, f, indent=4)

# Helper function to add player manually to the database
def add_player_to_db(player_name):
    if player_name not in player_stats:
        player_stats[player_name] = {"Runs": 0, "Balls": 0, "Wickets": 0}
    return f"✅ Player **{player_name}** has been successfully added to the database with initial stats set to **0**."


def load_fantasy_data():
    try:
        with open(FANTASY_FILE, 'r') as f:
            data = json.load(f)
            return data.get('teams', {})
    except FileNotFoundError:
        return {}

def save_fantasy_data():
    data = {'teams': fantasy_teams}
    with open(FANTASY_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Discord bot events
@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!create_team"):
        args = message.content.split(" ", 1)
        if len(args) < 2:
            await message.channel.send("❌ Please provide a team name!")
            return
        
        owner_id = str(message.author.id)
        if owner_id in fantasy_teams:
            await message.channel.send("❌ You already have a team!")
            return
            
        fantasy_teams[owner_id] = FantasyTeam(
            owner_id=owner_id,
            owner_name=message.author.name,
            name=args[1],
            players=[]
        ).__dict__
        save_fantasy_data()
        await message.channel.send(f"✅ Team '{args[1]}' created!")

    elif message.content.startswith("!add_player"):
        args = message.content.split(" ", 1)
        if len(args) < 2:
            await message.channel.send("❌ Please specify a player name!")
            return
            
        owner_id = str(message.author.id)
        if owner_id not in fantasy_teams:
            await message.channel.send("❌ Create a team first with !create_team")
            return
            
        team = fantasy_teams[owner_id]
        if len(team['players']) >= 11:
            await message.channel.send("❌ Team already has 11 players!")
            return
            
        player_name = args[1].strip()
        if player_name in team['players']:
            await message.channel.send("❌ Player already in team!")
            return
            
        team['players'].append(player_name)
        save_fantasy_data()
        await message.channel.send(f"✅ Added {player_name} to your team!")

    elif message.content == "!team":
        owner_id = str(message.author.id)
        if owner_id not in fantasy_teams:
            await message.channel.send("❌ You don't have a team!")
            return
            
        team = fantasy_teams[owner_id]
        response = f"**{team['name']}** (Owner: {team['owner_name']})\n"
        response += f"Points: {team['total_points']}\n\nPlayers:\n"
        for player in team['players']:
            response += f"• {player}\n"
        await message.channel.send(response)

    elif message.content == "!fantasy_standings":
        if not fantasy_teams:
            await message.channel.send("No teams registered yet!")
            return
            
        sorted_teams = sorted(fantasy_teams.values(), 
                            key=lambda x: x['total_points'], 
                            reverse=True)
        response = "**Fantasy League Standings**\n\n"
        for i, team in enumerate(sorted_teams, 1):
            response += f"{i}. {team['name']} - {team['total_points']} points\n"
        await message.channel.send(response)





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

        save_data()
        await message.channel.send("✅ Scorecards processed successfully. Points table and player stats updated.")


    elif message.content.startswith("!stats"):
        await message.channel.send(display_player_stats())

    elif message.content.startswith("!about"):
        about_text = """
**Fantasy Cricket Bot Commands:**

1. Team Management:
   - Create your team: `!create_team <team_name>`
   Example: `!create_team Super Kings`
   
   - Add player to team: `!add_player <player_name>`
   Example: `!add_player Virat Kohli`
   
   - View your team: `!team`
   
   - View fantasy standings: `!fantasy_standings`

2. Match Processing:
   - Process batting scorecard: `!prb [attach batting scorecard image]`
   - Process bowling scorecard: `!prf [attach bowling scorecard image]`

3. Statistics:
   - View tournament stats: `!stats`
   - View this help menu: `!about`

**Points System:**
Batting:
- 1 point per run
- 50 points for century
- 20 points for fifty
- -10 points for duck

Bowling:
- 25 points per wicket
- 15 points per maiden over
- 50 points for 5-wicket haul
- 30 points for 3-wicket haul

**Note:** 
- You can only create one team per user
- Maximum 11 players allowed per team
- Points are automatically updated after each match

**Developed by PR ;)**
"""
        await message.channel.send(about_text)

client.run("MTMyNjE5MDEyNDg1MzM2Njc4NA.Geyvif.NxvS2-qZbSSfdMJyhK5-IMLF3Ci5YuUrWTjX-8")