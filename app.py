import streamlit as st
from groq import Groq
import time
import random
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG ---
st.set_page_config(page_title="AI RPG: Battle Edition", page_icon="⚔️", layout="wide")
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED MULTIPLAYER STATE ---
@st.cache_resource
def get_game_state():
    return {
        "history": [{"role": "assistant", "name": "DM", "content": "The journey begins. You stand at the crossroads of a misty forest."}],
        "battle_log": ["World Initialized."], 
        "party_hp": {}, 
        "party_gold": {},      
        "party_inventory": {}, 
        "monster_name": None,
        "monster_hp": 0,
        "max_monster_hp": 0,
        "monster_active": False,
        "system_prompt": (
            "You are a witty Dungeon Master. "
            "To spawn a monster: '[MONSTER: Name, HP: 50]'. "
            "To change health: '[HP_CHANGE: Name, -2]' or '[MONSTER_HP: -10]'. "
            "To give/take gold: '[GOLD: Name, +20]' or '[GOLD: Name, -10]'. "
            "To give items: '[ITEM: Name, ItemName]'. "
            "Describe everything vividly. Keep responses under 60 words."
        )
    }

game_state = get_game_state()

# --- 3. HELPER: AI CALL & TAG PARSER ---
def ask_dm():
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        m_status = f"Monster: {game_state['monster_name']} ({game_state['monster_hp']} HP)" if game_state["monster_active"] else "No active monster."
        status = f" [System: {m_status}, Party: {game_state['party_hp']}, Gold: {game_state['party_gold']}]"
        
        messages = [{"role": "system", "content": game_state["system_prompt"] + status}]
        for m in game_state["history"][-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        
        completion = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
        response = completion.choices[0].message.content
        
        # Parse Monster
        if not game_state["monster_active"]:
            m_match = re.search(r"\[MONSTER:\s*(.*?),\s*HP:\s*(\d+)\]", response)
            if m_match:
                game_state["monster_name"], hp_v = m_match.group(1), int(m_match.group(2))
                game_state["monster_hp"] = game_state["max_monster_hp"] = hp_v
                game_state["monster_active"] = True
                game_state["battle_log"].insert(0, f"⚠️ {game_state['monster_name']} appeared!")

        # Parse Monster Damage
        mh_match = re.search(r"\[MONSTER_HP:\s*([+-]?\d+)\]", response)
        if mh_match and game_state["monster_active"]:
            game_state["monster_hp"] = max(0, game_state["monster_hp"] + int(mh_match.group(1)))

        # Parse Player HP
        ph_match = re.search(r"\[HP_CHANGE:\s*(.*?),\s*([+-]?\d+)\]", response)
        if ph_match:
            target_raw, val = ph_match.group(1).strip(), int(ph_match.group(2))
            for actual_name in game_state["party_hp"].keys():
                if target_raw.lower() == actual_name.lower():
                    game_state["party_hp"][actual_name] = max(0, min(10, game_state["party_hp"][actual_name] + val))

        # Parse Gold (FIXED)
        gold_match = re.search(r"\[GOLD:\s*(.*?),\s*([+-]?\d+)\]", response)
        if gold_match:
            target_raw, val = gold_match.group(1).strip(), int(gold_match.group(2))
            for actual_name in game_state["party_gold"].keys():
                if target_raw.lower() == actual_name.lower():
                    game_state["party_gold"][actual_name] = max(0, game_state["party_gold"][actual_name] + val)
                    verb = "gained" if val > 0 else "lost"
                    game_state["battle_log"].insert(0, f"💰 {actual_name} {verb} {abs(val)} gold!")

        # Parse Items
        item_match = re.search(r"\[ITEM:\s*(.*?),\s*(.*?)\]", response)
        if item_match:
            target_raw, item = item_match.group(1).strip(), item_match.group(2).strip()
            for actual_name in game_state["party_inventory"].keys():
                if target_raw.lower() == actual_name.lower():
                    game_state["party_inventory"][actual_name].append(item)
                    game_state["battle_log"].insert(0, f"🎒 {actual_name} found: {item}")

        return re.sub(r"\[.*?\]", "", response).strip()
    except Exception as e:
        return f"⚠️ DM Error: {e}"

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🧙‍♂️ Character Sheet")
    if "my_name" not in st.session_state: st.session_state.my_name = ""
    name_input = st.text_input("Name:", value=st.session_state.my_name)
    if name_input and name_input != st.session_state.my_name:
        st.session_state.my_name = name_input
        if name_input not in game_state["party_hp"]:
            game_state["party_hp"][name_input], game_state["party_gold"][name_input], game_state["party_inventory"][name_input] = 10, 0, []
        st.rerun()

    if st.session_state.my_name in game_state["party_hp"]:
        curr = st.session_state.my_name
        st.metric("Health", f"{game_state['party_hp'][curr]}/10 ❤️")
        st.metric("Gold", f"{game_state['party_gold'][curr]} 💰")
        
        st.write("🎒 **Inventory**")
        for i, item in enumerate(game_state["party_inventory"].get(curr, [])):
            c1, c2 = st.columns([4, 1])
            c1.caption(f"• {item}")
            if c2.button("🗑️", key=f"del_{i}"):
                game_state["party_inventory"][curr].pop(i)
                st.rerun()
    
    st.divider()
    st.subheader("📜 Battle Log")
    for log in game_state["battle_log"][:5]:
        st.caption(log)

# --- 5. MAIN HUD ---
st.title("⚔️ Rudy's RPG")
h1, h2 = st.columns(2)
with h1:
    if game_state["monster_active"]:
        if game_state["monster_hp"] > 0:
            st.subheader(f"👹 {game_state['monster_name']}")
            pct = max(0.0, min(1.0, float(game_state["monster_hp"]) / float(game_state["max_monster_hp"])))
            st.progress(pct, text=f"HP: {game_state['monster_hp']}/{game_state['max_monster_hp']}")
        else:
            st.success(f"✨ {game_state['monster_name']} Slain!")
            if st.button("Loot & Continue"): 
                game_state["history"].append({"role": "user", "name": "SYSTEM", "content": f"{st.session_state.my_name} is looting. DM, award gold/items."})
                game_state["monster_active"] = False
                game_state["monster_name"] = None 
                game_state["history"].append({"role": "assistant", "name": "DM", "content": ask_dm()})
                st.rerun()
    else:
        st.info("🌲 Path is clear.")

with h2:
    st.subheader("🛡️ Party")
    for p_name, p_hp in game_state["party_hp"].items():
        st.write(f"**{p_name}**: {p_hp}/10 HP | {game_state['party_gold'].get(p_name, 0)} Gold")

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
        if roll >= 10: game_state["monster_hp"] = max(0, game_state["monster_hp"] - 5)
        game_state["history"].append({"role": "user", "name": "SYSTEM", "content": f"🎲 {st.session_state.my_name} rolled {roll}!"})
        game_state["history"].append({"role": "assistant", "name": "DM", "content": ask_dm()})
        st.rerun()

with c_input:
    user_action = st.chat_input("What do you do?")
    if user_action and st.session_state.my_name:
        game_state["history"].append({"role": "user", "name": st.session_state.my_name, "content": user_action})
        game_state["history"].append({"role": "assistant", "name": "DM", "content": ask_dm()})
        st.rerun()
