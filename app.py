import streamlit as st
import requests
import pandas as pd

# --- CONFIG & LEAGUE ID ---
LEAGUE_ID = "1389391092092239872"

st.set_page_config(page_title="League News & History", layout="wide")

@st.cache_data(ttl=3600)
def fetch_data(url):
    return requests.get(url).json()

def get_league_chain(current_id):
    chain = []
    temp_id = current_id
    while temp_id and temp_id != "0":
        data = fetch_data(f"https://api.sleeper.app/v1/league/{temp_id}")
        if not data: break
        chain.append({
            "id": temp_id,
            "season": data['season'],
            "name": data['name'],
            "previous_id": data.get('previous_league_id')
        })
        temp_id = data.get('previous_league_id')
    return chain

def get_league_metadata(league_id):
    users = fetch_data(f"https://api.sleeper.app/v1/league/{league_id}/users")
    rosters = fetch_data(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    
    # Map roster_id to display name
    user_map = {u['user_id']: u.get('display_name', 'Unknown') for u in users}
    roster_to_name = {r['roster_id']: user_map.get(r['owner_id'], 'Unknown') for r in rosters}
    return roster_to_name

@st.cache_data
def get_historical_h2h(chain):
    all_matchups = []
    for year in chain:
        # Check weeks 1-17 (standard)
        for week in range(1, 18):
            data = fetch_data(f"https://api.sleeper.app/v1/league/{year['id']}/matchups/{week}")
            if not data: continue
            
            # Map roster to names for that specific year
            names = get_league_metadata(year['id'])
            
            match_groups = {}
            for team in data:
                m_id = team['matchup_id']
                if m_id not in match_groups: match_groups[m_id] = []
                match_groups[m_id].append({
                    "name": names.get(team['roster_id'], "Unknown"),
                    "points": team['points'],
                    "season": year['season'],
                    "week": week
                })
            
            for m_id, teams in match_groups.items():
                if len(teams) == 2:
                    all_matchups.append(teams)
    return all_matchups

# --- APP UI ---
st.title("🏈 League Newsletter & History")
st.sidebar.info(f"Connected to League: {LEAGUE_ID}")

with st.spinner("Analyzing league history (this may take a minute the first time)..."):
    chain = get_league_chain(LEAGUE_ID)
    current_season = chain[0]['id']
    history = get_historical_h2h(chain)

# Get current week matchups
current_week = 1 # Update this or fetch from league settings
names = get_league_metadata(current_season)
this_week_data = fetch_data(f"https://api.sleeper.app/v1/league/{current_season}/matchups/{current_week}")

col1, col2 = st.columns(2)

with col1:
    st.header(f"📅 Week {current_week} Matchups")
    match_dict = {}
    for t in this_week_data:
        mid = t['matchup_id']
        if mid not in match_dict: match_dict[mid] = []
        match_dict[mid].append(t)

    for mid, teams in match_dict.items():
        if len(teams) == 2:
            t1_name = names.get(teams[0]['roster_id'])
            t2_name = names.get(teams[1]['roster_id'])
            
            with st.expander(f"{t1_name} vs {t2_name}"):
                # Calculate Historical H2H
                h2h_wins = [0, 0] # [t1 wins, t2 wins]
                for past_match in history:
                    p_names = [m['name'] for m in past_match]
                    if t1_name in p_names and t2_name in p_names:
                        # Determine winner of that past match
                        idx1 = 0 if past_match[0]['name'] == t1_name else 1
                        idx2 = 1 - idx1
                        if past_match[idx1]['points'] > past_match[idx2]['points']:
                            h2h_wins[0] += 1
                        else:
                            h2h_wins[1] += 1
                
                st.write(f"**All-Time Series:** {t1_name} {h2h_wins[0]} - {h2h_wins[1]} {t2_name}")
                if sum(h2h_wins) > 0:
                    st.progress(h2h_wins[0] / sum(h2h_wins))
                else:
                    st.write("First time meeting!")

with col2:
    st.header("🗞️ Weekly Newsletter")
    st.subheader("Look Ahead")
    st.write("Generate trash talk or context based on the H2H stats on the left.")
    
    st.subheader("Historical Records")
    df_history = []
    for m in history:
        df_history.append({"Manager": m[0]['name'], "Points": m[0]['points'], "Season": m[0]['season']})
        df_history.append({"Manager": m[1]['name'], "Points": m[1]['points'], "Season": m[1]['season']})
    
    if df_history:
        df = pd.DataFrame(df_history)
        high_score = df.sort_values(by="Points", ascending=False).iloc[0]
        st.metric("All-Time High Score", f"{high_score['Points']} pts", f"by {high_score['Manager']} ({high_score['Season']})")
