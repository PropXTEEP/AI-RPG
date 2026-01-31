import streamlit as st
from groq import Groq
import time
import random
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG ---
st.set_page_config(page_title="AI RPG: Dynamic Combat", page_icon="⚔️", layout="wide")
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED MULTIPLAYER STATE ---
@st.cache_resource
def get_game_state():
    return {
        "history": [{"role": "assistant", "content": "The journey begins. You stand at the crossroads of a misty forest. There are no enemies in sight... yet."}],
        "party_hp": {}, 
        "monster_name": None,
        "monster_hp": 0,
        "max_monster_hp": 0,
        "monster_active": False,
        "system_prompt": "You are a witty Dungeon Master. If you want to start a fight, mention an enemy name. If a fight is active, track HP. When the monster hits 0 HP, describe their death. Keep responses under 70 words."
    }

game_state = get_game_state()

# --- 3. HELPER: AI CALL ---
def ask_dm():
    try:
        api_key = st.secrets["GROQ_API_KEY"]
        client = Groq(api_key=api_key)
        
        # We tell the AI the current status so it can decide to start or end a fight
        status = f" [System Info: Monster Active: {game_state['monster_active']}, Monster HP: {game_state['monster_hp']}, Party: {game_state['party_hp']}]"
        
        messages = [{"role": "system", "content": game_state["system_prompt"] + status}]
        for m in game_state["history"][-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        
        completion = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
        response = completion.choices[0].message.content
        
        # LOGIC: If the DM mentions a common monster keyword but no monster is active, we can 'auto-detect'
        # Or you can manually trigger it via the chat. 
        return response
    except Exception as e:
        return f"⚠️ DM Error: {e}"

# --- 4. SIDEBAR: CHARACTER SETUP ---
with st.sidebar:
    st.title("🧙‍♂️ Character Sheet")
    if "my_name" not in st.session_state:
        st.session_state.my_name = f"Hero_{random.randint(100, 999)}"
    
    name = st.text_input("Your Name", value=st.session_state.my_name)
    st.session_state.my_name = name
    char_class = st.selectbox("Class", ["Warrior", "Mage", "Rogue", "Paladin", "Bard"])

    if name not in game_state["party_hp"]:
        game_state["party_hp"][name] = 10

    st.divider()
    
    # DM TOOLS (For you to trigger encounters)
    st.subheader("🛠️ DM Tools")
    m_name = st.text_input("Spawn Monster Name", placeholder="e.g. Ancient Dragon")
    m_health = st.number_input("Monster HP", min_value=10, max_value=500, value=50)
    if st.button("Spawn Enemy"):
        game_state["monster_name"] = m_name
        game_state["monster_hp"] = m_health
        game_state["max_monster_hp"] = m_health
        game_state["monster_active"] = True
        game_state["history"].append({"role": "assistant", "content": f"⚠️ A wild {m_name} appears!"})
        st.rerun()

    if st.button("🔥 Reset Adventure"):
        game_state["history"] = [{"role": "assistant", "content": "The world resets..."}]
        game_state["monster_active"] = False
        game_state["party_hp"] = {}
        st.rerun()

# --- 5. MAIN AREA: DYNAMIC HUD ---
st.title("⚔️ The AI World")

# Conditional HUD
if game_state["monster_active"]:
    hud_monster, hud_party = st.columns(2)
    
    with hud_monster:
        st.subheader(f"👹 Enemy: {game_state['monster_name']}")
        pct = max(0, game_state["monster_hp"] / game_state["max_monster_hp"])
        st.progress(pct, text=f"Health: {game_state['monster_hp']} / {game_state['max_monster_hp']}")
        
        if game_state["monster_hp"] <= 0:
            st.balloons()
            game_state["monster_active"] = False # This removes the bar on next refresh
            st.success("The enemy is defeated!")
            if st.button("Clear Monster"): st.rerun()

    with hud_party:
        st.subheader("🛡️ The Party")
        for p_name, p_hp in game_state["party_hp"].items():
            st.progress(max(0, p_hp/10), text=f"{p_name}: {p_hp}/10 HP")
else:
    # Non-combat HUD: Just show the party
    st.subheader("🛡️ Party Status (Exploration Mode)")
    cols = st.columns(len(game_state["party_hp"]) if game_state["party_hp"] else 1)
    for i, (p_name, p_hp) in enumerate(game_state["party_hp"].items()):
        cols[i].metric(label=p_name, value=f"{p_hp}/10 HP")

st.divider()

# --- 6. CHAT HISTORY ---
chat_container = st.container(height=350)
with chat_container:
    for msg in game_state["history"]:
        avatar = "🧙‍♂️" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            sender = msg.get("name", "DM")
            st.write(f"**{sender}**: {msg['content']}")

# --- 7. ACTION CONTROLS ---
col_dice, col_input = st.columns([1, 4])

with col_dice:
    # Disable dice if no monster
    dice_disabled = not game_state["monster_active"]
    if st.button("🎲 ROLL D20", use_container_width=True, type="primary", disabled=dice_disabled):
        roll = random.randint(1, 20)
        
        if roll >= 15:
            game_state["monster_hp"] -= 10
            res = "Critical Hit! (-10 DMG)"
        elif roll >= 10:
            game_state["monster_hp"] -= 5
            res = "Hit! (-5 DMG)"
        elif roll <= 5:
            game_state["party_hp"][name] = max(0, game_state["party_hp"][name] - 2)
            res = "Counter-attacked! (-2 HP)"
        else:
            res = "You missed."
            
        game_state["history"].append({"role": "user", "name": "SYSTEM", "content": f"🎲 {name} rolled a {roll}! {res}"})
        game_state["history"].append({"role": "assistant", "content": ask_dm()})
        st.rerun()

with col_input:
    user_action = st.chat_input("What do you do?")
    if user_action:
        game_state["history"].append({"role": "user", "name": name, "content": f"({char_class}) {user_action}"})
        game_state["history"].append({"role": "assistant", "content": ask_dm()})
        st.rerun()
