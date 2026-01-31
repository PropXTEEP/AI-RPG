import streamlit as st
from groq import Groq
import time
import random
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG ---
st.set_page_config(page_title="AI RPG: Auto-DM", page_icon="⚔️", layout="wide")
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED MULTIPLAYER STATE ---
@st.cache_resource
def get_game_state():
    return {
        "history": [{"role": "assistant", "content": "You stand at the entrance of a crumbling ruin. The air is cold. What do you do?"}],
        "party_hp": {}, 
        "monster_name": None,
        "monster_hp": 0,
        "max_monster_hp": 0,
        "monster_active": False,
        "system_prompt": (
            "You are a witty Dungeon Master. "
            "COMBAT RULES: To start a fight, you MUST include '[MONSTER: Name, HP: Number]' in your text. "
            "Example: 'A giant spider drops! [MONSTER: Giant Spider, HP: 40]'. "
            "When a monster's HP reaches 0, describe its death. "
            "Keep responses under 70 words."
        )
    }

game_state = get_game_state()

# --- 3. HELPER: AI CALL & PARSING ---
def ask_dm():
    try:
        api_key = st.secrets["GROQ_API_KEY"]
        client = Groq(api_key=api_key)
        
        # Inject state info into the prompt dynamically
        status = f" [Current Status: Monster Active: {game_state['monster_active']}, Monster HP: {game_state['monster_hp']}, Party: {game_state['party_hp']}]"
        
        messages = [{"role": "system", "content": game_state["system_prompt"] + status}]
        for m in game_state["history"][-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        
        completion = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
        response = completion.choices[0].message.content
        
        # --- AUTO-DETECTION LOGIC ---
        # Look for [MONSTER: Name, HP: Number]
        match = re.search(r"\[MONSTER:\s*(.*?),\s*HP:\s*(\d+)\]", response)
        if match:
            game_state["monster_name"] = match.group(1)
            game_state["monster_hp"] = int(match.group(2))
            game_state["max_monster_hp"] = int(match.group(2))
            game_state["monster_active"] = True
            # Clean the tag out of the text so players don't see the 'code'
            response = re.sub(r"\[MONSTER:.*?\]", "", response)
            
        return response
    except Exception as e:
        return f"⚠️ DM Error: {e}"

# --- 4. SIDEBAR: PARTY MGMT ---
with st.sidebar:
    st.title("🧙‍♂️ Character Sheet")
    if "my_name" not in st.session_state: st.session_state.my_name = ""
    
    temp_name = st.text_input("Your Name", value=st.session_state.my_name)
    if temp_name and temp_name != st.session_state.my_name:
        st.session_state.my_name = temp_name
        if temp_name not in game_state["party_hp"]:
            game_state["party_hp"][temp_name] = 10
        st.rerun()

    char_class = st.selectbox("Class", ["Warrior", "Mage", "Rogue", "Paladin", "Bard"])

    st.divider()
    st.subheader("👥 Party Management")
    for p_name in list(game_state["party_hp"].keys()):
        c1, c2 = st.columns([3, 1])
        c1.write(p_name)
        if c2.button("❌", key=f"del_{p_name}"):
            del game_state["party_hp"][p_name]
            if st.session_state.my_name == p_name: st.session_state.my_name = ""
            st.rerun()

    if st.button("🔥 Reset Adventure"):
        game_state["history"] = [{"role": "assistant", "content": "The world resets..."}]
        game_state["monster_active"] = False
        game_state["party_hp"] = {}
        st.rerun()

# --- 5. MAIN HUD ---
st.title("⚔️ AI Multiplayer RPG")

if game_state["monster_active"]:
    h_m, h_p = st.columns(2)
    with h_m:
        st.subheader(f"👹 {game_state['monster_name']}")
        pct = max(0, game_state["monster_hp"] / game_state["max_monster_hp"])
        st.progress(pct, text=f"HP: {game_state['monster_hp']}/{game_state['max_monster_hp']}")
        if game_state["monster_hp"] <= 0:
            game_state["monster_active"] = False
            st.success("Enemy Slain!")
    with h_p:
        st.subheader("🛡️ The Party")
        for p_name, p_hp in game_state["party_hp"].items():
            st.progress(max(0, p_hp/10), text=f"{p_name}: {p_hp}/10 HP")
else:
    st.subheader("🛡️ Party Status (Exploring)")
    if game_state["party_hp"]:
        cols = st.columns(len(game_state["party_hp"]))
        for i, (p_name, p_hp) in enumerate(game_state["party_hp"].items()):
            cols[i].metric(label=p_name, value=f"{p_hp}/10 HP")

st.divider()

# --- 6. CHAT & ACTIONS ---
chat_container = st.container(height=350)
with chat_container:
    for msg in game_state["history"]:
        avatar = "🧙‍♂️" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(f"**{msg.get('name', 'DM')}**: {msg['content']}")

col_dice, col_input = st.columns([1, 4])
with col_dice:
    # Button is only active during combat
    if st.button("🎲 ROLL D20", use_container_width=True, type="primary", disabled=not game_state["monster_active"]):
        roll = random.randint(1, 20)
        # Combat Logic
        if roll >= 15: game_state["monster_hp"] -= 10
        elif roll >= 10: game_state["monster_hp"] -= 5
        elif roll <= 5: game_state["party_hp"][st.session_state.my_name] = max(0, game_state["party_hp"][st.session_state.my_name] - 2)
        
        game_state["history"].append({"role": "user", "name": "SYSTEM", "content": f"🎲 {st.session_state.my_name} rolled {roll}!"})
        game_state["history"].append({"role": "assistant", "content": ask_dm()})
        st.rerun()

with col_input:
    user_action = st.chat_input("What do you do?")
    if user_action and st.session_state.my_name:
        game_state["history"].append({"role": "user", "name": st.session_state.my_name, "content": f"({char_class}) {user_action}"})
        game_state["history"].append({"role": "assistant", "content": ask_dm()})
        st.rerun()
