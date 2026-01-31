import streamlit as st
from groq import Groq
import time
import random
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. PAGE CONFIG & SYNC ---
st.set_page_config(page_title="Free AI RPG", page_icon="⚔️", layout="wide")
st_autorefresh(interval=5000, key="rpg_sync")

# --- 2. SHARED MULTIPLAYER STATE ---
@st.cache_resource
def get_shared_game_state():
    return {
        "history": [{"role": "assistant", "content": "The tavern is quiet until the door bangs open. Welcome, travelers. What is your first move?"}],
        "system_prompt": "You are a witty, dark fantasy Dungeon Master. React to player actions and dice rolls. Keep it under 80 words."
    }

game_state = get_shared_game_state()

# --- 3. SIDEBAR: PLAYER & TOOLS ---
with st.sidebar:
    st.title("🛡️ Party Menu")
    
    # GROQ API KEY INPUT
    groq_api_key = st.text_input("Groq API Key (Free)", type="password", help="Get it at console.groq.com")
    
    st.divider()
    
    if "player_name" not in st.session_state:
        st.session_state.player_name = "Traveler"
    st.session_state.player_name = st.text_input("Character Name", value=st.session_state.player_name)
    char_class = st.selectbox("Class", ["Warrior", "Mage", "Rogue", "Paladin", "Bard"])

    st.divider()
    
    # DICE ROLLER
    st.subheader("🎲 Action Roll")
    if st.button("Roll D20"):
        roll = random.randint(1, 20)
        game_state["history"].append({
            "role": "user", 
            "name": "SYSTEM", 
            "content": f"🎲 {st.session_state.player_name} rolled a {roll}!"
        })
        st.rerun()

    st.divider()
    
    if st.button("🔥 Reset Adventure"):
        game_state["history"] = [{"role": "assistant", "content": "The world resets. A new story begins..."}]
        st.rerun()

    st.caption(f"Last sync: {datetime.now().strftime('%H:%M:%S')}")

# --- 4. THE GAME INTERFACE ---
st.title("⚔️ The Cursed Caverns (Free AI Edition)")

for msg in game_state["history"]:
    role = msg["role"]
    avatar = "🧙‍♂️" if role == "assistant" else "👤"
    
    with st.chat_message(role, avatar=avatar):
        if "name" in msg:
            st.write(f"**{msg['name']}**: {msg['content']}")
        else:
            st.write(msg["content"])

# --- 5. INPUT LOGIC ---
user_input = st.chat_input("What do you do?")

if user_input:
    if not groq_api_key:
        st.error("Please enter your free Groq API Key in the sidebar!")
    else:
        # Save player action to shared history
        game_state["history"].append({
            "role": "user", 
            "name": st.session_state.player_name, 
            "content": f"({char_class}) {user_input}"
        })
        
        # Initialize Groq Client
        client = Groq(api_key=groq_api_key)
        
        try:
            with st.spinner("DM is thinking..."):
                # Build context (System + last 10 messages)
                messages = [{"role": "system", "content": game_state["system_prompt"]}]
                for m in game_state["history"][-10:]:
                    messages.append({"role": m["role"], "content": m["content"]})
                
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model="llama-3.3-70b-versatile", # High quality, fast, and free
                )
                
                dm_response = chat_completion.choices[0].message.content
                game_state["history"].append({"role": "assistant", "content": dm_response})
            
            st.rerun()
            
        except Exception as e:
            st.error(f"Groq Error: {str(e)}")

# --- 6. FOOTER ---
st.divider()
st.caption("Using Llama-3 (Groq) • Multi-player enabled • Data resets on server restart")
    if "player_name" not in st.session_state:
        st.session_state.player_name = "New Traveler"
    
    st.session_state.player_name = st.text_input("Character Name", value=st.session_state.player_name)
    char_class = st.selectbox("Class", ["Warrior", "Mage", "Rogue", "Paladin", "Bard"])
    
    st.divider()
    
    # RESET BUTTON: Clears the shared history for everyone
    if st.button("🔥 Reset Adventure for All"):
        game_state["history"] = [
            {"role": "assistant", "content": "The world has been unmade and reborn. A new journey begins..."}
        ]
        st.rerun()
    
    st.caption(f"Syncing with Party... {datetime.now().strftime('%H:%M:%S')}")

# --- 4. THE GAME INTERFACE ---
st.title("⚔️ AI Dungeon Master: Multi-Player")

# Display Chat History
for msg in game_state["history"]:
    if msg["role"] == "assistant":
        with st.chat_message("assistant", avatar="🧙‍♂️"):
            st.write(msg["content"])
    else:
        # Extract player name from the stored message
        p_name = msg.get("name", "Unknown")
        # Use a different avatar if it's the current player vs someone else
        is_me = p_name == st.session_state.player_name
        with st.chat_message("user", avatar="🛡️" if is_me else "👤"):
            st.write(f"**{p_name}**: {msg['content']}")

# --- 5. PLAYER ACTION LOGIC ---
user_input = st.chat_input("What is your move?")

if user_input:
    if not api_key:
        st.error("Please enter an OpenAI API Key in the sidebar to act!")
    else:
        # A. Add Player's move to shared history
        player_msg = {
            "role": "user", 
            "name": st.session_state.player_name, 
            "content": f"({char_class}) {user_input}"
        }
        game_state["history"].append(player_msg)
        
        # B. Call the AI DM
        client = openai.OpenAI(api_key=api_key)
        
        # Build the context for the AI (System Prompt + History)
        messages_for_ai = [{"role": "system", "content": game_state["system_prompt"]}]
        # Add the last 15 messages for context (to prevent token overflow)
        for m in game_state["history"][-15:]:
            messages_for_ai.append({"role": m["role"], "content": m["content"]})
        
        try:
            with st.spinner("The DM is thinking..."):
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages_for_ai
                )
            
            dm_reply = response.choices[0].message.content
            
            # C. Add DM's reply to shared history
            game_state["history"].append({"role": "assistant", "content": dm_reply})
            
            # Refresh for everyone
            st.rerun()
            
        except Exception as e:
            st.error(f"The DM had a stroke: {e}")

# --- 6. FOOTER INFO ---
st.divider()
st.caption("Shared session active. Tell your friends to join using this URL.")
