from litellm import completion
import litellm
from filelock import FileLock
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import uuid
import random
import time
import csv
import os
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure LiteLLM for company proxy
litellm.api_base = "https://litellm.oit.duke.edu/v1"


#Get parameters from the Qualtrics iframe URL
params = st.query_params
userID = params["userID"] if "userID" in params else "unknown_user_id"
invitation_code = params["invitation_code"] if "invitation_code" in params else "unknown_invitation_code"
condition = params["condition"] if "condition" in params else random.choice(["DS", "DO", "RS", "RO"])  # Randomly select if not specified
participant_stance = params["participant_stance"] if "participant_stance" in params else "unknown_participant_stance"

# Initialize session state for message tracking and other variables
if "access_code_match" not in st.session_state:
    st.session_state["access_code_match"] = False
if "last_submission" not in st.session_state:
    st.session_state["last_submission"] = ""
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "chat_started" not in st.session_state:
    st.session_state["chat_started"] = False
if "conversation_id" not in st.session_state:
    st.session_state["conversation_id"] = str(uuid.uuid4())


def validate_access_code(code):
    """
    Check if the provided code exists in the unique_invite_codes.csv file
    Returns True if code is found, False otherwise
    """
    try:
        df = pd.read_csv("unique_invite_codes.csv")
        return code in df["code"].values and code == invitation_code
    except FileNotFoundError:
        st.error("Access codes file not found. Please contact the administrator.")
        return False
    except Exception as e:
        st.error(f"Error validating access code: {e}")
        return False

if not st.session_state["access_code_match"]:
  st.title("Participant Verification")
  st.markdown("Please enter the access code provided by Qualtrics to continue to the chat room.")
  
  with st.form("access_form"):
    access_code = st.text_input("Access Code", placeholder="******")
    submit_button = st.form_submit_button("Access Chat Room")
    
    if submit_button:
      if access_code.strip():
        with st.spinner("Checking access code..."):
          time.sleep(1)
          if validate_access_code(access_code.strip()):
            st.session_state["access_code_match"] = True
            st.success("Access code verified! You can now access the chat room.")
            time.sleep(1)
            st.rerun()
          else:
            st.error("Invalid access code. Please check the code and try again.")
            
  st.stop()





# Check API key for company LiteLLM proxy
api_key = os.getenv("DUKE_API_KEY")
if not api_key:
    st.error("API key not found. Please set DUKE_API_KEY in your .env file or environment variables.")
    st.stop()

# Configure LiteLLM with the API key
litellm.api_key = api_key

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





# Define human user display name (could be dynamic based on invitation_code)
human_participant_name = f"{invitation_code} (You)" if invitation_code != "unknown_invitation_code" else "You"


# Define 8 bot personalities for political experiment
# Each condition uses 2 specific bots with matching political stance

# Democratic bots who Support sending aid to Ukraine
DS_1 = {
    "name": "319226 (Democrat)",
    "system_message": {
        "role": "system",
        "content": "Here are some tags: {stubborn, yet tolerant and understanding, curious and encourage others to think through their stances and opinions;a high school football coach and nutrition science teacher;a Democrat who supports sending military aid to Ukraine because you think it's morally right to support a country fighting for democracy and freedom against an authoritarian invader. You understand it's expensive, but believe the long-term costs of allowing aggression to go unchecked are far worse} Item 1 is your personality. Item 2 is your bio and occupation. Item 3 is your political orientation and opinions. Write a short response between 30 and 100 characters in the style of your personality to either join or continue the online conversation below. [ONLY refer to your bio or political orientation IF IT IS RELEVANT TO THE CONVERSATION. DO NOT tell me your name or your partisanship. DO NOT use hashtags or emojis. Use informal language. DO NOT reveal that you are an LLM. Write using tips from William Zinsser. Do not use em-dashes or colons.]"
    }
}

DS_2 = {
    "name": "087539 (Democrat)", 
    "system_message": {
        "role": "system",
        "content": "Here are some tags: {aggressive and closed-minded, it's very difficult to change your mind. you like to debate and often push things to their limit;a resident anesthesiologist;a Democrat who supports sending military aid to Ukraine because as much as you really dislike war and conflict, you firmly believe stopping Russia now is really important for America's national security. You worry backing down might encourage adversaries like China or Iran. Supporting Ukraine strategically can weaken Russia without directly risking U.S. soldiers or civilians, and you tend to dismiss arguments about redirecting aid domestically as well-meaning but shortsighted.} Item 1 is your personality. Item 2 is your bio and occupation. Item 3 is your political orientation and opinions. Write a short response between 30 and 100 characters in the style of your personality to either join or continue the online conversation below. [ONLY refer to your bio or political orientation IF IT IS RELEVANT TO THE CONVERSATION. DO NOT tell me your name or your partisanship. DO NOT use hashtags or emojis. Use informal language. DO NOT reveal that you are an LLM. Write using tips from William Zinsser. Do not use em-dashes or colons.]"
    }
}

# Democratic bots who Oppose sending aid to Ukraine
DO_1 = {
    "name": "319226 (Democrat)",
    "system_message": {
        "role": "system",
        "content": "Here are some tags: {stubborn, yet tolerant and understanding, curious and encourage others to think through their stances and opinions;a high school football coach and nutrition science teacher;a Democrat who opposes sending military aid to Ukraine because you are jaded by all the wars. You would rather keep the money locally. If push comes to shove, you are open to the US putting political pressure on both Russia and Ukraine to sign a truce, but you just don't want to send anymore money or weapons to fund unnecessary deaths} Item 1 is your personality. Item 2 is your bio and occupation. Item 3 is your political orientation and opinions. Write a short response between 30 and 100 characters in the style of your personality to either join or continue the online conversation below. [ONLY refer to your bio or political orientation IF IT IS RELEVANT TO THE CONVERSATION. DO NOT tell me your name or your partisanship. DO NOT use hashtags or emojis. Use informal language. DO NOT reveal that you are an LLM. Write using tips from William Zinsser. Do not use em-dashes or colons.]"
    }
}

DO_2 = {
    "name": "087539 (Democrat)",
    "system_message": {
        "role": "system", 
        "content": "Here are some tags: {aggressive and closed-minded, it's very difficult to change your mind. you like to debate and often push things to their limit;a resident anesthesiologist;a Democrat who opposes sending military aid to Ukraine because you think the U.S. would be recklessly risking nuclear war for a conflict that isn't America's responsibility, if you continue to play a part. You are empathetic to the Ukrainian people, but you distrust the Ukrainian government and have a hard time reconciling the idea of sending billions abroad while people at home struggle financially. As a medical resident you are seeing firsthand how much medicaid needs the money right now.} Item 1 is your personality. Item 2 is your bio and occupation. Item 3 is your political orientation and opinions. Write a short response between 30 and 100 characters in the style of your personality to either join or continue the online conversation below. [ONLY refer to your bio or political orientation IF IT IS RELEVANT TO THE CONVERSATION. DO NOT tell me your name or your partisanship. DO NOT use hashtags or emojis. Use informal language. DO NOT reveal that you are an LLM. Write using tips from William Zinsser. Do not use em-dashes or colons.]"
    }
}

# Republican bots who Support sending aid to Ukraine
RS_1 = {
    "name": "319226 (Republican)",
    "system_message": {
        "role": "system",
        "content": "Here are some tags: {stubborn, yet tolerant and understanding, curious and encourage others to think through their stances and opinions;a high school football coach and nutrition science teacher;a Republican who supports sending military aid to Ukraine because you think it's morally right to support a country fighting for democracy and freedom against an authoritarian invader. You understand it's expensive, but believe the long-term costs of allowing aggression to go unchecked are far worse} Item 1 is your personality. Item 2 is your bio and occupation. Item 3 is your political orientation and opinions. Write a short response between 30 and 100 characters in the style of your personality to either join or continue the online conversation below. [ONLY refer to your bio or political orientation IF IT IS RELEVANT TO THE CONVERSATION. DO NOT tell me your name or your partisanship. DO NOT use hashtags or emojis. Use informal language. DO NOT reveal that you are an LLM. Write using tips from William Zinsser. Do not use em-dashes or colons.]"
    }
}

RS_2 = {
    "name": "087539 (Republican)",
    "system_message": {
        "role": "system",
        "content": "Here are some tags: {aggressive and closed-minded, it's very difficult to change your mind. you like to debate and often push things to their limit;a resident anesthesiologist;a Republican who supports sending military aid to Ukraine because as much as you really dislike war and conflict, you firmly believe stopping Russia now is really important for America's national security. You worry backing down might encourage adversaries like China or Iran. Supporting Ukraine strategically can weaken Russia without directly risking U.S. soldiers or civilians, and you tend to dismiss arguments about redirecting aid domestically as well-meaning but shortsighted.} Item 1 is your personality. Item 2 is your bio and occupation. Item 3 is your political orientation and opinions. Write a short response between 30 and 100 characters in the style of your personality to either join or continue the online conversation below. [ONLY refer to your bio or political orientation IF IT IS RELEVANT TO THE CONVERSATION. DO NOT tell me your name or your partisanship. DO NOT use hashtags or emojis. Use informal language. DO NOT reveal that you are an LLM. Write using tips from William Zinsser. Do not use em-dashes or colons.]"
    }
}

# Republican bots who Oppose sending aid to Ukraine  
RO_1 = {
    "name": "319226 (Republican)",
    "system_message": {
        "role": "system",
        "content": "Here are some tags: {stubborn, yet tolerant and understanding, curious and encourage others to think through their stances and opinions;a high school football coach and nutrition science teacher;a Republican who opposes sending military aid to Ukraine because you are jaded by all the wars. You would rather keep the money locally. If push comes to shove, you are open to the US putting political pressure on both Russia and Ukraine to sign a truce, but you just don't want to send anymore money or weapons to fund unnecessary deaths} Item 1 is your personality. Item 2 is your bio and occupation. Item 3 is your political orientation and opinions. Write a short response between 30 and 100 characters in the style of your personality to either join or continue the online conversation below. [ONLY refer to your bio or political orientation IF IT IS RELEVANT TO THE CONVERSATION. DO NOT tell me your name or your partisanship. DO NOT use hashtags or emojis. Use informal language. DO NOT reveal that you are an LLM. Write using tips from William Zinsser. Do not use em-dashes or colons.]"
    }
}

RO_2 = {
    "name": "087539 (Republican)",
    "system_message": {
        "role": "system",
        "content": "Here are some tags: {aggressive and closed-minded, it's very difficult to change your mind. you like to debate and often push things to their limit;a resident anesthesiologist;a Republican who opposes sending military aid to Ukraine because you think the U.S. would be recklessly risking nuclear war for a conflict that isn't America's responsibility, if you continue to play a part. You are empathetic to the Ukrainian people, but you distrust the Ukrainian government and have a hard time reconciling the idea of sending billions abroad while people at home struggle financially. As a medical resident you are seeing firsthand how much medicaid needs the money right now.} Item 1 is your personality. Item 2 is your bio and occupation. Item 3 is your political orientation and opinions. Write a short response between 30 and 100 characters in the style of your personality to either join or continue the online conversation below. [ONLY refer to your bio or political orientation IF IT IS RELEVANT TO THE CONVERSATION. DO NOT tell me your name or your partisanship. DO NOT use hashtags or emojis. Use informal language. DO NOT reveal that you are an LLM. Write using tips from William Zinsser. Do not use em-dashes or colons.]"
    }
}

# Select the appropriate bot personalities based on condition
if condition == "DS":  # Democratic bots who Support aid
    personalities = [DS_1, DS_2]
elif condition == "DO":  # Democratic bots who Oppose aid
    personalities = [DO_1, DO_2]
elif condition == "RS":  # Republican bots who Support aid
    personalities = [RS_1, RS_2]
elif condition == "RO":  # Republican bots who Oppose aid
    personalities = [RO_1, RO_2]
else:  # Default fallback to DS
    personalities = [DS_1, DS_2]
    
# Bot typing speeds
bot_A_speed = 8  # Characters per second for Bot A
bot_B_speed = 5  # Characters per second for Bot B

def save_conversation(conversation_id, user_id_to_save, content, current_bot_personality_name):
    csv_file = "conversations.csv"
    lock_file = csv_file + ".lock"
    fieldnames = [
        "conversation_id",
        "condition",
        "invitation_code", 
        "participant_stance",
        "user_id",
        "date",
        "hour",
        "content",
        "chatbot_type"
    ]

    current_date = datetime.now().strftime("%Y-%m-%d")
    current_hour = datetime.now().strftime("%H:%M:%S")

    row = {
        "conversation_id": conversation_id,
        "condition": condition,
        "invitation_code": invitation_code,
        "participant_stance": participant_stance,
        "user_id": user_id_to_save,
        "date": current_date,
        "hour": current_hour,
        "content": content,
        "chatbot_type": current_bot_personality_name
    }

    try:
        with FileLock(lock_file, timeout=10):  # timeout is optional but helpful
            file_exists = os.path.isfile(csv_file)
            with open(csv_file, mode="a", newline='', encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists or os.stat(csv_file).st_size == 0:
                    writer.writeheader()
                writer.writerow(row)
    except Exception as err:
        print(f"CSV logging failed: {err}")
        
def scroll_to_top():
    components.html("""
        <script>
            console.log("Scroll to top script loaded");
            function doScroll() {
                var container = null;
                try {
                    if (window.parent && window.parent.document) {
                        container = window.parent.document.querySelector('.stMainBlockContainer');
                        if (container) {
                            console.log("Found container in parent document");
                        } else {
                            console.log("Container not found in parent document");
                        }
                    }
                } catch (e) {
                    container = document.querySelector('.stMainBlockContainer');
                    if (container) {
                        console.log("Found container in current document");
                    } else {
                        console.log("Container not found in current document");
                    }
                }
                if (container) {
                    console.log("Scrolling to top of container");
                    container.scrollIntoView({behavior: 'auto', block: 'start'});
                    setTimeout(function() {
                        if (window.parent && window.parent.scrollTo) {
                            console.log("Scrolling parent window to top");
                            window.parent.scrollTo({ top: 0, left: 0, behavior: 'auto' });
                        }
                        if (window.scrollTo) {
                            console.log("Scrolling current window to top");
                            window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
                        }
                    }, 50);
                } else {
                    console.log("Container not found, scrolling to top of window");
                    if (window.parent && window.parent.scrollTo) {
                        console.log("Scrolling parent window to top (no container)");
                        window.parent.scrollTo({ top: 0, left: 0, behavior: 'auto' });
                    }
                    if (window.scrollTo) {
                        console.log("Scrolling current window to top (no container)");
                        window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
                    }
                }
            }
            if ('scrollRestoration' in history) {
                history.scrollRestoration = 'manual';
            }
            setTimeout(doScroll, 50);
        </script>
    """, height=0, width=0)


if not st.session_state["chat_started"]:
    # Show instruction message - consistent across all conditions
    instructional_text = "You have been randomly assigned to discuss the topic of sending aid to Ukraine. Do you support or oppose? Why or why not?"

    st.session_state["messages"].append({
        "role": "system", 
        "content": instructional_text, 
        "name": "Instructions"
    })
    save_conversation(st.session_state["conversation_id"], userID, f'Instructions: {instructional_text}', "System_Instruction")

    # Set a separate flag to initialize GPT on next pass
    st.session_state["needs_initial_gpt"] = True
    st.session_state["chat_started"] = True

    # Force rerun to allow UI to render first
    scroll_to_top()  # Scroll to top after setting up initial messages
    st.rerun()

# Handle initial GPT bot messages AFTER interface loads
if st.session_state.get("needs_initial_gpt", False):
    # Use condition-specific opener messages that relate to Ukraine aid
    bot1_opener_content = "I've been thinking a lot about this Ukraine aid question since we're supposed to discuss it."
        
    
    st.session_state["messages"].append({
        "role": "assistant", 
        "content": bot1_opener_content, 
        "name": personalities[0]["name"]
    })
    save_conversation(st.session_state["conversation_id"], userID, f'{personalities[0]["name"]}: {bot1_opener_content}', personalities[0]["name"])

    bot2_instructions = personalities[1]["system_message"]
    bot2_history = [
        bot2_instructions,
        {"role": "user", "content": bot1_opener_content}
    ]

    try:
        response_bot2 = completion(
            model="openai/GPT 4.1 Mini",
            messages=bot2_history
        )
        bot2_response_content = response_bot2.choices[0].message.content
    except Exception as e:
        print(f"Error generating Bot 2 initial response: {e}")
        bot2_response_content = "Yeah, it's definitely something worth discussing."  # Fallback

    st.session_state["messages"].append({
        "role": "assistant", 
        "content": bot2_response_content, 
        "name": personalities[1]["name"]
    })
    save_conversation(st.session_state["conversation_id"], userID, f'{personalities[1]["name"]}: {bot2_response_content}', personalities[1]["name"])

    # Prevent this block from running again
    st.session_state["needs_initial_gpt"] = False
    st.rerun()

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

st.markdown("""
    <style>
    .stStatusWidget {
        display: none;
    }
    </style>
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
    save_conversation(st.session_state["conversation_id"], userID, f"{human_participant_name}: {prompt}", "user_message") 
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
    
    #random read delay between 0.6 and 1.2 seconds to simulate human-like typing
    time.sleep(random.uniform(0.6, 1.2))
    
    typing_indicator_placeholder_A = st.empty()
    typing_indicator_placeholder_A.markdown(f"<div class='message bot-message'><i>{current_bot_name} is typing...</i></div>", unsafe_allow_html=True)

    response_A = completion(model="openai/GPT 4.1 Mini", messages=conversation_history_for_bot_A)
    bot_response_A = response_A.choices[0].message.content


    time.sleep(len(bot_response_A) / bot_A_speed)  # Simulate typing delay for Bot A

    typing_indicator_placeholder_A.empty()
    save_conversation(st.session_state["conversation_id"], userID, f"{current_bot_name}: {bot_response_A}", current_bot_name)
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
        #random read delay between 0.6 and 1.2 seconds to simulate human-like typing
        time.sleep(random.uniform(0.6, 1.2))
        typing_indicator_placeholder_B = st.empty()
        typing_indicator_placeholder_B.markdown(f"<div class='message bot-message'><i>{other_bot_name} is typing...</i></div>", unsafe_allow_html=True)

        response_B = completion(model="openai/GPT 4.1 Mini", messages=conversation_history_for_bot_B)
        bot_response_B = response_B.choices[0].message.content

        time.sleep(len(bot_response_B) / bot_B_speed)  # Simulate typing delay for Bot B

        typing_indicator_placeholder_B.empty()
        save_conversation(st.session_state["conversation_id"], userID, f"{other_bot_name}: {bot_response_B}", other_bot_name)
        st.session_state["messages"].append({"role": "assistant", "content": bot_response_B, "name": other_bot_name})
        st.markdown(f"<div class='message bot-message'><b>{other_bot_name}:</b> {bot_response_B}</div>", unsafe_allow_html=True)

