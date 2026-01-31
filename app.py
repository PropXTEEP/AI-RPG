import streamlit as st
from groq import Groq
import time
import random
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG ---
st.set_page_config(page_title="AI RPG: Fixed Spawns", page_icon="⚔️", layout="wide")
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED MULTIPLAYER STATE ---
@st.cache_resource
def get_game_state():
    return {
        "history": [{"role": "assistant", "content": "The journey begins. You stand at the crossroads of a misty forest. No enemies in sight."}],
        "party_hp": {}, 
        "party_gold": {},      
        "party_inventory": {}, 
        "monster_name": None,
        "monster_hp": 0,
        "max_monster_hp": 0,
        "monster_active": False,
        "system_prompt": (
            "You are a witty Dungeon Master. "
            "IMPORTANT: Only spawn a monster if the players enter a dangerous area or roll poorly. "
            "To spawn, use: '[MONSTER: Name, HP: 50]'. "
            "Do NOT repeat the spawn tag once the monster is already active. "
            "To change health: '[HP_CHANGE: Name, -2]' or '[MONSTER_HP: -10]'. "
            "To give loot: '[GOLD: Name, +20]' or '[ITEM: Name, ItemName]'. "
            "Keep responses under 60 words."
        )
    }

game_state = get_game_state()

# --- 3. HELPER: AI CALL & TAG PARSER ---
def ask_dm():
    try:
        api_key = st.secrets["GROQ_API_KEY"]
        client = Groq(api_key=api_key)
        
        # We explicitly tell the AI if a monster is ALREADY here so it doesn't spawn a second one
        m_status = f"Active Monster: {game_state['monster_name']} at {game_state['monster_hp']} HP" if game_state["monster_active"] else "No active monster."
        status = f" [System Info: {m_status}, Party: {game_state['party_hp']}, Gold: {game_state['party_gold']}]"
        
        messages = [{"role": "system", "content": game_state["system_prompt"] + status}]
        for m in game_state["history"][-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        
        completion = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
        response = completion.choices[0].message.content
        
        # --- PARSE SYSTEM TAGS ---
        # 1. Monster Spawn (Only if no monster is currently active)
        if not game_state["monster_active"]:
            m_match = re.search(r"\[MONSTER:\s*(.*?),\s*HP:\s*(\d+)\]", response)
            if m_match:
                game_state["monster_name"], hp_v = m_match.group(1), int(m_match.group(2))
                game_state["monster_hp"] = game_state["max_monster_hp"] = hp_v
                game_state["monster_active"] = True

        # 2. Monster Damage
        mh_match = re.search(r"\[MONSTER_HP:\s*([+-]?\d+)\]", response)
        if mh_match and game_state["monster_active"]:
            game_state["monster_hp"] = max(0, game_state["monster_hp"] + int(mh_match.group(1)))

        # 3. Player HP
        ph_match = re.search(r"\[HP_CHANGE:\s*(.*?),\s*([+-]?\d+)\]", response)
        if ph_match:
            target, val = ph_match.group(1).strip(), int(ph_match.group(2))
            if target in game_state["party_hp"]:
                game_state["party_hp"][target] = max(0, min(10, game_state["party_hp"][target] + val))

        # 4. Gold
        gold_match = re.search(r"\[GOLD:\s*(.*?),\s*([+-]?\d+)\]", response)
        if gold_match:
            target, val = gold_match.group(1).strip(), int(gold_match.group(2))
            game_state["party_gold"][target] = max(0, game_state["party_gold"].get(target, 0) + val)

        # 5. Items
        item_match = re.search(r"\[ITEM:\s*(.*?),\s*(.*?)\]", response)
        if item_match:
            target, item = item_match.group(1).strip(), item_match.group(2).strip()
            if target in game_state["party_inventory"]:
                game_state["party_inventory"][target].append(item)

        return re.sub(r"\[.*?\]", "", response).strip()
    except Exception as e:
        return f"⚠️ DM Error: {e}"

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🧙‍♂️ Character Sheet")
    if "my_name" not in st.session_state: st.session_state.my_name = ""
    
    name = st.text_input("Name:", value=st.session_state.my_name)
    if name and name != st.session_state.my_name:
        st.session_state.my_name = name
        if name not in game_state["party_hp"]:
            game_state["party_hp"][name], game_state["party_gold"][name], game_state["party_inventory"][name] = 10, 0, ["Rusty Dagger"]
        st.rerun()

    if st.session_state.my_name in game_state["party_hp"]:
        st.subheader(f"💰 {game_state['party_gold'].get(name, 0)} Gold")
        if st.button("Buy Potion (20g)"):
            if game_state["party_gold"].get(name, 0) >= 20:
                game_state["party_gold"][name] -= 20
                game_state["party_hp"][name] = min(10, game_state["party_hp"][name] + 5)
                st.rerun()
        st.write("🎒 **Inventory**")
        for item in game_state["party_inventory"].get(name, []):
            st.caption(f"• {item}")
    
    st.divider()
    if st.button("🔥 Reset World"):
        game_state.update({"monster_active": False, "monster_name": None, "monster_hp": 0, "max_monster_hp": 0, "party_hp": {}, "party_gold": {}, "party_inventory": {}, "history": [{"role": "assistant", "content": "The world resets..."}]})
        st.rerun()

# --- 5. MAIN HUD ---
st.title("⚔️ AI Multiplayer RPG")

h1, h2 = st.columns(2)
with h1:
    if game_state["monster_active"]:
        st.subheader(f"👹 {game_state['monster_name']}")
        if game_state["max_monster_hp"] > 0:
            pct = max(0.0, min(1.0, float(game_state["monster_hp"]) / float(game_state["max_monster_hp"])))
            st.progress(pct, text=f"HP: {game_state['monster_hp']}/{game_state['max_monster_hp']}")
        
        if game_state["monster_hp"] <= 0:
            st.success("Enemy Slain!")
            if st.button("Loot & Continue"): 
                game_state["monster_active"] = False
                game_state["monster_name"] = None # Clear name to prevent logic loops
                st.rerun()
    else:
        st.info("🌲 Exploration Mode")

with h2:
    st.subheader("🛡️ The Party")
    for p_name, p_hp in game_state["party_hp"].items():
        st.progress(p_hp/10.0, text=f"{p_name}: {p_hp}/10 HP | {game_state['party_gold'].get(p_name, 0)} Gold")

st.divider()

# --- 6. CHAT & ACTIONS ---
chat_c = st.container(height=300)
with chat_c:
    for msg in game_state["history"]:
        avatar = "🧙‍♂️" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(f"**{msg.get('name', 'DM')}**: {msg['content']}")

c_dice, c_input = st.columns([1, 4])
with c_dice:
    if st.button("🎲 ROLL D20", use_container_width=True, type="primary", disabled=not game_state["monster_active"]):
        roll = random.randint(1, 20)
        if roll >= 18: game_state["monster_hp"] -= 15
        elif roll >= 10: game_state["monster_hp"] -= 5
        elif roll <= 5: game_state["party_hp"][st.session_state.my_name] = max(0, game_state["party_hp"][st.session_state.my_name] - 2)
        
        game_state["history"].append({"role": "user", "name": "SYSTEM", "content": f"🎲 {st.session_state.my_name} rolled {roll}!"})
        game_state["history"].append({"role": "assistant", "content": ask_dm()})
        st.rerun()

with c_input:
    user_action = st.chat_input("Enter action...")
    if user_action and st.session_state.my_name:
        game_state["history"].append({"role": "user", "name": st.session_state.my_name, "content": user_action})
        game_state["history"].append({"role": "assistant", "content": ask_dm()})
        st.rerun()
