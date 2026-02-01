import streamlit as st
from groq import Groq
import time
import random
import re
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & REFRESH ---
st.set_page_config(page_title="Rudy's RPG: Gothic Edition", page_icon="⚔️", layout="wide")
# Auto-refresh allows multiplayer sync by polling the shared state every 5 seconds
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED MULTIPLAYER STATE ---
@st.cache_resource
def get_game_state():
    """Initializes the global game state shared across all users."""
    return {
        "history": [{
            "role": "assistant", 
            "name": "DM", 
            "content": "🛡️ **The Saga Begins.** The sky bleeds a bruised purple over the Jagged Peaks. You stand before the *Shattered Gate*, where the air smells of ancient ozone and rusted iron. A low hum vibrates through your boots. The path forward is draped in shadows. *What do you do?*"
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
            "You are a master Bard and Dungeon Master. Your style is gothic, atmospheric, and witty. "
            "Use sensory details (smells, sounds, lighting) in every response. "
            "Narrate dice rolls and actions with high drama. "
            "To spawn a monster: '[MONSTER: Name, HP: 50]'. "
            "To change health: '[HP_CHANGE: Name, -2]' or '[MONSTER_HP: -10]'. "
            "To give/take gold: '[GOLD: Name, +20]'. "
            "To give items: '[ITEM: Name, ItemName]'. "
            "Keep responses under 80 words. Be descriptive but punchy."
        )
    }

game_state = get_game_state()

# --- 3. HELPER: AI CALL & TAG PARSER ---
def ask_dm():
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        
        # Contextual status for the AI
        m_status = f"Monster: {game_state['monster_name']} ({game_state['monster_hp']} HP)" if game_state["monster_active"] else "No active monster."
        low_hp_warning = " (Tension is high: a player is badly wounded!)" if any(v < 4 for v in game_state["party_hp"].values()) else ""
        status = f" [System Status: {m_status}, Party HP: {game_state['party_hp']}, Gold: {game_state['party_gold']}.{low_hp_warning}]"
        
        messages = [{"role": "system", "content": game_state["system_prompt"] + status}]
        for m in game_state["history"][-12:]:
            messages.append({"role": m["role"], "content": m["content"]})
        
        completion = client.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile")
        response = completion.choices[0].message.content
        
        # --- PARSE ENGINE TAGS ---
        # Monster Spawning
        if not game_state["monster_active"]:
            m_match = re.search(r"\[MONSTER:\s*(.*?),\s*HP:\s*(\d+)\]", response)
            if m_match:
                game_state["monster_name"], hp_v = m_match.group(1), int(m_match.group(2))
                game_state["monster_hp"] = game_state["max_monster_hp"] = hp_v
                game_state["monster_active"] = True
                game_state["battle_log"].insert(0, f"⚠️ {game_state['monster_name']} emerged from the gloom!")

        # Monster Damage
        mh_match = re.search(r"\[MONSTER_HP:\s*([+-]?\d+)\]", response)
        if mh_match and game_state["monster_active"]:
            game_state["monster_hp"] = max(0, game_state["monster_hp"] + int(mh_match.group(1)))

        # Player HP
        ph_match = re.search(r"\[HP_CHANGE:\s*(.*?),\s*([+-]?\d+)\]", response)
        if ph_match:
            target_raw, val = ph_match.group(1).strip(), int(ph_match.group(2))
            for actual_name in game_state["party_hp"].keys():
                if target_raw.lower() == actual_name.lower():
                    game_state["party_hp"][actual_name] = max(0, min(10, game_state["party_hp"][actual_name] + val))

        # Gold Tracking
        gold_match = re.search(r"\[GOLD:\s*(.*?),\s*([+-]?\d+)\]", response)
        if gold_match:
            target_raw, val = gold_match.group(1).strip(), int(gold_match.group(2))
            for actual_name in game_state["party_gold"].keys():
                if target_raw.lower() == actual_name.lower():
                    game_state["party_gold"][actual_name] = max(0, game_state["party_gold"][actual_name] + val)
                    game_state["battle_log"].insert(0, f"💰 {actual_name} {'gained' if val > 0 else 'lost'} {abs(val)} gold!")

        # Inventory Items
        item_match = re.search(r"\[ITEM:\s*(.*?),\s*(.*?)\]", response)
        if item_match:
            target_raw, item = item_match.group(1).strip(), item_match.group(2).strip()
            for actual_name in game_state["party_inventory"].keys():
                if target_raw.lower() == actual_name.lower():
                    game_state["party_inventory"][actual_name].append(item)
                    game_state["battle_log"].insert(0, f"🎒 {actual_name} found: {item}")

        # Clean tags from the final text
        return re.sub(r"\[.*?\]", "", response).strip()
    except Exception as e:
        return f"⚠️ DM Error: {e}"

# --- 4. SIDEBAR: CHARACTER SHEET ---
with st.sidebar:
    st.title("🧙‍♂️ Character Sheet")
    if "my_name" not in st.session_state: st.session_state.my_name = ""
    name_input = st.text_input("Enter your Hero's Name:", value=st.session_state.my_name)
    
    if name_input and name_input != st.session_state.my_name:
        st.session_state.my_name = name_input
        if name_input not in game_state["party_hp"]:
            game_state["party_hp"][name_input] = 10
            game_state["party_gold"][name_input] = 5
            game_state["party_inventory"][name_input] = []
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

# --- 5. MAIN HUD: MONSTER & PARTY ---
st.title("⚔️ Rudy's Gothic RPG")
h1, h2 = st.columns(2)

with h1:
    if game_state["monster_active"]:
        if game_state["monster_hp"] > 0:
            st.subheader(f"👹 {game_state['monster_name']}")
            pct = max(0.0, min(1.0, float(game_state["monster_hp"]) / float(game_state["max_monster_hp"])))
            st.progress(pct, text=f"HP: {game_state['monster_hp']}/{game_state['max_monster_hp']}")
        else:
            st.success(f"✨ {game_state['monster_name']} Slain!")
            if st.button("Collect Loot & Move On"): 
                game_state["history"].append({"role": "user", "name": "SYSTEM", "content": f"{st.session_state.my_name} loots the corpse."})
                game_state["monster_active"] = False
                game_state["history"].append({"role": "assistant", "name": "DM", "content": ask_dm()})
                st.rerun()
    else:
        st.info("🌲 The trail ahead is quiet... for now.")

with h2:
    st.subheader("🛡️ The Party")
    for p_name, p_hp in game_state["party_hp"].items():
        st.write(f"**{p_name}**: {p_hp}/10 HP | {game_state['party_gold'].get(p_name, 0)} Gold")

st.divider()

# --- 6. CHAT & ACTIONS ---
chat_c = st.container(height=350)
with chat_c:
    for msg in game_state["history"]:
        avatar = "🧙‍♂️" if msg["role"] == "assistant" else "⚔️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.write(f"**{msg.get('name', 'DM')}**: {msg['content']}")

if not st.session_state.my_name:
    st.warning("👈 Enter your name in the sidebar to join the party!")
else:
    c_dice, c_input = st.columns([1, 4])
    with c_dice:
        if st.button("🎲 ROLL D20", use_container_width=True, type="primary"):
            roll = random.randint(1, 20)
            dmg_desc = ""
            if game_state["monster_active"] and roll >= 10:
                dmg = 5 if roll < 20 else 10 # Critical Hit
                game_state["monster_hp"] = max(0, game_state["monster_hp"] - dmg)
                dmg_desc = f" dealing {dmg} damage!"
            
            game_state["history"].append({"role": "user", "name": "SYSTEM", "content": f"🎲 {st.session_state.my_name} rolled a {roll}{dmg_desc}."})
            game_state["history"].append({"role": "assistant", "name": "DM", "content": ask_dm()})
            st.rerun()

    with c_input:
        user_action = st.chat_input("Speak or act...")
        if user_action:
            game_state["history"].append({"role": "user", "name": st.session_state.my_name, "content": user_action})
            with st.spinner("The DM is weaving the tale..."):
                response = ask_dm()
            game_state["history"].append({"role": "assistant", "name": "DM", "content": response})
            st.rerun()
