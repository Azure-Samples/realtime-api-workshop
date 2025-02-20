# Workshop: Building a Realtime Voice Assistant with Chainlit

Welcome to our workshop on creating a **voice-enabled assistant** using [Chainlit](https://docs.chainlit.io/) and Azure OpenAI's Realtime API. In this workshop, you'll learn how to build an AI assistant that can:
- Accept **live audio** and **text** input from users
- Provide real-time voice and text responses
- Use tools to perform actions and gather information

## Quick Start

### Prerequisites
- Azure OpenAI API access with real-time capabilities enabled
- Python 3.8 or higher

### Setting Up

#### Environment Variables
Create a `.env` file with your Azure OpenAI credentials:
```bash
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_DEPLOYMENT=your_deployment_name
```

#### Installation

Choose one of the following methods to run the demo:

##### Option 1: Using uv (Recommended)
[uv](https://github.com/astral-sh/uv) is a fast Python package installer and runner. If you haven't installed it yet:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then navigate to the workshop directory and run the chat application:
```bash
cd 01-getting-started-function-calling
uv run chainlit run chat.py
```

##### Option 2: Using pip
1. Install dependencies from the root folder of the repository: (Skip this step if you have done azd up from the root folder)
   ```bash
   # From the root folder of the repository
   pip install -r requirements.txt
   ```

2. Navigate to the workshop directory and start the chat application:
   ```bash
   cd 01-getting-started-function-calling
   chainlit run chat.py
   ```

The application will start on `http://localhost:8000` by default.

## Understanding the Code

The workshop code is organized into three main components:

### 1. Main Application (`chat.py`)
The core of our application that:
- Initializes Chainlit for the web interface
- Sets up the realtime client for audio handling
- Defines our technical support assistant and its tools
- Manages the conversation flow

Here's how we define our assistant's tools:
```python
main_assistant = {
    "id": "tech_support",
    "name": "Technical Support",
    "description": "A technical support assistant that helps with service issues.",
    "tools": [
        {
            "name": "check_usage",
            "description": "Check customer's service usage data",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"}
                },
                "required": ["customer_id"]
            }
        },
        {
            "name": "check_service_status",
            "description": "Check if there are any known service issues",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"}
                },
                "required": ["service"]
            }
        }
    ]
}
```

### 2. Assistant Service (`assistant_service.py`)
Manages our AI assistants and their tools:
- Registers and configures assistants
- Maintains the tool registry
- Handles function execution

### 3. Realtime Client (`realtime2.py`)
Handles the low-level WebSocket functionality:
- Manages connections to Azure OpenAI
- Streams audio data
- Processes conversation events

## Hands-on Exercises

### Exercise 1: Basic Voice Interaction
Let's start by testing the voice capabilities:

1. Start the application and open it in your browser
2. Click the microphone button
3. Try these queries:
   ```
   "Hello, can you help me with my internet connection?"
   "What services can you help me with?"
   "Can you check if there are any problems with the internet?"
   ```
4. Observe:
   - Real-time speech transcription
   - Natural voice responses
   - Conversation context maintenance

### Exercise 2: Testing Built-in Tools
The assistant comes with two tools. Let's test them:

1. Check Service Status:
   ```
   "Is there any problem with the internet service?"
   "What's the status of the mobile network?"
   ```

2. Check Usage Data:
   ```
   "How much data have I used this month?"
   "Am I close to my usage limit?"
   ```

3. Observe how the assistant:
   - Automatically chooses when to use tools
   - Incorporates tool responses naturally
   - Maintains context between queries

### Exercise 3: Add a Mobile Configuration Tool
Let's add a tool that helps users configure their mobile devices for internet access:

1. Open `chat.py` and find the `main_assistant` configuration
2. Add this new tool to the `tools` list:
```python
{
    "name": "get_mobile_internet_config",
    "description": "Get instructions for configuring internet on a mobile device",
    "parameters": {
        "type": "object",
        "properties": {
            "device_type": {
                "type": "string",
                "description": "Type of mobile device",
                "enum": ["iPhone", "Android"]
            }
        },
        "required": ["device_type"]
    },
    "returns": lambda input: {
        "steps": (
            # iPhone configuration
            ["Go to Settings", "Tap Cellular", "Enable Cellular Data", "Tap Cellular Data Options", "Enable 5G (if available)"]
            if input["device_type"] == "iPhone"
            # Android configuration
            else ["Open Settings", "Tap Network & Internet", "Tap Mobile Network", "Enable Mobile Data", "Select Preferred Network Type"]
        ),
        "apn_settings": {
            "name": "Internet",
            "apn": "internet"
        }
    }
}
```

3. Restart the application and try these queries:
   ```
   "How do I set up internet on my iPhone?"
   "Can you help me configure my Android phone for mobile data?"
   "What are the APN settings for my device?"
   ```

4. Notice how:
   - The assistant provides device-specific instructions
   - Configuration steps are clear and easy to follow
   - Technical details like APN settings are included when relevant

## Troubleshooting

Common issues and solutions:

1. **No audio input/output**
   - Check browser permissions for microphone access
   - Verify audio device settings

2. **Connection errors**
   - Confirm Azure OpenAI credentials are correct
   - Check internet connectivity
   - Verify deployment name is valid

## Next Steps

Now that you've built a voice-enabled AI assistant, you can:
1. Add more tools to handle different scenarios
2. Modify the system message to change the assistant's personality
3. Experiment with different voice settings
4. Explore the multi-agent system workshop to learn about agent collaboration
