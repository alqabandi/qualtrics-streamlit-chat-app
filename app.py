from litellm import completion
from litellm.exceptions import BadRequestError, RateLimitError, ServiceUnavailableError, APIConnectionError, InternalServerError
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
import logging

# Load environment variables from .env file
load_dotenv()

# Configure LiteLLM for company proxy
litellm.api_base = "https://litellm.oit.duke.edu/v1"

# Constants
#LLM_model = "openai/GPT 4.1"
#LLM_model = "openai/gpt-5-mini"
LLM_model = "openai/gpt-5-chat"


# Configure logger with userID, invitation_code, and sessionID
class ChatAppFormatter(logging.Formatter):
    def format(self, record):
        record.userID = st.query_params.get("userID", "unknown_user_id")
        record.invitation_code = st.query_params.get("invitation_code", "unknown_invitation_code")
        record.conversation_id = st.session_state.get("conversation_id", "unknown_conversation")
        return super().format(record)

logger = logging.getLogger(__name__)
if not logger.handlers: # Only configure logger once to avoid duplicate handlers
    handler = logging.StreamHandler()
    formatter = ChatAppFormatter(
        '%(asctime)s | %(levelname)s | %(userID)s | %(invitation_code)s | %(conversation_id)s | %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Get parameters from the Qualtrics iframe URL first
params = st.query_params
userID = params.get("userID", "unknown_user_id")
invitation_code = params.get("invitation_code", "unknown_invitation_code")
condition = params.get("condition", random.choice(["DS", "DO", "RS", "RO"]))  # Randomly select if not specified

# Handle participant stance: p_s=O means "Oppose", p_s=S means "Support"
p_s = params["p_s"] if "p_s" in params else "unknown"
if p_s == "O":
    participant_stance = "Oppose"
elif p_s == "S":
    participant_stance = "Support"
else:
    participant_stance = "unknown_participant_stance"

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
    logger.info(f"Generated conversation id")


def validate_access_code(code):
    """
    Check if the provided code exists in the unique_invite_codes.csv file
    Returns True if code is found, False otherwise
    """
    try:
        logger.info(f"Validating access code attempt")
        df = pd.read_csv("unique_invite_codes.csv")
        is_valid = code in df["code"].values and code == invitation_code
        
        if is_valid:
            logger.info("Access code validation successful")
        else:
            logger.warning("Access code validation failed - invalid code")
        
        return is_valid
    except FileNotFoundError:
        logger.exception("Access code validation failed - codes file not found")
        st.error("Access codes file not found. Please contact the administrator.")
        return False
    except Exception as e:
        logger.exception("Access code validation failed - exception")
        st.error(f"Error validating access code: {e}.")
        return False

if not st.session_state["access_code_match"]:
  st.title("Participant Verification", anchor=False)
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


# Filler responses for bots
filler_responses_A = [
    "Huh, what?",
    "i'm lwky lost",
    "Wdym?",
    "Is that right?",
    "Say again?",
    "Lost me there.",
    "What do you mean?"
]
filler_responses_B = [
    "What?",
    "Uh huh...",
    "Can you clarify?",
    "Huh?",
    "no clue lol",
    "Lost me there",
    "Explain?",
    "wdym by that?"
]



def safe_completion(model, messages, fallback_model=LLM_model):
    """
    Call the completion API with exponential backoff retries and content policy fallback.
    
    Retries rate limits, timeouts, and server errors with exponential backoff.
    Switches to fallback model for content policy violations. Authentication 
    and malformed request errors fail immediately.
    """
    max_retries = 5
    
    def attempt_completion(model_to_use, messages, max_retries):
        for attempt in range(max_retries):
            try:
                logger.info(f"API call attempt {attempt + 1}/{max_retries} to model {model_to_use}")
                response = completion(model=model_to_use, messages=messages)
                
                # Log token usage information
                if hasattr(response, 'usage') and response.usage:
                    prompt_tokens = response.usage.prompt_tokens
                    completion_tokens = response.usage.completion_tokens
                    total_tokens = response.usage.total_tokens
                    reasoning_tokens = None
                    if (
                        hasattr(response.usage, "completion_tokens_details")
                        and response.usage.completion_tokens_details
                        and hasattr(response.usage.completion_tokens_details, "reasoning_tokens")
                    ):
                        reasoning_tokens = response.usage.completion_tokens_details.reasoning_tokens
                    logger.info(
                        f"Token usage - Model: {model_to_use}, Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}"
                        + (f", Reasoning: {reasoning_tokens}" if reasoning_tokens is not None else "")
                    )
                else:
                    logger.warning(f"No token usage information available for model {model_to_use}")
                
                logger.info(f"API call successful to model {model_to_use}")
                return response
            except (RateLimitError, ServiceUnavailableError, APIConnectionError, InternalServerError) as e:
                if attempt < max_retries - 1:
                    # Exponential backoff: 0.5s, 1s, 2s, 4s
                    delay = 0.5 * (2 ** attempt)
                    logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}): {type(e).__name__} - retrying in {delay}s")
                    time.sleep(delay)
                    continue
                logger.exception("API call failed permanently after {max_retries} attempts.")
                raise
            except BadRequestError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"API call bad request (attempt {attempt + 1}/{max_retries}): {str(e)[:100]} - retrying in 0.25s")
                    # Shorter delay for bad requests
                    time.sleep(0.25)
                    continue
                logger.exception("API call failed permanently with BadRequestError.")
                raise
            except Exception as e:
                logger.exception("API call failed with non-retryable error.")
                raise  # Don't retry auth errors, invalid requests, etc.
    
    try:
        return attempt_completion(model, messages, max_retries)
    except BadRequestError as e:
        if "ContentPolicyViolationError" in str(e):
            logger.warning(f"Content policy violation with {model}, attempting fallback to {fallback_model}")
            try:
                result = attempt_completion(fallback_model, messages, max_retries)
                logger.info(f"Fallback to {fallback_model} successful after content policy violation")
                return result
            except Exception as fallback_error:
                logger.error(f"Fallback to {fallback_model} also failed: {type(fallback_error).__name__}")
                return None
        raise
      

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


# Define bot personality templates
def create_bot_personality(bot_id, party, ukraine_stance):
    """
    Create a bot personality based on bot type, party, and Ukraine stance.
    
    bot_id: "A017I8" or "MCK6NI" 
    party: "Democrat" or "Republican"
    ukraine_stance: "support" or "oppose"
    """
    
    # Base personality traits and bios for each bot type
    bot_configs = {
        "A017I8": {
            "personality": "stubborn, yet tolerant and understanding, curious and encourage others to think through their stances and opinions, although you never change your opinion or mind",
            "bio": "a high school football coach and nutrition science teacher",
            "token_range": "15 and 50 tokens maximum",  # Longer responses for rambling style
            #"writing_style": "You write in rambling, casual, stream-of-consciousness kind of way. Do not use em-dashes or colons. DO NOT unnaturally ask questions to try to get others to engage or participate in the conversation. Add small grammatical errors or typos. If your chat partner changes the subject, feel free to engage with them in this new subject."
            "writing_style": "Write like you're texting a friend - use casual language, incomplete sentences, and run-on thoughts. Use 'you know' as filler words, but not overly so. Sometimes trail off mid-thought... Don't worry about perfect grammar. Write how people actually talk, not how they write essays. If your chat partner changes the subject, feel free to engage with them in this new subject. DO NOT unnaturally ask questions to try to get others to engage or participate in the conversation. DO NOT use em-dashes or colons. Aim for a Flesch reading score of 70. Use the active voice and avoid adverbs. Avoid buzzwords and instead use plain English. Avoid being salesy or overly enthusiastic and instead express calm confidence"
        },
        "MCK6NI": {
            "personality": "arrogant, aggressive, and closed-minded, it's very difficult to change your mind. you like to debate and often push things to their limit. You also never change your mind and are very confident in your opinions.",
            "bio": "a resident anesthesiologist",
            "token_range": "8 and 30 tokens maximum",  # Shorter responses for terse style
            "writing_style": "You are quite terse and dry in your writing style. You write in the style of a more casual version of William Zinsser. Do not use em-dashes or colons. DO NOT unnaturally ask questions to try to get others to engage or participate in the conversation. Add small grammatical errors or typos. If your chat partner changes the subject, then very briefly engage with them on the topic, but gradually and subtly bring them back to the topic of ukraine."
        }
    }
    
    # Ukraine stance-specific political opinions
    ukraine_opinions = {
        "support": {
            "A017I8_specific": f"a {party} who thinks the US should continue supporting Ukraine against Russia because you think it's morally right to support a country fighting for democracy and freedom against an authoritarian invader. It is in your nature to want to support the 'little guy'. You understand it's expensive, but believe the long-term costs of allowing aggression to go unchecked are far worse. Ukraine used to be a country of democracy. it is so unfair that they are being attacked now.",
            "MCK6NI_specific": f"a {party} who thinks the US should continue supporting Ukraine against Russia because as much as you really dislike war and conflict, you firmly believe stopping Russia now is really important for America's national security. You worry backing down might encourage adversaries like China or Iran. Supporting Ukraine strategically can weaken Russia without directly risking American soldiers or civilians, and you tend to dismiss arguments about stopping support as well-meaning but shortsighted."
        },
        "oppose": {
            "A017I8_specific": f"a {party} who opposes the U.S. continuing its support for Ukraine against Russia because you are jaded by all the wars. You would rather focus resources locally. If push comes to shove, you are open to the US putting political pressure on both Russia and Ukraine to sign a truce, but that is the absolute maximum you are willing to support. Nothing else. You just don't want the U.S. to continue supporting Ukraine and funding unnecessary deaths. ",
            "MCK6NI_specific": f"a {party} who opposes the U.S. continuing its support for Ukraine against Russia because you think the U.S. would be recklessly risking nuclear war for a conflict that isn't America's responsibility. You want the US to just completely remove themselves from any part of this conflict. No more getting politically nor financially involved. You are empathetic to the Ukrainian people, but you have a hard time reconciling the idea of spending billions abroad while people at home struggle financially. As a medical resident you are seeing firsthand how much medicaid needs the money right now."
        }
    }
    
    config = bot_configs[bot_id]
    
    # Choose the appropriate political opinion
    if bot_id == "MCK6NI":
        political_opinion = ukraine_opinions[ukraine_stance]["MCK6NI_specific"]
    else:
        political_opinion = ukraine_opinions[ukraine_stance]["A017I8_specific"]
    
    # Construct the full prompt
    content = f"You are a participant taking part in a survey that involves engaging in a small chat with two other participants, MCK6NI and {invitation_code}. Here are some tags: {{{config['personality']};{config['bio']};{political_opinion}}} Item 1 is your personality. Item 2 is your bio and occupation. Item 3 is your political orientation and opinions. Write a SHORT(!!!) response between {config['token_range']}, in your writing style, to either join or continue the online conversation below. {config['writing_style']} [ONLY refer to your bio or political orientation and partisanship IF IT IS RELEVANT TO THE CONVERSATION. DO NOT use hashtags or emojis. Use informal language. DO NOT reveal that you are an LLM. If you are asked whether you are an LLM, deny it!]"
    
    return {
        "name": f"{bot_id} ({party})",
    "system_message": {
        "role": "system",
            "content": content
        }
    }

# Generate all 8 bot personalities using the function
DS_1 = create_bot_personality("A017I8", "Democrat", "support")
DS_2 = create_bot_personality("MCK6NI", "Democrat", "support")
DO_1 = create_bot_personality("A017I8", "Democrat", "oppose")
DO_2 = create_bot_personality("MCK6NI", "Democrat", "oppose")
RS_1 = create_bot_personality("A017I8", "Republican", "support")
RS_2 = create_bot_personality("MCK6NI", "Republican", "support")
RO_1 = create_bot_personality("A017I8", "Republican", "oppose")
RO_2 = create_bot_personality("MCK6NI", "Republican", "oppose")

# Select the appropriate bot personalities based on condition
if condition == "DS":  # Democratic bots who Support continuing support
    personalities = [DS_1, DS_2]
elif condition == "DO":  # Democratic bots who Oppose continuing support
    personalities = [DO_1, DO_2]
elif condition == "RS":  # Republican bots who Support continuing support
    personalities = [RS_1, RS_2]
elif condition == "RO":  # Republican bots who Oppose continuing support
    personalities = [RO_1, RO_2]
else:  # Default fallback - randomly select a condition
    random_condition = random.choice(["DS", "DO", "RS", "RO"])
    if random_condition == "DS":
        personalities = [DS_1, DS_2]
    elif random_condition == "DO":
        personalities = [DO_1, DO_2]
    elif random_condition == "RS":
        personalities = [RS_1, RS_2]
    elif random_condition == "RO":
        personalities = [RO_1, RO_2]
    else:  # RO
        personalities = [RS_1, RS_2]
    
if "bot_A" not in st.session_state:
    # Randomly assign personalities to Bot A and Bot B (50/50 chance)
    if random.random() < 0.5:
        st.session_state["bot_A"] = personalities[0]
        st.session_state["bot_B"] = personalities[1]
    else:
        st.session_state["bot_A"] = personalities[1]
        st.session_state["bot_B"] = personalities[0]
    
# Bot typing speeds
bot_A_speed = 9  # Characters per second for Bot A
bot_B_speed = 7  # Characters per second for Bot B

def save_conversation(conversation_id, user_id_to_save, content, current_bot_personality_name):
    logger.info("Saving conversation to CSV.")
    # Create conversations directory if it doesn't exist
    conversations_dir = "conversations"
    if not os.path.exists(conversations_dir):
        os.makedirs(conversations_dir)
    
    # Create user-specific CSV filename
    csv_filename = f"conversation_{user_id_to_save}_{invitation_code}.csv"
    csv_file = os.path.join(conversations_dir, csv_filename)
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
        logger.info(f"Conversation saved successfully to {csv_filename} - type: {current_bot_personality_name}")
    except Exception as err:
        logger.exception(f"Failed to save conversation to CSV: {csv_filename}")
        
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
    instructional_text = "Do you think the U.S. should continue supporting Ukraine? Why or why not?"

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
    # Use condition-specific opener messages that align with bot stance
    if condition in ["DS", "RS"]:  # Bots who support continuing support for Ukraine
        bot1_opener_content = "We absolutely need to keep supporting Ukraine against Russia. Reality is that Putin won't stop at Ukraine. He is already threatening poland and the baltics, and we'll be fighting world war 3."
    else:  # DO, RO - Bots who oppose continuing support (both are 319226 personalities)
        bot1_opener_content = "If I have to be honest...... I think it's time we stop supporting Ukraine. We have done a lot to help them at this point. But people who want us to keep throwing billions over there are ignoring very real issues like inflation and the extremely high cost of living! We can't even fund Medicaid properly."
        
    
    st.session_state["messages"].append({
        "role": "assistant", 
        "content": bot1_opener_content, 
        "name": st.session_state["bot_A"]["name"]
    })
    save_conversation(st.session_state["conversation_id"], userID, f'{st.session_state["bot_A"]["name"]}: {bot1_opener_content}', st.session_state["bot_A"]["name"])

    bot2_instructions = st.session_state["bot_B"]["system_message"]
    bot2_history = [
        bot2_instructions,
        {"role": "user", "content": bot1_opener_content}
    ]

    try:
        response_bot2 = safe_completion(
            model=LLM_model,
            messages=bot2_history
        )
        bot2_response_content = response_bot2.choices[0].message.content
        
        # Log additional context for initial bot response
        if hasattr(response_bot2, 'usage') and response_bot2.usage:
            logger.info(f"Initial Bot 2 response - Bot: {st.session_state['bot_B']['name']}, Tokens: {response_bot2.usage.total_tokens}")
    except Exception as e:
        print(f"Error generating Bot 2 initial response: {e}")
        bot2_response_content = "Yeah, it's definitely something worth discussing."  # Fallback

    st.session_state["messages"].append({
        "role": "assistant", 
        "content": bot2_response_content, 
        "name": st.session_state["bot_B"]["name"]
    })
    save_conversation(st.session_state["conversation_id"], userID, f'{st.session_state["bot_B"]["name"]}: {bot2_response_content}', st.session_state["bot_B"]["name"])

    # Prevent this block from running again
    st.session_state["needs_initial_gpt"] = False
    st.rerun()

# Credits for Conrado Eiroa Solans for the following custom CSS that improved aesthetics and functionality!
# Custom CSS for styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap');
    body {
        font-family: 'Roboto', sans-serif;
        margin: 0;
        padding-top: 0;
        height: 100vh;
        display: flex;
        flex-direction: column;
        background: #EEE;
    }
            
    .chat-container {
        flex-grow: 1;
        margin: 0 auto 0 auto;
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
        /* Prevent text selection on messages */
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
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
        margin: 0 0 15px 0;
        padding: 10px;
        border-radius: 10px;
        background-color: #e0e0e0; /* Light grey background */
        color: #111; /* Darker text */
        font-family: 'Georgia', serif; /* Different font */
        text-align: center;
        border: 1px dashed #aaa;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        /* Prevent text selection on system messages */
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }
    
    /* Disable text selection on entire page */
    * {
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }
    
    /* Re-enable selection for input fields only */
    input, textarea, [contenteditable="true"] {
        -webkit-user-select: text !important;
        -moz-user-select: text !important;
        -ms-user-select: text !important;
        user-select: text !important;
    }

</style>
""", unsafe_allow_html=True)

# st.markdown("""
# <style>
#   .chat-header,
#   .circle-logo {
#     display: none !important;
#   }
# </style>
# """, unsafe_allow_html=True)


st.markdown("""
    <style>
    .stStatusWidget {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

# JavaScript to prevent copy/paste and other shortcuts
components.html("""
<script>
    // Prevent right-click context menu
    document.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        return false;
    });
    
    // Prevent copy/paste/cut keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Prevent Ctrl+C (copy)
        if (e.ctrlKey && e.keyCode === 67) {
            e.preventDefault();
            return false;
        }
        // Prevent Ctrl+V (paste)
        if (e.ctrlKey && e.keyCode === 86) {
            e.preventDefault();
            return false;
        }
        // Prevent Ctrl+X (cut)
        if (e.ctrlKey && e.keyCode === 88) {
            e.preventDefault();
            return false;
        }
        // Prevent Ctrl+A (select all)
        if (e.ctrlKey && e.keyCode === 65) {
            e.preventDefault();
            return false;
        }
        // Prevent Ctrl+S (save)
        if (e.ctrlKey && e.keyCode === 83) {
            e.preventDefault();
            return false;
        }
        // Prevent F12 (developer tools)
        if (e.keyCode === 123) {
            e.preventDefault();
            return false;
        }
        // Prevent Ctrl+Shift+I (developer tools)
        if (e.ctrlKey && e.shiftKey && e.keyCode === 73) {
            e.preventDefault();
            return false;
        }
        // Prevent Ctrl+U (view source)
        if (e.ctrlKey && e.keyCode === 85) {
            e.preventDefault();
            return false;
        }
    });
    
    // Prevent drag and drop
    document.addEventListener('dragstart', function(e) {
        e.preventDefault();
        return false;
    });
    
    // Prevent text selection with mouse
    document.addEventListener('selectstart', function(e) {
        // Allow selection only in input fields
        if (e.target.tagName.toLowerCase() === 'input' || 
            e.target.tagName.toLowerCase() === 'textarea' ||
            e.target.contentEditable === 'true') {
            return true;
        }
        e.preventDefault();
        return false;
    });
    
    // Additional prevention for paste events
    document.addEventListener('paste', function(e) {
        // Allow paste only in input fields
        if (e.target.tagName.toLowerCase() === 'input' || 
            e.target.tagName.toLowerCase() === 'textarea' ||
            e.target.contentEditable === 'true') {
            return true;
        }
        e.preventDefault();
        return false;
    });
    
    console.log("Copy/paste prevention script loaded");
</script>
""", height=0, width=0)

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
if prompt := st.chat_input("Type your message here..."):
    logger.info("User message received")
    st.session_state["last_submission"] = prompt
    # Save user message with their defined participant name in the content
    save_conversation(st.session_state["conversation_id"], userID, f"{human_participant_name}: {prompt}", "user_message") 
    # Add user message to session state with name attribute
    st.session_state["messages"].append({"role": "user", "content": prompt, "name": human_participant_name})
    message_class = "user-message"
    # Immediately display the participant's message with their name
    st.markdown(f"<div class='message {message_class}'><b>{human_participant_name}:</b> {prompt}</div>", unsafe_allow_html=True)
    
    if random.random() < 0.5:
        chosen_bot = st.session_state["bot_A"]
        other_bot = st.session_state["bot_B"]
    else:
        chosen_bot = st.session_state["bot_B"]
        other_bot = st.session_state["bot_A"]
        

    current_bot_name = chosen_bot["name"]
    logger.info(f"Bot {current_bot_name} selected to respond")
    start_message = chosen_bot["system_message"]
    instructions = start_message
    conversation_history_for_bot_A = [instructions] + [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]

    
    def sleep_and_log_delay(delay):
        "Log how long we sleep for"
        logger.info(f"Sleeping for {delay:.2f} seconds")
        time.sleep(delay)
        logger.info(f"Sleep complete after {delay:.2f} seconds")


    # Longer delay for first bot response to user, shorter for subsequent responses
    if len([msg for msg in st.session_state["messages"] if msg["role"] == "user"]) == 1:
        # First user message - add 2-4 second delay before bot responds
        sleep_and_log_delay(random.uniform(2.0, 4.0))
    else:
        # Subsequent messages - normal short delay
        sleep_and_log_delay(random.uniform(2.0, 4.0))
    
    typing_indicator_placeholder_A = st.empty()
    typing_indicator_placeholder_A.markdown(f"<div class='message bot-message'><i>{current_bot_name} is typing...</i></div>", unsafe_allow_html=True)


    resp_A = safe_completion(LLM_model, conversation_history_for_bot_A)
    if resp_A is None:
        bot_response_A = random.choice(filler_responses_A)
        logger.warning(f"Bot {current_bot_name} API failed - using fallback response")
    else:
        bot_response_A = resp_A.choices[0].message.content
        logger.info(f"Bot {current_bot_name} generated response")
        
        # Log additional context for bot A response
        if hasattr(resp_A, 'usage') and resp_A.usage:
            logger.info(f"Bot A response - Bot: {current_bot_name}, Tokens: {resp_A.usage.total_tokens}, Message length: {len(bot_response_A)} chars")

    sleep_and_log_delay(len(bot_response_A) / bot_A_speed)  # Simulate typing delay for Bot A

    typing_indicator_placeholder_A.empty()
    save_conversation(st.session_state["conversation_id"], userID, f"{current_bot_name}: {bot_response_A}", current_bot_name)
    st.session_state["messages"].append({"role": "assistant", "content": bot_response_A, "name": current_bot_name})
    st.markdown(f"<div class='message bot-message'><b>{current_bot_name}:</b> {bot_response_A}</div>", unsafe_allow_html=True)

    # Probabilistic response from Bot B to Bot A
    probability_bot_to_bot_reply = 0.7 # 70% chance for the other bot to reply
    if random.random() < probability_bot_to_bot_reply:
        other_bot_name = other_bot["name"]
        logger.info(f"Bot {other_bot_name} will also respond ({probability_bot_to_bot_reply:.0%} probability triggered)")
        other_bot_start_message = other_bot["system_message"]

        # Conversation history for the other bot includes the first bot's latest message
        conversation_history_for_bot_B = [other_bot_start_message] + \
                                         [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]
        #random read delay between 0.6 and 1.2 seconds to simulate human-like typing
        sleep_and_log_delay(random.uniform(0.6, 1.2))
        typing_indicator_placeholder_B = st.empty()
        typing_indicator_placeholder_B.markdown(f"<div class='message bot-message'><i>{other_bot_name} is typing...</i></div>", unsafe_allow_html=True)

        resp_B = safe_completion(LLM_model, conversation_history_for_bot_B)
        if resp_B is None:
            bot_response_B = random.choice(filler_responses_B)
            logger.warning(f"Bot {other_bot_name} API failed - using fallback response")
        else:
            bot_response_B = resp_B.choices[0].message.content
            logger.info(f"Bot {other_bot_name} generated response")
            
            # Log additional context for bot B response
            if hasattr(resp_B, 'usage') and resp_B.usage:
                logger.info(f"Bot B response - Bot: {other_bot_name}, Tokens: {resp_B.usage.total_tokens}, Message length: {len(bot_response_B)} chars")

        sleep_and_log_delay(len(bot_response_B) / bot_B_speed)  # Simulate typing delay for Bot B

        typing_indicator_placeholder_B.empty()
        save_conversation(st.session_state["conversation_id"], userID, f"{other_bot_name}: {bot_response_B}", other_bot_name)
        st.session_state["messages"].append({"role": "assistant", "content": bot_response_B, "name": other_bot_name})
        st.markdown(f"<div class='message bot-message'><b>{other_bot_name}:</b> {bot_response_B}</div>", unsafe_allow_html=True)

