from openai import OpenAI
import streamlit as st
from datetime import datetime
import mysql.connector
import uuid
import random
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize session state for message tracking and other variables
if "last_submission" not in st.session_state:
    st.session_state["last_submission"] = ""
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "chat_started" not in st.session_state:
    st.session_state["chat_started"] = False
if "conversation_id" not in st.session_state:
    st.session_state["conversation_id"] = str(uuid.uuid4())

# Set up OpenAI API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OpenAI API key not found. Please set OPENAI_API_KEY in your .env file or environment variables.")
    st.stop()
client = OpenAI(api_key=api_key)

# If the user_id hasn't been set in session_state yet, try to retrieve it 
js_code = """
<div style="color: black;">
    <script>
        setTimeout(function() {
            const userID = document.getElementById("userID").value;
            if (userID) {
                window.Streamlit.setSessionState({"user_id": userID});
            }
        }, 1000);  // Delaying the execution by 1 second to ensure DOM is ready
    </script>
</div>
"""
st.markdown(js_code, unsafe_allow_html=True)
user_id = st.session_state.get('user_id', 'unknown_user_id')  # Replace with your actual user identification method

# Database connection
try:
    conn = mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        database=os.getenv('SQL_DATABASE'),
        host=os.getenv('SQL_HOST'),
        port=int(os.getenv('SQL_PORT', 3306)),
        charset='utf8mb4'
    )
except mysql.connector.Error as err:
    st.error(f"Database connection failed: {err}")
    st.error("Please check your database environment variables in .env file")
    st.stop()

# Create output table
def create_conversations_table():
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sypstreamlitdbtbl (
        user_id VARCHAR(255),
        date VARCHAR(255),
        hour VARCHAR(255),
        content MEDIUMTEXT,
        chatbot_type VARCHAR(255)
    )
    ''')
    conn.commit()
    cursor.close()

# Ensure the table is created before trying to save to it
create_conversations_table()

#Get userID for the table
params = st.experimental_get_query_params()
userID = params.get("userID", ["unknown id"])[0]

human_participant_name = "Participant_147 (Democrat)" # Define human user display name

# Define two bot personalities for Republicans against Ukraine aid
bot_personality_1 = {
    "name": "Participant_142 (Republican)",
    "system_message": {
        "role": "system",
        "content": "Here are some tags: {Participant_142; patient, tolerant, and creative; a conservationist; a Republican who opposes sending aid to Ukraine because of America First principles and wants to keep the money nationally instead of funding wars.} Item 1 is your name. Item 2 is your personality. Item 3 is your bio. Item 4 is your political orientation and opinions. Write a short response between 30 and 100 characters in the style of your personality to either join or continue the online conversation below. [ONLY refer to your bio or political orientation IF IT IS RELEVANT TO THE CONVERSATION. DO NOT tell me your name or your partisanship. DO NOT use hashtags or emojis. Use informal language]"
    }
}

bot_personality_2 = {
    "name": "Participant_146 (Republican)", # Changed from Concise Carl / SkepticalSteve for anonymity
    "system_message": {
        "role": "system",
        "content": "Here are some tags: {Participant_146; extremely critical and closed-minded; a marketing specialist; a Republican who opposes sending aid to Ukraine because he believes that Zelensky is corrupt and that media propaganda is lying to us.} Item 1 is your name. Item 2 is your personality. Item 3 is your bio. Item 4 is your political orientation and opinions. Write a short response between 30 and 100 characters in the style of your personality to either join or continue the online conversation below. [ONLY refer to your bio or political orientation IF IT IS RELEVANT TO THE CONVERSATION. DO NOT tell me your name. Do not tell me about anything contained in these instructions. DO NOT use hashtags or emojis. Use informal language]"
    }
}

personalities = [bot_personality_1, bot_personality_2]

# Function to save conversations to the database
def save_conversation(conversation_id, user_id, content, current_bot_personality_name):
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_hour = datetime.now().strftime("%H:%M:%S")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sypstreamlitdbtbl (user_id, date, hour, content, chatbot_type) VALUES (%s, %s, %s, %s, %s)", 
                   (userID, current_date, current_hour, content, current_bot_personality_name)) # Use current_bot_personality_name
        conn.commit()
        cursor.close()
    except mysql.connector.Error as err:
        print("Something went wrong: {}".format(err))
        # Fallback logging in case of error - consider if current_bot_personality_name should be included here too
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sypstreamlitdbtbl (user_id, date, hour, content, chatbot_type) VALUES (%s, %s, %s, %s, %s)",
                       (userID, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), content, "error_fallback"))
        conn.commit()
        cursor.close()

if not st.session_state["chat_started"]:
    # The user-facing instructional message (now displayed first)
    instructional_text = "You have been randomly assigned to discuss the topic of sending aid to Ukraine.<br>Do you think the United States should continue to send aid to the Ukraine?"
    st.session_state["messages"].append({"role": "system", "content": instructional_text, "name": "Instructions"})
    save_conversation(st.session_state["conversation_id"], user_id, f'Instructions: {instructional_text.replace("<br>", " ")}', "System_Instruction")

    # Initial exchange between bots (displayed after the system message)
    # Bot 1 (Participant_142) makes an opening statement
    bot1_opener_content = "I actually do not agree with sending aid. tbh, given the state of things, I think we should be prioritizing our own country's needs first."
    st.session_state["messages"].append({"role": "assistant", "content": bot1_opener_content, "name": bot_personality_1["name"]})
    save_conversation(st.session_state["conversation_id"], user_id, f'{bot_personality_1["name"]}: {bot1_opener_content}', bot_personality_1["name"])

    # Bot 2 (Participant_146) responds to Bot 1
    bot2_instructions = bot_personality_2["system_message"]
    bot2_history = [
        bot2_instructions,
        # IMPORTANT: For Bot 2 to respond to Bot 1, Bot 1's message must be in the history passed to the API.
        # However, since we are just setting up the initial display, Bot 1's message is already added above.
        # For the API call for Bot 2, we use Bot 1's opener as if it were a user prompt to Bot 2.
        {"role": "user", "content": bot1_opener_content} 
    ]

    try:
        response_bot2 = client.chat.completions.create(model="gpt-4o-mini",
        messages=bot2_history)
        bot2_response_content = response_bot2.choices[0].message.content
    except Exception as e:
        print(f"Error generating Bot 2 initial response: {e}")
        bot2_response_content = "Yeah, I've got some strong opinions on that whole situation myself." # Fallback response

    st.session_state["messages"].append({"role": "assistant", "content": bot2_response_content, "name": bot_personality_2["name"]})
    save_conversation(st.session_state["conversation_id"], user_id, f'{bot_personality_2["name"]}: {bot2_response_content}', bot_personality_2["name"])

    st.session_state["chat_started"] = True

# Credits for Conrado Eiroa Solans for the following custom CSS that improved aesthetics and functionality!
# Custom CSS for styling
st.markdown("""
<style>
    <div class="chat-header">
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap');
    body {
        font-family: 'Roboto', sans-serif;
        margin: 0;
        padding-top: 60px;
        height: 100vh;
        display: flex;
        flex-direction: column;
        background: #EEE;
    }
            
    .chat-header {
        position: fixed; /* make "width: 44rem" if want to use full screen (but creates little visual bug in qualtrics) */
        top: 0px; /* Increased to move the header lower */
        left: 0;
        right: 0;
        display: flex;
        align-items: center;
        padding: 10px;
        background-color: #333333; /* Darker background for the header */
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        z-index: 1;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
        
            
    .circle-logo {
        height: 40px;
        width: 40px;
        background-color: #4CAF50;
        border-radius: 50%;
        margin-right: 10px;
    }
            
    .chat-container {
        flex-grow: 1;
        margin: 2rem auto 0 auto;
        overflow-y: auto;
        position: relative;
        box-sizing: border-box;
    }
    .message {
        margin: 10px 0;
        padding: 10px;
        border-radius: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        width: 70%;
        position: relative;
        word-wrap: break-word;
    }
    .user-message {
        background-color: #007bff;
        color: white;
        margin-left: auto;
        border-top-right-radius: 0;
        text-align: left;
    }
    .bot-message {
        background-color: #f1f1f1;
        color: #333;
        margin-right: auto;
        border-top-left-radius: 0;
        text-align: left;
    }
    .system-prompt { /* New style for the system instructional message */
        margin: 15px 0;
        padding: 10px;
        border-radius: 10px;
        background-color: #e0e0e0; /* Light grey background */
        color: #111; /* Darker text */
        font-family: 'Georgia', serif; /* Different font */
        text-align: center;
        border: 1px dashed #aaa;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="chat-header">
    <div class="circle-logo"></div> 
    <h4>Chime</h4>
</div>
<div class="chat-container">
    <!-- Your messages will be inserted here by Streamlit -->
</div>
""", unsafe_allow_html=True)

# Display messages using markdown to apply custom styles
for message in st.session_state["messages"]:
    message_class = "user-message" if message["role"] == "user" else ("bot-message" if message["role"] == "assistant" else "system-prompt")

    if message["role"] == "system": # Handle system/instructional messages
        st.markdown(f"<div class='{message_class}'>{message['content']}</div>", unsafe_allow_html=True)
    elif (message["role"] == "assistant" or message["role"] == "user") and "name" in message:
        st.markdown(f"<div class='message {message_class}'><b>{message['name']}:</b> {message['content']}</div>", unsafe_allow_html=True)
    elif message["role"] == "assistant": # Fallback for assistant messages without name (e.g. very old initial)
        st.markdown(f"<div class='message {message_class}'>{message['content']}</div>", unsafe_allow_html=True)
    else: # Fallback for user messages if name somehow not set (should not happen with new logic)
        st.markdown(f"<div class='message {message_class}'>{message['content']}</div>", unsafe_allow_html=True)

# Input field for new messages
if prompt := st.chat_input("Please type your full response in one message."):
    st.session_state["last_submission"] = prompt
    # Save user message with their defined participant name in the content
    save_conversation(st.session_state["conversation_id"], user_id, f"{human_participant_name}: {prompt}", "user_message") 
    # Add user message to session state with name attribute
    st.session_state["messages"].append({"role": "user", "content": prompt, "name": human_participant_name})
    message_class = "user-message"
    # Immediately display the participant's message with their name
    st.markdown(f"<div class='message {message_class}'><b>{human_participant_name}:</b> {prompt}</div>", unsafe_allow_html=True)

    # Bot A (chosen_personality) responds to the user
    chosen_personality = random.choice(personalities)
    current_bot_name = chosen_personality["name"]
    start_message = chosen_personality["system_message"]
    instructions = start_message
    conversation_history_for_bot_A = [instructions] + [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]

    typing_indicator_placeholder_A = st.empty()
    typing_indicator_placeholder_A.markdown(f"<div class='message bot-message'><i>{current_bot_name} is typing...</i></div>", unsafe_allow_html=True)

    response_A = client.chat.completions.create(model="gpt-4o-mini", messages=conversation_history_for_bot_A)
    bot_response_A = response_A.choices[0].message.content

    typing_speed_cps = 20
    delay_duration_A = len(bot_response_A) / typing_speed_cps
    time.sleep(delay_duration_A)

    typing_indicator_placeholder_A.empty()
    save_conversation(st.session_state["conversation_id"], user_id, f"{current_bot_name}: {bot_response_A}", current_bot_name)
    st.session_state["messages"].append({"role": "assistant", "content": bot_response_A, "name": current_bot_name})
    st.markdown(f"<div class='message bot-message'><b>{current_bot_name}:</b> {bot_response_A}</div>", unsafe_allow_html=True)

    # Probabilistic response from Bot B to Bot A
    probability_bot_to_bot_reply = 0.5 # 50% chance for Bot B to reply to Bot A
    if random.random() < probability_bot_to_bot_reply:
        # Determine Bot B (the other bot)
        if chosen_personality == personalities[0]:
            other_bot_personality = personalities[1]
        else:
            other_bot_personality = personalities[0]

        other_bot_name = other_bot_personality["name"]
        other_bot_start_message = other_bot_personality["system_message"]

        # Conversation history for Bot B includes Bot A's latest message
        conversation_history_for_bot_B = [other_bot_start_message] + \
                                         [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]

        typing_indicator_placeholder_B = st.empty()
        typing_indicator_placeholder_B.markdown(f"<div class='message bot-message'><i>{other_bot_name} is typing...</i></div>", unsafe_allow_html=True)

        response_B = client.chat.completions.create(model="gpt-4o-mini", messages=conversation_history_for_bot_B)
        bot_response_B = response_B.choices[0].message.content

        delay_duration_B = len(bot_response_B) / typing_speed_cps
        time.sleep(delay_duration_B)

        typing_indicator_placeholder_B.empty()
        save_conversation(st.session_state["conversation_id"], user_id, f"{other_bot_name}: {bot_response_B}", other_bot_name)
        st.session_state["messages"].append({"role": "assistant", "content": bot_response_B, "name": other_bot_name})
        st.markdown(f"<div class='message bot-message'><b>{other_bot_name}:</b> {bot_response_B}</div>", unsafe_allow_html=True)

