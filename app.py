import streamlit as st
from groq import Groq
import time
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & SYNC ---
st.set_page_config(page_title="AI RPG: Dice Aware", page_icon="⚔️", layout="wide")
st_autorefresh(interval=5000, key="rpg_sync")

@st.cache_resource
def get_shared_game_state():
    return {
        "history": [{"role": "assistant", "content": "The party stands before the heavy stone doors of the Crypt. What do you do?"}],
        "system_prompt": "You are a professional Dungeon Master. When a player rolls a die, you MUST interpret the result: 1 is a hilarious/terrible failure, 20 is a legendary success. React to the specific number rolled. Keep responses under 80 words."
    }

game_state = get_shared_game_state()

# --- 2. DM BRAIN FUNCTION ---
def ask_dungeon_master(api_key):
    client = Groq(api_key=api_key)
    try:
        messages = [{"role": "system", "content": game_state["system_prompt"]}]
        # Give context of the last 12 events
        for m in game_state["history"][-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        
        completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"The DM is speechless (Error: {str(e)})"

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Party Controls")
    groq_key = st.text_input("Groq API Key", type="password")
    
    st.divider()
    
    if "player_name" not in st.session_state:
        st.session_state.player_name = "Adventurer"
    st.session_state.player_name = st.text_input("Character Name", value=st.session_state.player_name)
    char_class = st.selectbox("Class", ["Warrior", "Mage", "Rogue", "Paladin"])

    st.divider()
    
    # DICE ROLLER WITH AI AWARENESS
    st.subheader("🎲 Roll the Dice")
    if st.button("Roll D20"):
        if not groq_key:
            st.error("Enter Groq Key first!")
        else:
            roll = random.randint(1, 20)
            # 1. Log the roll into history
            roll_text = f"🎲 {st.session_state.player_name} ({char_class}) rolled a {roll}!"
            game_state["history"].append({"role": "user", "name": "SYSTEM", "content": roll_text})
            
            # 2. Immediately trigger DM to react to the roll
            with st.spinner("DM is interpreting the roll..."):
                dm_reaction = ask_dungeon_master(groq_key)
                game_state["history"].append({"role": "assistant", "content": dm_reaction})
            st.rerun()

    if st.button("🔥 Reset Game"):
        game_state["history"] = [{"role": "assistant", "content": "The timeline resets..."}]
        st.rerun()

# --- 4. GAME CHAT ---
st.title("⚔️ The AI Dungeon")

for msg in game_state["history"]:
    avatar = "🧙‍♂️" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        if "name" in msg:
            st.write(f"**{msg['name']}**: {msg['content']}")
        else:
            st.write(msg["content"])

# --- 5. MANUAL TEXT INPUT ---
user_input = st.chat_input("Describe your action...")

if user_input:
    if not groq_key:
        st.error("Need API Key!")
    else:
        # Add action
        action_text = f"({char_class}) {user_input}"
        game_state["history"].append({"role": "user", "name": st.session_state.player_name, "content": action_text})
        
        # Get DM reaction
        with st.spinner("The DM watches..."):
            dm_response = ask_dungeon_master(groq_key)
            game_state["history"].append({"role": "assistant", "content": dm_response})
        st.rerun()
