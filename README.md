# Qualtrics Streamlit Chat App

A chat application that embeds in Qualtrics surveys. Participants chat with AI bots that have different political stances on whether the US should continue to support Ukraine.

This repository builds upon code from [vicomello/customizable_chatbot](https://github.com/vicomello/customizable_chatbot), who also credits Conrado Eiroa Solans for the some of the CSS styling. We have adapted and extended these components, adding experimental conditions, bot personalities, structured logging, access control, and other features.

## What You'll Build

By the end of this guide, you'll have:
- A live chat app running on Duke's VCM
- HTTPS access for Qualtrics embedding  
- Separate conversation files for each participant
- A complete research pipeline from survey to data

## Prerequisites

You need:
- Duke NetID and access to VCM
- Basic terminal skills
- A computer with SSH capability

## Local Development Setup

### Install Tools

On macOS, install these tools:

```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install uv and Docker
brew install uv
brew install --cask docker
```

### Set Up the Project

```bash
git clone https://github.com/alqabandi/qualtrics-streamlit-chat-app.git
cd qualtrics-streamlit-chat-app
uv sync
```

Create a `.env` file:
```env
DUKE_API_KEY=your_litellm_api_key_here
```

You can get a Gateway API key from dashboard.oit.duke.edu.

Test locally:
```bash
uv run streamlit run app.py
```

Visit `http://localhost:8501` to verify it works.

## VCM Setup

### Create Your VM

1. Go to [Duke VCM Portal](https://vcm.duke.edu/)
2. Create a new VM with default settings (Ubuntu 22.04 LTS)
3. Note your VM number (like `vcm-12345.vm.duke.edu`)

### Configure the VM

SSH into your VM:
```bash
ssh vcm@vcm-XXXXX.vm.duke.edu
```

Install Docker and Git:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io git
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

Log out and back in for Docker permissions to take effect.

### Deploy Your App

Clone your repository:
```bash
git clone https://github.com/alqabandi/qualtrics-streamlit-chat-app.git
cd qualtrics-streamlit-chat-app
```

Create your `.env` file:
```bash
nano .env
```

Add your API key:
```env
DUKE_API_KEY=your_litellm_api_key_here
```

Build and run:
```bash
sudo docker build -t qualtrics_app .
sudo docker run -d \
  --name qualtrics_app_public \
  --restart unless-stopped \
  --env-file .env \
  -p 8501:8501 \
  -v ./conversations:/app/conversations \
  qualtrics_app
```

Your app now runs at `https://vcm-XXXXX.vm.duke.edu:8501`

## Set Up Access Codes

Create `unique_invite_codes.csv` with your participant codes:
```csv
code
ABC123
DEF456
GHI789
```

Upload this file to your VM:
```bash
scp unique_invite_codes.csv vcm@vcm-XXXXX.vm.duke.edu:~/qualtrics-streamlit-chat-app/
```

## Qualtrics Integration

### Create Survey Fields

In Qualtrics, set up these Embedded Data fields:
- `ResponseID` (automatic)
- `invitation_code` (your access codes)
- `participantCondition` (DS, DO, RS, RO)
- `p_s` (O for Oppose, S for Support)

### Add the iframe

In your Qualtrics question, use HTML View:

```html
<iframe 
  src="https://vcm-XXXXX.vm.duke.edu:8501/?embed=true&userID=${e://Field/ResponseID}&invitation_code=${e://Field/invitation_code}&condition=${e://Field/participantCondition}&p_s=${e://Field/p_s}" 
  width="100%" 
  height="600px" 
  frameborder="0">
</iframe>
```

Replace `vcm-XXXXX` with your VM number.

### Experimental Conditions

The app has four conditions:
- **DS**: Democratic bots who think the US should continue to support Ukraine against Russia
- **DO**: Democratic bots who think the US should NOT continue to support Ukraine against Russia 
- **RS**: Republican bots who think the US should continue to support Ukraine against Russia
- **RO**: Republican bots who think the US should NOT continue to support Ukraine against Russia 

Set `participantCondition` to one of these values for each participant.

## Data Collection

### How Conversations Save

Each participant gets their own CSV file:
- Format: `conversation_{userID}_{invitation_code}.csv`
- Location: Inside the Docker container at `/app/conversations/`

### Download Your Data

Check what files exist:
```bash
ssh vcm@vcm-XXXXX.vm.duke.edu
cd qualtrics-streamlit-chat-app
sudo docker exec -it qualtrics_app_public ls -la /app/conversations/
```

Copy files from Docker to VM:
```bash
sudo docker cp qualtrics_app_public:/app/conversations/ ~/qualtrics-streamlit-chat-app/
```

Download to your computer:
```bash
# From your local computer
scp "vcm@vcm-XXXXX.vm.duke.edu:~/qualtrics-streamlit-chat-app/conversations/*.csv" ~/insert_file_path_here/
```

### CSV Structure

Each conversation file contains:
- `conversation_id`: Unique ID for this chat session
- `condition`: Which bots the participant saw (DS/DO/RS/RO)
- `invitation_code`: The access code they used
- `participant_stance`: Support or Oppose (from p_s parameter)
- `user_id`: Their Qualtrics ResponseID
- `date` and `hour`: When each message was sent
- `content`: The actual message with sender name
- `chatbot_type`: Who sent it (user_message, bot name, or System_Instruction)

## Making Updates

When you change your code:

1. **Push changes:**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

2. **Deploy to VM:**
   ```bash
   ssh vcm@vcm-XXXXX.vm.duke.edu
   cd qualtrics-streamlit-chat-app
   git pull origin main
   sudo docker build -t qualtrics_app .
   sudo docker stop qualtrics_app_public
   sudo docker rm qualtrics_app_public
   sudo docker run -d \
     --name qualtrics_app_public \
     --restart unless-stopped \
     --env-file .env \
     -p 8501:8501 \
     -v ./conversations:/app/conversations \
     qualtrics_app
   ```

## Troubleshooting

**App won't start:**
```bash
sudo docker logs qualtrics_app_public
```

**Can't access from Qualtrics:**
- Verify your VM URL is correct
- Check that port 8501 is accessible
- Test the direct URL first

**No conversation files:**
- Make sure participants are using valid access codes
- Check that all URL parameters are set correctly
- Verify the Docker container is running

**Permission errors:**
```bash
sudo chmod -R 755 ~/qualtrics-streamlit-chat-app/conversations/
```

**SSH connection fails:**
- VCM VMs shut down automatically after inactivity
- Restart your VM from the VCM portal
- Wait a few minutes after restart before connecting

## Project Structure

```
qualtrics-streamlit-chat-app/
├── app.py                          # Main application
├── pyproject.toml                  # Dependencies
├── .env                           # Your API key (create this)
├── .gitignore                     # Excludes conversations/
├── Dockerfile                     # Container setup
├── unique_invite_codes.csv        # Access codes (create this)
├── conversations/                 # Generated data (ignored by git)
└── README.md                      # This file
```

## Security Notes

- Conversation data never goes to GitHub (excluded in `.gitignore`)
- Back up your conversation files regularly
- Don't commit API keys to version control
- Monitor your VM for unusual activity

## Getting Help

- For VCM issues: Contact Duke OIT
- For LiteLLM API access: Contact your research supervisor
- For Qualtrics problems: Check Duke's Qualtrics documentation
- For app bugs: Check the GitHub issues or create a new one

This setup gives you a complete research pipeline from participant recruitment to data analysis. The modular design makes it easy to modify bot personalities or experimental conditions for future studies.