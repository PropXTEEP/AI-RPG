import streamlit as st
import openai
import time
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. PAGE CONFIG & AUTO-REFRESH ---
st.set_page_config(page_title="AI RPG Party", page_icon="⚔️", layout="wide")

# This refreshes the app every 5 seconds so players see each other's moves
st_autorefresh(interval=5000, key="datarefresh")

# --- 2. SHARED STATE (The Multiplayer Engine) ---
@st.cache_resource
def get_shared_game_state():
    # This dictionary is shared by ALL users on the server
    return {
        "history": [
            {
                "role": "assistant", 
                "content": "The tavern door creaks open. A mist clings to the floor. Who are you, travelers, and what brings you to the Edge of the World?"
            }
        ],
        "system_prompt": "You are a dark fantasy Dungeon Master. Narrate the world, react to player actions, and occasionally demand a 'roll' for skill checks. Keep responses punchy and under 100 words."
    }

game_state = get_shared_game_state()

# --- 3. SIDEBAR: CHARACTER & CONTROLS ---
with st.sidebar:
    st.title("🛡️ Party Headquarters")
    
    api_key = st.text_input("OpenAI API Key", type="password")
    
    st.divider()
    
    if "player_name" not in st.session_state:
        st.session_state.player_name = "New Traveler"
    
    st.session_state.player_name = st.text_input("Character Name", value=st.session_state.player_name)
    char_class = st.selectbox("Class", ["Warrior", "Mage", "Rogue", "Paladin", "Bard"])
    
    st.divider()
    
    # RESET BUTTON: Clears the shared history for everyone
    if st.button("🔥 Reset Adventure for All"):
        game_state["history"] = [
            {"role": "assistant", "content": "The world has been unmade and reborn. A new journey begins..."}
        ]
        st.rerun()
    
    st.caption(f"Syncing with Party... {datetime.now().strftime('%H:%M:%S')}")

# --- 4. THE GAME INTERFACE ---
st.title("⚔️ AI Dungeon Master: Multi-Player")

# Display Chat History
for msg in game_state["history"]:
    if msg["role"] == "assistant":
        with st.chat_message("assistant", avatar="🧙‍♂️"):
            st.write(msg["content"])
    else:
        # Extract player name from the stored message
        p_name = msg.get("name", "Unknown")
        # Use a different avatar if it's the current player vs someone else
        is_me = p_name == st.session_state.player_name
        with st.chat_message("user", avatar="🛡️" if is_me else "👤"):
            st.write(f"**{p_name}**: {msg['content']}")

# --- 5. PLAYER ACTION LOGIC ---
user_input = st.chat_input("What is your move?")

if user_input:
    if not api_key:
        st.error("Please enter an OpenAI API Key in the sidebar to act!")
    else:
        # A. Add Player's move to shared history
        player_msg = {
            "role": "user", 
            "name": st.session_state.player_name, 
            "content": f"({char_class}) {user_input}"
        }
        game_state["history"].append(player_msg)
        
        # B. Call the AI DM
        client = openai.OpenAI(api_key=api_key)
        
        # Build the context for the AI (System Prompt + History)
        messages_for_ai = [{"role": "system", "content": game_state["system_prompt"]}]
        # Add the last 15 messages for context (to prevent token overflow)
        for m in game_state["history"][-15:]:
            messages_for_ai.append({"role": m["role"], "content": m["content"]})
        
        try:
            with st.spinner("The DM is thinking..."):
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages_for_ai
                )
            
            dm_reply = response.choices[0].message.content
            
            # C. Add DM's reply to shared history
            game_state["history"].append({"role": "assistant", "content": dm_reply})
            
            # Refresh for everyone
            st.rerun()
            
        except Exception as e:
            st.error(f"The DM had a stroke: {e}")

# --- 6. FOOTER INFO ---
st.divider()
st.caption("Shared session active. Tell your friends to join using this URL.")
