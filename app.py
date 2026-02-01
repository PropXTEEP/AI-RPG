import streamlit as st
from groq import Groq
import time
import random
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & SYNC ---
st.set_page_config(page_title="Rudy's RPG: Shared Loot", page_icon="⚔️", layout="wide")
# Syncs everyone's screen every 5 seconds
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED MULTIPLAYER STATE ---
@st.cache_resource
def get_game_state():
    return {
        "history": [{
            "role": "assistant", 
            "name": "DM", 
            "content": "🛡️ **The Saga Begins.** The sky bleeds a bruised purple over the Jagged Peaks. You stand before the *Shattered Gate*, where the air smells of ancient ozone and rusted iron. A low hum vibrates through the ground. *What do you do?*"
        }],
        "battle_log": ["✨ A new legend begins..."], 
        "party_hp": {}, 
        "party_gold": {},      
        "party_inventory": {}, 
        "monster_name": None,
        "monster_hp": 0,
        "max_monster_hp": 0,
        "monster_active": False,
        "system_prompt": (
            "You are a master Bard and Dungeon Master. Gothic, atmospheric style. "
            "IMPORTANT: When awarding gold/items/HP, use the EXACT player names provided. "
            "Use sensory details. Narrate actions with drama. "
            "TAGS: [MONSTER: Name, HP: 50], [HP_CHANGE: PlayerName, -2], [MONSTER_HP: -10], [GOLD: PlayerName, +20], [ITEM: PlayerName, ItemName]. "
            "Keep responses under 80 words."
        )
    }

game_state = get_game_state()

# --- 3. HELPER: AI CALL & TAG PARSER ---
def ask_dm():
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        player_list = ", ".join(game_state["party_hp"].keys())
        m_status = f"Monster: {game_state['monster_name']} ({game_state['monster_hp']} HP)" if game_state["monster_active"] else "No monster."
        status = f" [Active Players: {player_list} | Status: {m_status}, Gold: {game_state['party_gold']}]"
        
        messages = [{"role": "system", "content": game_state["system_prompt"] + status}]
        for m in game_state["history"][-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        
        completion = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
        response = completion.choices[0].message.content
        
        # --- ROBUST PARSER ---
        if not game_state["monster_active"]:
            m_match = re.search(r"\[MONSTER:\s*(.*?),\s*HP:\s*(\d+)\]", response)
            if m_match:
                game_state["monster_name"], hp_v = m_match.group(1), int(m_match.group(2))
                game_state["monster_hp"] = game_state["max_monster_hp"] = hp_v
                game_state["monster_active"] = True
                game_state["battle_log"].insert(0, f"⚠️ {game_state['monster_name']} appeared!")

        mh_match = re.search(r"\[MONSTER_HP:\s*([+-]?\d+)\]", response)
        if mh_match and game_state["monster_active"]:
            game_state["monster_hp"] = max(0, game_state["monster_hp"] + int(mh_match.group(1)))

        # Multi-target parsing for HP, Gold, and Items
        for actual_name in game_state["party_hp"].keys():
            # HP
            hp_find = re.findall(rf"\[HP_CHANGE:\s*.*?{re.escape(actual_name)}.*?,\s*([+-]?\d+)\]", response, re.IGNORECASE)
            for val in hp_find:
                game_state["party_hp"][actual_name] = max(0, min(10, game_state["party_hp"][actual_name] + int(val)))
            
            # Gold
            gold_find = re.findall(rf"\[GOLD:\s*.*?{re.escape(actual_name)}.*?,\s*([+-]?\d+)\]", response, re.IGNORECASE)
            for val in gold_find:
                game_state["party_gold"][actual_name] = max(0, game_state["party_gold"][actual_name] + int(val))
                game_state["battle_log"].insert(0, f"💰 {actual_name} modified gold by {val}")

            # Items
            item_find = re.findall(rf"\[ITEM:\s*.*?{re.escape(actual_name)}.*?,\s*(.*?)\]", response, re.IGNORECASE)
            for item in item_find:
                game_state["party_inventory"][actual_name].append(item.strip())
                game_state["battle_log"].insert(0, f"🎒 {actual_name} found: {item.strip()}")

        return re.sub(r"\[.*?\]", "", response).strip()
    except Exception as e:
        return f"⚠️ DM Error: {e}"

# --- 4. SIDEBAR: PERSONAL STATS ---
with st.sidebar:
    st.title("🧙‍♂️ My Hero")
    if "my_name" not in st.session_state: st.session_state.my_name = ""
    name_input = st.text_input("Name:", value=st.session_state.my_name).strip()
    
    if name_input and name_input != st.session_state.my_name:
        st.session_state.my_name = name_input
        if name_input not in game_state["party_hp"]:
            game_state["party_hp"][name_input], game_state["party_gold"][name_input], game_state["party_inventory"][name_input] = 10, 5, []
        st.rerun()

    if st.session_state.my_name in game_state["party_hp"]:
        curr = st.session_state.my_name
        st.metric("Your Health", f"{game_state['party_hp'][curr]}/10 ❤️")
        st.metric("Your Gold", f"{game_state['party_gold'][curr]} 💰")
    
    st.divider()
    st.subheader("📜 Recent Events")
    for log in game_state["battle_log"][:5]:
        st.caption(log)

# --- 5. MAIN HUD: MONSTER & SHARED PARTY VIEW ---
st.title("⚔️ Rudy's Gothic RPG")

# --- Row 1: Monster Status ---
if game_state["monster_active"]:
    m_col1, m_col2 = st.columns([1, 2])
    with m_col1:
        st.subheader(f"👹 {game_state['monster_name']}")
    with m_col2:
        if game_state["monster_hp"] > 0:
            pct = max(0.0, min(1.0, float(game_state["monster_hp"]) / float(game_state["max_monster_hp"])))
            st.progress(pct, text=f"HP: {game_state['monster_hp']}/{game_state['max_monster_hp']}")
        else:
            st.success("The beast is slain!")
            if st.button("Loot Corpse"):
                game_state["history"].append({"role": "user", "name": "SYSTEM", "content": f"{st.session_state.my_name} loots. DM, award items/gold."})
                game_state["monster_active"] = False
                game_state["history"].append({"role": "assistant", "name": "DM", "content": ask_dm()})
                st.rerun()
else:
    st.info("🌲 The trail ahead is shrouded in mist...")

st.divider()

# --- Row 2: Shared Party Inventory & Stats ---
st.subheader("🛡️ The Party's Status & Satchels")
cols = st.columns(len(game_state["party_hp"]) if game_state["party_hp"] else 1)

for i, (p_name, p_hp) in enumerate(game_state["party_hp"].items()):
    with cols[i]:
        st.markdown(f"**{p_name}**")
        st.caption(f"❤️ {p_hp}/10 | 💰 {game_state['party_gold'][p_name]}")
        
        # Display Inventory for this specific player
        items = game_state["party_inventory"].get(p_name, [])
        if items:
            for idx, item in enumerate(items):
                # Only the owner of the item sees the delete button
                if p_name == st.session_state.my_name:
                    c1, c2 = st.columns([4, 1])
                    c1.markdown(f"*{item}*")
                    if c2.button("🗑️", key=f"del_{p_name}_{idx}"):
                        game_state["party_inventory"][p_name].pop(idx)
                        st.rerun()
                else:
                    st.markdown(f"*{item}*")
        else:
            st.caption("Empty pockets.")

st.divider()

# --- 6. CHAT & ACTIONS ---
chat_c = st.container(height=300)
with chat_c:
    for msg in game_state["history"]:
        role_icon = "🧙‍♂️" if msg["role"] == "assistant" else "⚔️"
        with st.chat_message(msg["role"], avatar=role_icon):
            st.write(f"**{msg.get('name', 'DM')}**: {msg['content']}")

if not st.session_state.my_name:
    st.warning("👈 Please enter your Hero's Name in the sidebar to join!")
else:
    c_dice, c_input = st.columns([1, 4])
    with c_dice:
        if st.button("🎲 ROLL D20", use_container_width=True, type="primary"):
            roll = random.randint(1, 20)
            bonus = " CRITICAL!" if roll == 20 else ""
            game_state["history"].append({"role": "user", "name": "SYSTEM", "content": f"🎲 {st.session_state.my_name} rolled a {roll}{bonus}."})
            
            # Simple combat math
            if game_state["monster_active"] and roll >= 10:
                dmg = 5 if roll < 20 else 10
                game_state["monster_hp"] = max(0, game_state["monster_hp"] - dmg)
            
            game_state["history"].append({"role": "assistant", "name": "DM", "content": ask_dm()})
            st.rerun()

    with c_input:
        user_action = st.chat_input("Speak, move, or attack...")
        if user_action:
            game_state["history"].append({"role": "user", "name": st.session_state.my_name, "content": user_action})
            game_state["history"].append({"role": "assistant", "name": "DM", "content": ask_dm()})
            st.rerun()
