import streamlit as st
from groq import Groq
import time
import random
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG ---
st.set_page_config(page_title="AI RPG: Battle HUD", page_icon="⚔️", layout="wide")
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED MULTIPLAYER STATE ---
@st.cache_resource
def get_game_state():
    return {
        "history": [{"role": "assistant", "content": "The party enters the cavern... a giant **Stone Golem** rumbles to life!"}],
        "party_hp": {}, 
        "monster_name": "Stone Golem",
        "monster_hp": 50,
        "max_monster_hp": 50,
        "system_prompt": "You are a professional Dungeon Master. Track combat. If players roll high, subtract monster HP. If they roll low, they lose 1 HP. Keep responses punchy and under 70 words."
    }

game_state = get_game_state()

# --- 3. HELPER: AI CALL ---
def ask_dm():
    try:
        api_key = st.secrets["GROQ_API_KEY"]
        client = Groq(api_key=api_key)
        hp_status = f" Current Stats: Monster({game_state['monster_name']}) HP: {game_state['monster_hp']}. Party HP: {game_state['party_hp']}"
        messages = [{"role": "system", "content": game_state["system_prompt"] + hp_status}]
        for m in game_state["history"][-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        completion = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
        return completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ DM Error: {e}"

# --- 4. SIDEBAR: PERSONAL SETUP ---
with st.sidebar:
    st.title("🧙‍♂️ Character Sheet")
    if "my_name" not in st.session_state:
        st.session_state.my_name = f"Hero_{random.randint(100, 999)}"
    
    name = st.text_input("Character Name", value=st.session_state.my_name)
    st.session_state.my_name = name
    char_class = st.selectbox("Class", ["Warrior", "Mage", "Rogue", "Paladin", "Bard"])

    if name not in game_state["party_hp"]:
        game_state["party_hp"][name] = 10

    st.divider()
    if st.button("🔥 Reset Adventure"):
        game_state["history"] = [{"role": "assistant", "content": "The mists reset the world..."}]
        game_state["monster_hp"] = 50
        game_state["party_hp"] = {}
        st.rerun()

# --- 5. MAIN AREA: BATTLE HUD ---
st.title("⚔️ The AI Encounter")

# Create two columns for the HUD
hud_monster, hud_party = st.columns(2)

with hud_monster:
    st.subheader(f"👹 Enemy: {game_state['monster_name']}")
    if game_state["monster_hp"] > 0:
        pct = max(0, game_state["monster_hp"] / game_state["max_monster_hp"])
        st.progress(pct, text=f"HP: {game_state['monster_hp']} / {game_state['max_monster_hp']}")
    else:
        st.success("✨ VICTORY: The enemy has fallen!")

with hud_party:
    st.subheader("🛡️ The Party")
    # Display all players currently in the game state
    for p_name, p_hp in game_state["party_hp"].items():
        hp_pct = max(0, p_hp / 10)
        # Color coding: Green if healthy, Red if low
        label = "🩸" if p_hp < 4 else "💚"
        st.progress(hp_pct, text=f"{label} {p_name}: {p_hp}/10 HP")

st.divider()

# --- 6. CHAT HISTORY ---
chat_container = st.container(height=400)
with chat_container:
    for msg in game_state["history"]:
        avatar = "🧙‍♂️" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            sender = msg.get("name", "DM")
            st.write(f"**{sender}**: {msg['content']}")

# --- 7. ACTION CONTROLS ---
# Using columns to put the Dice and Input on the same line
col_dice, col_input = st.columns([1, 4])

with col_dice:
    if st.button("🎲 ROLL D20", use_container_width=True, type="primary"):
        roll = random.randint(1, 20)
        
        # Battle Logic
        if roll >= 15:
            game_state["monster_hp"] -= 10
            result = "Critical Hit! (-10 DMG)"
        elif roll >= 10:
            game_state["monster_hp"] -= 5
            result = "A solid strike! (-5 DMG)"
        elif roll <= 5:
            game_state["party_hp"][name] = max(0, game_state["party_hp"][name] - 2)
            result = "You stumbled! (-2 HP)"
        else:
            result = "A narrow miss."
            
        roll_entry = f"🎲 {name} rolled a {roll}! {result}"
        game_state["history"].append({"role": "user", "name": "SYSTEM", "content": roll_entry})
        
        with st.spinner("DM responding..."):
            game_state["history"].append({"role": "assistant", "content": ask_dm()})
        st.rerun()

with col_input:
    user_action = st.chat_input("Speak or act...")
    if user_action:
        game_state["history"].append({"role": "user", "name": name, "content": f"({char_class}) {user_action}"})
        with st.spinner("DM watching..."):
            game_state["history"].append({"role": "assistant", "content": ask_dm()})
        st.rerun()
