import streamlit as st
from groq import Groq
import time
import random
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG ---
st.set_page_config(page_title="AI RPG: Combat Edition", page_icon="⚔️", layout="wide")
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED MULTIPLAYER STATE ---
@st.cache_resource
def get_game_state():
    return {
        "history": [{"role": "assistant", "content": "The party enters the cavern... suddenly, a **Goblin King** leaps from the shadows!"}],
        "party_hp": {}, 
        "monster_name": "Goblin King",
        "monster_hp": 30,
        "system_prompt": "You are a witty Dungeon Master. Track combat. If players roll high, subtract monster HP. If they roll low, they lose 1 HP. When monster HP hits 0, they win. Keep responses under 70 words."
    }

game_state = get_game_state()

# --- 3. HELPER: AI CALL ---
def ask_dm(user_context=""):
    try:
        api_key = st.secrets["GROQ_API_KEY"]
        client = Groq(api_key=api_key)
        
        # We inject the current HP stats so the AI always knows the score
        hp_status = f" Current Stats: Monster({game_state['monster_name']}) HP: {game_state['monster_hp']}. Party HP: {game_state['party_hp']}"
        
        messages = [{"role": "system", "content": game_state["system_prompt"] + hp_status}]
        for m in game_state["history"][-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        
        completion = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
        return completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ DM Error: {e}"

# --- 4. SIDEBAR: PARTY TRACKER ---
with st.sidebar:
    st.title("🛡️ Party Info")
    if "my_name" not in st.session_state:
        st.session_state.my_name = f"Hero_{random.randint(100, 999)}"
    
    name = st.text_input("Character Name", value=st.session_state.my_name)
    st.session_state.my_name = name
    char_class = st.selectbox("Class", ["Warrior", "Mage", "Rogue", "Paladin"])

    if name not in game_state["party_hp"]:
        game_state["party_hp"][name] = 10

    st.subheader("🩸 Party Health")
    for player, hp in game_state["party_hp"].items():
        st.progress(hp/10, text=f"{player}: {hp}/10")

    if st.button("🔥 Reset Adventure"):
        game_state["history"] = [{"role": "assistant", "content": "A new journey begins..."}]
        game_state["monster_hp"] = 30
        game_state["party_hp"] = {}
        st.rerun()

# --- 5. MAIN AREA: COMBAT & CHAT ---
st.title("⚔️ AI Dungeon: Battle for the Crypt")

# --- MONSTER BATTLE BAR ---
if game_state["monster_hp"] > 0:
    st.error(f"👹 ENEMY: {game_state['monster_name']}")
    st.progress(game_state["monster_hp"]/30, text=f"Monster Health: {game_state['monster_hp']}/30")
else:
    st.success("🏆 VICTORY! The monster has been defeated.")

# --- CHAT HISTORY ---
chat_container = st.container(height=400)
with chat_container:
    for msg in game_state["history"]:
        avatar = "🧙‍♂️" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            sender = msg.get("name", "DM")
            st.write(f"**{sender}**: {msg['content']}")

# --- MAIN INTERACTIVE AREA (Dice + Input) ---
st.divider()
col1, col2 = st.columns([1, 4])

with col1:
    if st.button("🎲 ROLL D20", use_container_width=True, type="primary"):
        roll = random.randint(1, 20)
        
        # Logic: Adjust HP based on roll
        if roll >= 15:
            game_state["monster_hp"] -= 5
            res = "Critical Hit!"
        elif roll <= 5:
            game_state["party_hp"][name] -= 1
            res = "Ouch! You took damage."
        else:
            res = "A decent effort."
            
        roll_text = f"🎲 {name} rolled a {roll}! {res}"
        game_state["history"].append({"role": "user", "name": "SYSTEM", "content": roll_text})
        
        with st.spinner("DM narrating..."):
            game_state["history"].append({"role": "assistant", "content": ask_dm()})
        st.rerun()

with col2:
    user_action = st.chat_input("What is your move?")
    if user_action:
        game_state["history"].append({"role": "user", "name": name, "content": f"({char_class}) {user_action}"})
        with st.spinner("The DM watches..."):
            game_state["history"].append({"role": "assistant", "content": ask_dm()})
        st.rerun()
