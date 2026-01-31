import streamlit as st
from groq import Groq
import time
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# 1. PAGE CONFIG
st.set_page_config(page_title="Free AI RPG", page_icon="⚔️", layout="wide")

# Syncs the party every 5 seconds
st_autorefresh(interval=5000, key="rpg_sync")

# 2. SHARED MULTIPLAYER STATE
@st.cache_resource
def get_shared_game_state():
    return {
        "history": [{"role": "assistant", "content": "The tavern is quiet until the door bangs open. Welcome, travelers. What is your first move?"}],
        "system_prompt": "You are a witty, dark fantasy Dungeon Master. React to player actions and dice rolls. Keep it under 80 words."
    }

game_state = get_shared_game_state()

# 3. SIDEBAR: PLAYER & TOOLS
with st.sidebar:
    st.title("🛡️ Party Menu")
    
    # GROQ API KEY
    groq_api_key = st.text_input("Groq API Key (Free)", type="password")
    
    st.divider()
    
    if "player_name" not in st.session_state:
        st.session_state.player_name = "Traveler"
    
    st.session_state.player_name = st.text_input("Character Name", value=st.session_state.player_name)
    char_class = st.selectbox("Class", ["Warrior", "Mage", "Rogue", "Paladin", "Bard"])

    st.divider()
    
    st.subheader("🎲 Action Roll")
    if st.button("Roll D20"):
        roll = random.randint(1, 20)
        game_state["history"].append({
            "role": "user", 
            "name": "SYSTEM", 
            "content": f"🎲 {st.session_state.player_name} rolled a {roll}!"
        })
        st.rerun()

    st.divider()
    
    if st.button("🔥 Reset Adventure"):
        game_state["history"] = [{"role": "assistant", "content": "The world resets. A new story begins..."}]
        st.rerun()

# 4. THE GAME INTERFACE
st.title("⚔️ Multi-Player AI Dungeon")

# Display Messages
for msg in game_state["history"]:
    role = msg["role"]
    avatar = "🧙‍♂️" if role == "assistant" else "👤"
    
    with st.chat_message(role, avatar=avatar):
        if "name" in msg:
            st.write(f"**{msg['name']}**: {msg['content']}")
        else:
            st.write(msg["content"])

# 5. INPUT LOGIC
user_input = st.chat_input("What do you do?")

if user_input:
    if not groq_api_key:
        st.error("Please enter your free Groq API Key in the sidebar!")
    else:
        # Save player action
        game_state["history"].append({
            "role": "user", 
            "name": st.session_state.player_name, 
            "content": f"({char_class}) {user_input}"
        })
        
        # Initialize Groq
        client = Groq(api_key=groq_api_key)
        
        try:
            with st.spinner("DM is thinking..."):
                messages = [{"role": "system", "content": game_state["system_prompt"]}]
                # Use only last 10 messages for context
                for m in game_state["history"][-10:]:
                    messages.append({"role": m["role"], "content": m["content"]})
                
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                )
                
                dm_response = chat_completion.choices[0].message.content
                game_state["history"].append({"role": "assistant", "content": dm_response})
            
            st.rerun()
            
        except Exception as e:
            st.error(f"Groq Error: {str(e)}")
