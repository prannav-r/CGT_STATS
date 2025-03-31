import discord
import pickle
from datetime import datetime
import csv
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize client
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Add this if you need member-related functionality
client = discord.Client(intents=intents)

# File paths for points table and player stats
DREAM11_POINTS_FILE = "dream11_points.pkl"
MATCH_RESULTS_FILE = "match_results.pkl"

# Admin user ID (replace with your Discord user ID)
ADMIN_USER_ID = 796665468664021012  # Replace this with your actual Discord user ID

# Load or initialize Dream11 points
try:
    with open(DREAM11_POINTS_FILE, 'rb') as f:
        dream11_points = pickle.load(f)
except FileNotFoundError:
    dream11_points = {}

# Load or initialize Dream11 history
try:
    with open('dream11_history.pkl', 'rb') as f:
        dream11_history = pickle.load(f)
except FileNotFoundError:
    dream11_history = []

# Load or initialize match results
try:
    with open(MATCH_RESULTS_FILE, 'rb') as f:
        match_results = pickle.load(f)
except FileNotFoundError:
    match_results = []

# Load IPL 2025 Schedule
def load_schedule():
    schedule = {}
    with open('IPL_2025_SEASON_SCHEDULE.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_no = int(row['Match No'])
            schedule[match_no] = {
                'date': datetime.strptime(row['Date'], '%Y-%m-%d'),
                'day': row['Day'],
                'start': row['Start'],
                'home': row['Home'],
                'away': row['Away'],
                'venue': row['Venue']
            }
    return schedule

# Load schedule at startup
IPL_2025_SCHEDULE = load_schedule()

# Team name to acronym mapping
TEAM_ACRONYMS = {
    "Kolkata Knight Riders": "KKR",
    "Royal Challengers Bengaluru": "RCB",
    "Sunrisers Hyderabad": "SRH",
    "Rajasthan Royals": "RR",
    "Chennai Super Kings": "CSK",
    "Mumbai Indians": "MI",
    "Delhi Capitals": "DC",
    "Lucknow Super Giants": "LSG",
    "Gujarat Titans": "GT",
    "Punjab Kings": "PBKS"
}

def is_admin(user):
    """Check if the user is an admin"""
    return user.id == ADMIN_USER_ID

def update_dream11_points(user, points_change, match_number=None, recorded_by=None):
    """Update Dream11 points for a user"""
    global dream11_points, dream11_history, match_results
    
    # Initialize user points if not exists
    if user not in dream11_points:
        dream11_points[user] = 0
    
    # Update points
    dream11_points[user] += points_change
    
    # Record history
    history_entry = {
        'user': user,
        'points_change': points_change,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # If this is a match win, add match number and recorder
    if match_number is not None:
        history_entry['match_number'] = match_number
        # Add to match results with recorder information
        match_results.append({
            'match_number': match_number,
            'winner': user,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'recorded_by': recorded_by if recorded_by else 'Unknown'
        })
    
    dream11_history.append(history_entry)
    
    # Save updated data
    with open(DREAM11_POINTS_FILE, 'wb') as f:
        pickle.dump(dream11_points, f)
    with open('dream11_history.pkl', 'wb') as f:
        pickle.dump(dream11_history, f)
    with open(MATCH_RESULTS_FILE, 'wb') as f:
        pickle.dump(match_results, f)

def clear_all_points():
    """Clear all Dream11 points and match results"""
    global dream11_points, dream11_history, match_results
    
    try:
        # Reset all data
        dream11_points = {}
        dream11_history = []
        match_results = []
        
        # Save empty data to files
        with open(DREAM11_POINTS_FILE, 'wb') as f:
            pickle.dump(dream11_points, f)
        with open('dream11_history.pkl', 'wb') as f:
            pickle.dump(dream11_history, f)
        with open(MATCH_RESULTS_FILE, 'wb') as f:
            pickle.dump(match_results, f)
        
        return "✅ All Dream11 points, history, and match results have been cleared successfully."
    except Exception as e:
        return f"❌ Error clearing points: {str(e)}"

def display_dream11_leaderboard():
    """Display Dream11 leaderboard and match winners log"""
    if not dream11_points:
        return "No points recorded yet!"
    
    # Sort users by points
    sorted_users = sorted(dream11_points.items(), key=lambda x: x[1], reverse=True)
    
    # Create leaderboard message
    leaderboard = "🏆 Dream11 Leaderboard 🏆\n\n"
    for rank, (user, points) in enumerate(sorted_users, 1):
        leaderboard += f"{rank}. {user}: {points} point(s)\n"
    
    # Add match winners log
    if match_results:
        leaderboard += "\n\n🏆 Dream11 Contest Match Winners Log 🏆\n\n"
        leaderboard += "Match #" + " " * 5 + "Match Details" + " " * 20 + "Winner\n"
        leaderboard += "-" * 70 + "\n"
        
        # Sort results by match number
        sorted_results = sorted(match_results, key=lambda x: x['match_number'])
        
        for result in sorted_results:
            match_no = result['match_number']
            schedule_info = IPL_2025_SCHEDULE.get(match_no, {})
            
            # Format match details with acronyms
            if schedule_info:
                home_team = schedule_info['home'].strip()
                away_team = schedule_info['away'].strip()
                # Get acronyms from the mapping
                home_acronym = TEAM_ACRONYMS.get(home_team, home_team)
                away_acronym = TEAM_ACRONYMS.get(away_team, away_team)
                match_details = f"{home_acronym} vs {away_acronym}"
            else:
                match_details = "Unknown Match"
            
            # Format the log line
            leaderboard += f"Match {match_no:<5} {match_details:<30} {result.get('winner', 'TBD'):<15}\n"
    
    return leaderboard

def undo_last_dream11_point():
    """Undo the last Dream11 point change"""
    global dream11_points, dream11_history, match_results
    
    if not dream11_history:
        return False, "No points to undo"
    
    # Get last change
    last_change = dream11_history.pop()
    user = last_change['user']
    points_change = last_change['points_change']
    
    # Revert points
    dream11_points[user] -= points_change
    
    # If this was a match win, remove it from match_results
    if 'match_number' in last_change:
        # Find and remove the matching entry from match_results
        match_results = [r for r in match_results if not (
            r['match_number'] == last_change['match_number'] and 
            r['winner'] == user and 
            r['timestamp'] == last_change['timestamp']
        )]
    
    # Save updated data
    with open(DREAM11_POINTS_FILE, 'wb') as f:
        pickle.dump(dream11_points, f)
    with open('dream11_history.pkl', 'wb') as f:
        pickle.dump(dream11_history, f)
    with open(MATCH_RESULTS_FILE, 'wb') as f:
        pickle.dump(match_results, f)
    
    return True, f"Undid {points_change} point(s) for {user}"

# Discord bot events
@client.event
async def on_ready():
    print(f"Dream11 Bot has logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!win"):
        try:
            # Extract username and match number from command
            parts = message.content[len("!win "):].strip().split()
            if len(parts) < 2:
                await message.channel.send("❌ Please specify both username and match number: `!win <username> <match_number>`")
                return
                
            username = parts[0]
            try:
                match_number = int(parts[1])
            except ValueError:
                await message.channel.send("❌ Please provide a valid match number.")
                return
            
            # Check if match has already been recorded
            for result in match_results:
                if result['match_number'] == match_number:
                    await message.channel.send(f"❌ Match {match_number} has already been recorded. Winner: {result['winner']}")
                    return
            
            # Get current date
            current_date = datetime.now().date()
            
            # Check if user is admin
            if not is_admin(message.author):
                # For regular users, check if match is scheduled for today
                match_schedule = IPL_2025_SCHEDULE.get(match_number)
                if not match_schedule or match_schedule['date'].date() != current_date:
                    await message.channel.send("❌ You can only record points for matches scheduled for today. Admins can record points for any match.")
                    return
            
            # Update points
            update_dream11_points(username, 1, match_number, message.author.name)
            await message.channel.send(f"✅ Added 1 point to {username} for winning Match {match_number}")
            
        except Exception as e:
            await message.channel.send(f"❌ Error updating points: {str(e)}")

    elif message.content.startswith("!d11"):
        leaderboard = display_dream11_leaderboard()
        await message.channel.send(leaderboard)

    elif message.content.startswith("!undo"):
        # Check if user is admin
        if not is_admin(message.author):
            await message.channel.send("❌ This command is restricted to admin users only.")
            return
            
        success, message_text = undo_last_dream11_point()
        if success:
            await message.channel.send(f"✅ {message_text}")
        else:
            await message.channel.send(f"❌ {message_text}")

    elif message.content.startswith("!clearpoints"):
        # Check if user is admin
        if not is_admin(message.author):
            await message.channel.send("❌ This command is restricted to admin users only.")
            return
        await message.channel.send(clear_all_points())

    elif message.content.startswith("!adminlog"):
        # Check if user is admin
        if not is_admin(message.author):
            await message.channel.send("❌ This command is restricted to admin users only.")
            return
            
        try:
            with open(MATCH_RESULTS_FILE, 'rb') as f:
                results = pickle.load(f)
                if not results:
                    await message.channel.send("No match results recorded yet!")
                else:
                    output = "Match Results File Contents:\n\n"
                    for result in results:
                        output += f"Match: {result['match_number']}\n"
                        output += f"Winner: {result['winner']}\n"
                        output += f"Recorded By: {result.get('recorded_by', 'Unknown')}\n"
                        output += f"Timestamp: {result['timestamp']}\n"
                        output += "-" * 30 + "\n"
                    await message.channel.send(output)
        except Exception as e:
            await message.channel.send(f"Error reading match results: {str(e)}")

    elif message.content.startswith("!tdy"):
        # Get current date
        current_date = datetime.now().date()
        
        # Find matches scheduled for today
        today_matches = []
        for match_no, match_info in IPL_2025_SCHEDULE.items():
            if match_info['date'].date() == current_date:
                # Get team acronyms
                home_team = match_info['home'].strip()
                away_team = match_info['away'].strip()
                home_acronym = TEAM_ACRONYMS.get(home_team, home_team)
                away_acronym = TEAM_ACRONYMS.get(away_team, away_team)
                
                today_matches.append({
                    'match_no': match_no,
                    'home': home_acronym,
                    'away': away_acronym,
                    'start': match_info['start']
                })
        
        if not today_matches:
            await message.channel.send("No matches scheduled for today.")
            return
            
        # Create output message
        output = "🏏 Today's Matches 🏏\n\n"
        output += "Match #" + " " * 5 + "Teams" + " " * 20 + "Start Time\n"
        output += "-" * 50 + "\n"
        
        # Sort matches by match number
        today_matches.sort(key=lambda x: x['match_no'])
        
        for match in today_matches:
            output += f"Match {match['match_no']:<5} {match['home']} vs {match['away']:<15} {match['start']}\n"
        
        await message.channel.send(output)

    elif message.content.startswith("!about"):
        # Create an embed message
        embed = discord.Embed(
            title="📋 Dream11 Bot Commands",
            description="Here is the list of Dream11 commands you can use:",
            color=discord.Color.blue()
        )
        
        # Add fields for regular commands
        embed.add_field(
            name="Regular Commands",
            value="These commands are available to all users:",
            inline=False
        )
        embed.add_field(
            name="1. `!win <username> <match_number>`",
            value="Add 1 point to a user for winning a match",
            inline=False
        )
        embed.add_field(
            name="2. `!d11`",
            value="Show Dream11 leaderboard and match winners log",
            inline=False
        )
        embed.add_field(
            name="3. `!tdy`",
            value="Show today's scheduled matches",
            inline=False
        )
        embed.add_field(
            name="4. `!about`",
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

        # Footer with developer credit
        embed.set_footer(text="Developed by Pr😉")

        # Send the embed message
        await message.channel.send(embed=embed)

# Run the bot
client.run(os.getenv('DREAM11_BOT_TOKEN')) 