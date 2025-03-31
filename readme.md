# **CGT_STATS Discord Bot**

The CGT_STATS bot is designed for cricket enthusiasts who want to keep track of fantasy points, process scorecards, create teams, and view leaderboards—all within Discord! This bot simplifies cricket management and provides fun interactions with detailed statistics.

---

## **Features**

1.  **Process Scorecards**:

    - Upload batting or bowling scorecards, and the bot will process them to calculate fantasy points.

2.  **Create Teams**:

    - Easily create and save a fantasy cricket team of exactly 11 players.

3.  **View Leaderboards**:

    - Check fantasy team standings and individual performance stats.

4.  **User-Friendly Commands**:

    - Simple and intuitive commands for interacting with the bot.

---

## **Commands**

Here’s a detailed list of available commands:

### **1\. `!pr` - Process Cricket Match Scorecards**

- Process batting or bowling scorecards to calculate performance.
- **Usage**:
  - **Batting Scorecard**: `!prb [attach batting scorecard file]`
  - **Bowling Scorecard**: `!prf [attach bowling scorecard file]`

---

### **2\. `!stats` - View Leaderboard**

- Displays the leaderboard with player or team statistics.
- **Usage**: `!stats`

---

### **3\. `!addteam` - Create a Fantasy Team**

- Allows users to create and save a team of 11 players.
- **Usage**:

  `!addteam <player1>,<player2>,<player3>,...,<player11>`

- **Details**:
  - Provide a list of exactly 11 player names, separated by commas.
  - Ensure there’s a space after each comma for better formatting.
- **Example**:

  `!addteam Virat Kohli,Rohit Sharma,Steve Smith,AB de Villiers,MS Dhoni,Andre Russell,Pat Cummins,Jasprit Bumrah,Trent Boult,Imran Tahir,Ben Stokes`

---

### **4\. `!flb` - Fantasy Leaderboard**

- Displays the fantasy team leaderboard for all users.
- **Usage**: `!flb`

---

### **5\. `!about` - View Bot Information**

- Shows a list of available commands and general information about the bot.
- **Usage**: `!about`

---

## **Setup Instructions**

Follow these steps to set up the bot on your server:

### **1\. Prerequisites**

- A Discord server where the bot will be added.
- Python 3.8 or higher installed on your system.

### **2\. Installation**

1.  Clone the bot repository:

    `git clone https://github.com/yourusername/CGT_STATS.git`

2.  Navigate to the project directory:

    `cd CGT_STATS`

3.  Install required dependencies:

    `pip install -r requirements.txt`

### **3\. Add the Bot to Discord**

1.  Go to the Discord Developer Portal.
2.  Create a new application and generate a bot token.
3.  Invite the bot to your server using the OAuth2 URL.

### **4\. Run the Bot**

Start the bot with:

`python bot.py`

---

## **File Structure**

- **bot.py**: Main script for running the bot.
- **commands.py**: Contains the logic for all bot commands.
- **requirements.txt**: Lists all Python dependencies.
- **README.md**: This documentation file.

---

## **Fantasy Point Rules**

### Batters:

- **Runs Scored**: +1 point per run.
- **Strike Rate Bonus**:
  - 50-75 SR: -2 points
  - 75-100 SR: +0 points
  - 100-125 SR: +5 points
  - 125+ SR: +10 points
- **Milestone Bonus**:
  - 50 runs: +10 points
  - 100 runs: +25 points

### Bowlers:

- **Wickets Taken**: +25 points per wicket.
- **Economy Rate Bonus** (min 2 overs):
  - <5.0: +15 points
  - 5.0-6.5: +10 points
  - 6.5-8.0: +5 points
  - 8.0-10.0: 0 points
  - > 10.0: -5 points
- **5-Wicket Haul**: +25 points.
- **Maiden Overs**: +10 points each.

---

## **Contributing**

We welcome contributions! To contribute:

1.  Fork the repository.
2.  Create a new branch:

    `git checkout -b feature-name`

3.  Make changes and commit:

    `git commit -m "Added new feature"`

4.  Push to your fork and create a pull request.

---

## **Support**

If you encounter any issues, please open an issue on GitHub or contact the developer.

---

## **Developed By**

PR 😉

Enjoy the CGT_STATS bot! 🏏

![Export to Google Doc](chrome-extension://iapioliapockkkikccgbiaalfhoieano/assets/create.svg)![Copy with formatting](chrome-extension://iapioliapockkkikccgbiaalfhoieano/assets/copy.svg)![Select for Multi-select](chrome-extension://iapioliapockkkikccgbiaalfhoieano/assets/multi-select.svg)
