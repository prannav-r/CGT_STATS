import pickle

def merge_duplicate_players():
    # Load the batting stats file
    try:
        with open('b_statsS2.pkl', 'rb') as f:
            batting_data = pickle.load(f)
    except FileNotFoundError:
        print("Error: b_statsS2.pkl not found")
        return

    # Dictionary to store merged stats
    merged_stats = {}
    
    # Dictionary mapping duplicate names to original names
    name_mapping = {
        'NIKLAS SAUNDERS Ibw RAZZAK': 'NIKLAS SAUNDERS',
        'SIMON SCOTT Ibw RUSSELL': 'SIMON SCOTT',
        'HEINRICH KLAASEN Ibw PANDYA': 'HEINRICH KLAASEN',
        # Add more mappings here if needed
    }

    # Process each player's stats
    for player in batting_data:
        player_name = player['batter'].strip()
        
        # Check if this is a duplicate name
        original_name = name_mapping.get(player_name, player_name)
        
        if original_name in merged_stats:
            # Merge stats with existing player
            existing = merged_stats[original_name]
            existing['runs'] += player['runs']
            existing['balls'] += player['balls']
            # Keep the original name
            existing['batter'] = original_name
        else:
            # Create new entry
            merged_stats[original_name] = {
                'batter': original_name,
                'runs': player['runs'],
                'balls': player['balls']
            }

    # Convert back to list format
    merged_data = list(merged_stats.values())

    # Save the merged stats back to file
    with open('b_statsS2.pkl', 'wb') as f:
        pickle.dump(merged_data, f)

    print(f"Successfully merged {len(batting_data) - len(merged_data)} duplicate entries")
    print(f"Original entries: {len(batting_data)}")
    print(f"Merged entries: {len(merged_data)}")

if __name__ == "__main__":
    merge_duplicate_players() 