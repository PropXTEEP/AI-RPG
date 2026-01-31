import streamlit as st
from groq import Groq
import time
import random
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG ---
st.set_page_config(page_title="AI RPG: Fixed Spawns", page_icon="⚔️", layout="wide")

# Refresh every 5 seconds so players see updates from others
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED MULTIPLAYER STATE ---
# We use cache_resource to make this object global across all sessions
@st.cache_resource
def get_game_state():
    return {
        "history": [{"role": "assistant", "name": "DM", "content": "The journey begins. You stand at the crossroads of a misty forest. No enemies in sight."}],
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
            "Keep responses under 60 words. Be dramatic."
        )
    }

game_state = get_game_state()

# --- 3. HELPER: AI CALL & TAG PARSER ---
def ask_dm():
    try:
        # Check for API Key safely
        if "GROQ_API_KEY" not in st.secrets:
            return "⚠️ Error: GROQ_API_KEY not found in .streamlit/secrets.toml"
            
        api_key = st.secrets["GROQ_API_KEY"]
        client = Groq(api_key=api_key)
        
        # Context for the AI
        m_status = f"Active Monster: {game_state['monster_name']} ({game_state['monster_hp']} HP)" if game_state["monster_active"] else "No active monster."
        status = f" [System Info: {m_status}, Party HP: {game_state['party_hp']}, Gold: {game_state['party_gold']}]"
        
        # Build Message History
        messages = [{"role": "system", "content": game_state["system_prompt"] + status}]
        # We take the last 10 messages to keep context window manageable
        for m in game_state["history"][-10:]:
            messages.append({"role": m["role"], "content": m["content"]})
        
        completion = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
        response = completion.choices[0].message.content
        
        # --- PARSE SYSTEM TAGS ---
        
        # 1. Monster Spawn
        if not game_state["monster_active"]:
            m_match = re.search(r"\[MONSTER:\s*(.*?),\s*HP:\s*(\d+)\]", response)
            if m_match:
                game_state["monster_name"] = m_match.group(1)
                hp_val = int(m_match.group(2))
                game_state["monster_hp"] = hp_val
                game_state["max_monster_hp"] = hp_val
                game_state["monster_active"] = True

        # 2. Monster Damage/Heal
        mh_match = re.search(r"\[MONSTER_HP:\s*([+-]?\d+)\]", response)
        if mh_match and game_state["monster_active"]:
            change = int(mh_match.group(1))
            game_state["monster_hp"] = max(0, game_state["monster_hp"] + change)

        # 3. Player HP Change
        ph_match = re.search(r"\[HP_CHANGE:\s*(.*?),\s*([+-]?\d+)\]", response)
        if ph_match:
            target, val = ph_match.group(1).strip(), int(ph_match.group(2))
            if target in game_state["party_hp"]:
                game_state["party_hp"][target] = max(0, min(10, game_state["party_hp"][target] + val))

        # 4. Gold
        gold_match = re.search(r"\[GOLD:\s*(.*?),\s*([+-]?\d+)\]", response)
        if gold_match:
            target, val = gold_match.group(1).strip(), int(gold_match.group(2))
            if target in game_state["party_gold"]:
                game_state["party_gold"][target] += val

        # 5. Items
        item_match = re.search(r"\[ITEM:\s*(.*?),\s*(.*?)\]", response)
        if item_match:
            target, item = item_match.group(1).strip(), item_match.group(2).strip()
            if target in game_state["party_inventory"]:
                game_state["party_inventory"][target].append(item)

        # Return clean text (remove tags)
        return re.sub(r"\[.*?\]", "", response).strip()
    
    except Exception as e:
        return f"⚠️ DM Error: {e}"

# --- 4. SIDEBAR: CHARACTER SHEET ---
with st.sidebar:
    st.title("🧙‍♂️ Character Sheet")
    if "my_name" not in st.session_state: 
        st.session_state.my_name = ""
    
    name = st.text_input("Enter Name to Join:", value=st.session_state.my_name)
    
    if name:
        st.session_state.my_name = name
        # Initialize player if new
        if name not in game_state["party_hp"]:
            game_state["party_hp"][name] = 10
            game_state["party_gold"][name] = 0
            game_state["party_inventory"][name] = ["Rusty Dagger"]
            st.rerun()

    if st.session_state.my_name in game_state["party_hp"]:
        my_hp = game_state["party_hp"][st.session_state.my_name]
        my_gold = game_state["party_gold"][st.session_state.my_name]
        
        st.write(f"❤️ **HP:** {my_hp}/10")
        st.write(f"💰 **Gold:** {my_gold}")
        
        if st.button("🧪 Buy Potion (20g)"):
            if my_gold >= 20:
                game_state["party_gold"][st.session_state.my_name] -= 20
                game_state["party_hp"][st.session_state.my_name] = min(10, my_hp + 5)
                st.rerun()
            else:
                st.error("Not enough gold!")
                
        st.write("🎒 **Inventory**")
        for item in game_state["party_inventory"].get(st.session_state.my_name, []):
            st.caption(f"• {item}")
    
    st.divider()
    if st.button("🔥 Reset World (Admin)"):
        # Reset Logic
        game_state["monster_active"] = False
        game_state["monster_name"] = None
        game_state["monster_hp"] = 0
        game_state["history"] = [{"role": "assistant", "name": "DM", "content": "The world resets... A fresh breeze blows."}]
        game_state["party_hp"] = {} 
        game_state["party_gold"] = {}
        st.rerun()

# --- 5. MAIN HUD ---
st.title("⚔️ AI Multiplayer RPG")

h1, h2 = st.columns([2, 1])
with h1:
    # Monster Display
    if game_state["monster_active"]:
        st.error(f"**👹 {game_state['monster_name']}** is attacking!")
        if game_state["max_monster_hp"] > 0:
            pct = max(0.0, min(1.0, float(game_state["monster_hp"]) / float(game_state["max_monster_hp"])))
            st.progress(pct, text=f"HP: {game_state['monster_hp']}/{game_state['max_monster_hp']}")
        
        if game_state["monster_hp"] <= 0:
            st.success(f"The {game_state['monster_name']} has been slain!")
            if st.button("💀 Loot & Despawn Body"): 
                game_state["monster_active"] = False
                game_state["monster_name"] = None
                game_state["history"].append({"role": "user", "name": "SYSTEM", "content": "We search the body."})
                game_state["history"].append({"role": "assistant", "content": ask_dm()})
                st.rerun()
    else:
        st.info("🌲 You are exploring safely... for now.")

with h2:
    # Party Status
    st.subheader("🛡️ Party")
    for p_name, p_hp in game_state["party_hp"].items():
        st.progress(p_hp/10.0, text=f"{p_name}: {p_hp} HP")

st.divider()

# --- 6. CHAT & ACTIONS ---
chat_container = st.container(height=400)
with chat_container:
    for msg in game_state["history"]:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar="🧙‍♂️"):
                st.write(msg["content"])
        else:
            with st.chat_message("user", avatar="👤"):
                sender = msg.get("name", "Unknown")
                st.write(f"**{sender}:** {msg['content']}")

# Action Bar
c_dice, c_input = st.columns([1, 4])

with c_dice:
    # Logic: Only allow rolling if you are logged in
    can_roll = st.session_state.my_name != ""
    if st.button("🎲 ATK / SKILL", use_container_width=True, type="primary", disabled=not can_roll):
        roll = random.randint(1, 20)
        user = st.session_state.my_name
        
        result_text = f"rolled a {roll}!"
        
        # Simple Logic to Auto-Hit Monster (Optional)
        if game_state["monster_active"]:
            if roll >= 12:
                dmg = random.randint(3, 8)
                game_state["monster_hp"] = max(0, game_state["monster_hp"] - dmg)
                result_text += f" (Hit for {dmg} dmg)"
            else:
                result_text += " (Miss)"
        
        game_state["history"].append({"role": "user", "name": user, "content": f"🎲 *{result_text}*"})
        
        # Trigger DM response every roll? Optional. 
        # Sometimes it's better to let players roll a few times then talk.
        # Uncomment below to make DM react to every roll:
        # game_state["history"].append({"role": "assistant", "content": ask_dm()})
        
        st.rerun()

with c_input:
    user_action = st.chat_input(placeholder="What do you do?", disabled=st.session_state.my_name == "")
    if user_action:
        game_state["history"].append({"role": "user", "name": st.session_state.my_name, "content": user_action})
        
        # Add a spinner while AI thinks
        with st.spinner(" The DM is thinking..."):
            dm_response = ask_dm()
            game_state["history"].append({"role": "assistant", "content": dm_response})
        
        st.rerun()
