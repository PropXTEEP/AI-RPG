import streamlit as st
from groq import Groq
import time
import random
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG ---
st.set_page_config(page_title="AI RPG: Battle Edition", page_icon="⚔️", layout="wide")
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED STATE ---
@st.cache_resource
def get_game_state():
    return {
        "history": [{"role": "assistant", "name": "DM", "content": "The journey begins. You stand at the crossroads of a misty forest."}],
        "battle_log": [], # NEW: Track damage/events specifically
        "party_hp": {}, 
        "party_gold": {},      
        "party_inventory": {}, 
        "monster_name": None,
        "monster_hp": 0,
        "max_monster_hp": 0,
        "monster_active": False,
        "system_prompt": (
            "You are a witty Dungeon Master. "
            "To spawn a monster, use: '[MONSTER: Name, HP: 50]'. "
            "IMPORTANT: If you spawn a monster, you MUST still describe its appearance in your text for the players. "
            "To damage/heal: '[MONSTER_HP: -10]' or '[HP_CHANGE: Name, -2]'. "
            "To give loot: '[GOLD: Name, +20]' or '[ITEM: Name, ItemName]'. "
            "Keep responses under 60 words and be descriptive."
        )
    }

game_state = get_game_state()

# --- 3. HELPER: AI & PARSING ---
def ask_dm():
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        m_status = f"Active Monster: {game_state['monster_name']} ({game_state['monster_hp']} HP)" if game_state["monster_active"] else "No active monster."
        status = f" [System Info: {m_status}, Party: {game_state['party_hp']}]"
        
        messages = [{"role": "system", "content": game_state["system_prompt"] + status}]
        for m in game_state["history"][-10:]:
            messages.append({"role": m["role"], "content": m["content"]})
        
        completion = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
        response = completion.choices[0].message.content
        
        # --- PARSE TAGS ---
        if not game_state["monster_active"]:
            m_match = re.search(r"\[MONSTER:\s*(.*?),\s*HP:\s*(\d+)\]", response)
            if m_match:
                game_state["monster_name"], hp_v = m_match.group(1), int(m_match.group(2))
                game_state["monster_hp"] = game_state["max_monster_hp"] = hp_v
                game_state["monster_active"] = True
                game_state["battle_log"].insert(0, f"⚠️ A {game_state['monster_name']} appeared!")

        mh_match = re.search(r"\[MONSTER_HP:\s*([+-]?\d+)\]", response)
        if mh_match and game_state["monster_active"]:
            game_state["monster_hp"] = max(0, game_state["monster_hp"] + int(mh_match.group(1)))

        # (Other tags like GOLD/ITEM/HP_CHANGE remain the same as your previous logic)
        
        return re.sub(r"\[.*?\]", "", response).strip()
    except Exception as e:
        return f"⚠️ DM Error: {e}"

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🧙‍♂️ Character Sheet")
    name = st.text_input("Name:", value=st.session_state.get("my_name", ""))
    if name and name != st.session_state.get("my_name"):
        st.session_state.my_name = name
        if name not in game_state["party_hp"]:
            game_state["party_hp"][name], game_state["party_gold"][name], game_state["party_inventory"][name] = 10, 0, ["Rusty Dagger"]
        st.rerun()

    if st.session_state.get("my_name") in game_state["party_hp"]:
        st.metric("Health", f"{game_state['party_hp'][name]}/10 ❤️")
        st.metric("Gold", f"{game_state['party_gold'][name]} 💰")
    
    st.divider()
    # NEW: Battle Log in Sidebar
    st.subheader("📜 Battle Log")
    for log in game_state["battle_log"][:5]:
        st.caption(log)

# --- 5. MAIN HUD ---
st.title("⚔️ AI Multiplayer RPG")

h1, h2 = st.columns(2)
with h1:
    if game_state["monster_active"]:
        # Fix: Health bar only shows if monster is alive
        if game_state["monster_hp"] > 0:
            st.subheader(f"👹 {game_state['monster_name']}")
            pct = max(0.0, min(1.0, float(game_state["monster_hp"]) / float(game_state["max_monster_hp"])))
            st.progress(pct, text=f"HP: {game_state['monster_hp']}/{game_state['max_monster_hp']}")
        else:
            st.success(f"✨ {game_state['monster_name']} Defeated!")
            if st.button("Loot & Continue"): 
                game_state["monster_active"] = False
                game_state["monster_name"] = None # Fully clearing state
                game_state["monster_hp"] = 0
                game_state["battle_log"].insert(0, "The area is now quiet.")
                st.rerun()
    else:
        st.info("🌲 Exploration Mode")

with h2:
    st.subheader("🛡️ The Party")
    for p_name, p_hp in game_state["party_hp"].items():
        st.write(f"**{p_name}**: {p_hp}/10 HP")

st.divider()

# --- 6. CHAT & ACTIONS ---
chat_c = st.container(height=300)
with chat_c:
    for msg in game_state["history"]:
        with st.chat_message(msg["role"], avatar="🧙‍♂️" if msg["role"] == "assistant" else "👤"):
            st.write(f"**{msg.get('name', 'DM')}**: {msg['content']}")

c_dice, c_input = st.columns([1, 4])
with c_dice:
    if st.button("🎲 ROLL D20", use_container_width=True, type="primary", disabled=not game_state["monster_active"]):
        roll = random.randint(1, 20)
        dmg = 0
        if roll >= 18: dmg = 15
        elif roll >= 10: dmg = 5
        
        if dmg > 0:
            game_state["monster_hp"] = max(0, game_state["monster_hp"] - dmg)
            game_state["battle_log"].insert(0, f"⚔️ {st.session_state.my_name} hit for {dmg}!")
        else:
            game_state["battle_log"].insert(0, f"💨 {st.session_state.my_name} missed!")

        game_state["history"].append({"role": "user", "name": "SYSTEM", "content": f"🎲 {st.session_state.my_name} rolled {roll}!"})
        game_state["history"].append({"role": "assistant", "name": "DM", "content": ask_dm()})
        st.rerun()

with c_input:
    user_action = st.chat_input("Enter action...")
    if user_action and st.session_state.get("my_name"):
        game_state["history"].append({"role": "user", "name": st.session_state.my_name, "content": user_action})
        game_state["history"].append({"role": "assistant", "name": "DM", "content": ask_dm()})
        st.rerun()
