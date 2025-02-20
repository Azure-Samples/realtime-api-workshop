# Workshop: Building Multi-Agent Voice Systems

Welcome to part 2 of our voice assistant workshop series! Now that you've learned about function calling, let's explore how multiple specialized AI agents can work together to create a complete customer service system.

## Quick Start

### Prerequisites
- Completed the Function Calling workshop (01-getting-started-function-calling)
- Azure OpenAI API access with real-time capabilities
- Python 3.8 or higher

### Setting Up

#### Environment Variables
Use the same `.env` file from the previous workshop:
```bash
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_DEPLOYMENT=your_deployment_name
```

#### Installation

Choose your preferred installation method:

##### Option 1: Using uv (Recommended)
```bash
cd 02-building-multi-agent-system
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
   cd 02-building-multi-agent-system
   chainlit run chat.py
   ```

## Understanding Our Multi-Agent System

Our customer service system consists of four specialized agents:

1. **Root Assistant (Greeter)**
   - Acts as the first point of contact
   - Routes inquiries to specialized agents
   - Manages conversation flow and closure

2. **Technical Support**
   - Handles service issues and troubleshooting
   - Checks service status and telemetry
   - Provides common solutions for internet and mobile services

3. **Sales Assistant**
   - Provides product information and pricing
   - Handles upgrades and additional services
   - Manages product SKUs and bundles

4. **Activation Assistant**
   - Processes service activation requests
   - Collects necessary customer information
   - Handles SIM card replacements

## Hands-on Exercises

### Exercise 1: Understanding Agent Routing

Let's see how the Root Assistant routes queries to specialists:

1. Start the application and try these queries:
   ```
   "Hello, I'm having trouble with my internet connection"
   ```
   Watch how the Root Assistant:
   - Greets you professionally
   - Routes you to Technical Support
   - Technical Support then checks service status and provides solutions

2. Try a sales inquiry:
   ```
   "What internet packages do you offer?"
   ```
   Observe how:
   - Root Assistant identifies this as a sales query
   - Sales Assistant provides specific product details
   - Information includes prices and package features

### Exercise 2: Complex Service Scenarios

Let's explore scenarios requiring multiple agents:

1. Try this service activation flow:
   ```
   "I want to sign up for the All-in-One Bundle"
   ```
   Notice how:
   - Sales Assistant provides bundle details
   - Activation Assistant collects required information:
     - Phone number
     - Home address
   - Root Assistant manages the conversation flow

2. Test a technical issue that may lead to activation:
   ```
   "My SIM card isn't working"
   ```
   Watch the workflow:
   - Technical Support runs diagnostics
   - If replacement needed, routes to Activation
   - Activation Assistant handles replacement process

### Exercise 3: Add a Billing Assistant (Challenge)

#### Goal
Create a new Billing Assistant that helps customers understand their charges and billing history. The assistant should:
1. Check current outstanding balance and highlight any international call overcharges
2. Look up historical invoice information for any given month

#### Requirements
- Create a new agent with appropriate system message and description
- Implement two tools:
  1. A tool to check current balance that shows:
     - Total outstanding amount
     - Any international call overcharges
     - Due date
  2. A tool to retrieve monthly invoices that shows:
     - Total amount
     - Breakdown of charges
     - Statement date
- Register the agent properly with the system
- Ensure voice-friendly responses

#### Your Task
Try implementing this agent on your own! Create a new file `agents/billing.py` and implement the billing assistant. Think about:
- What should the system message contain?
- How should the tools be structured?
- What parameters are needed?
- What should the return values look like?

Test your implementation with queries like:
```
"What's my current balance?"
"Can you tell me about my international call charges?"
"How much was my bill for December?"
```

#### Solution
If you'd like to see a complete solution, here's how you could implement the Billing Assistant:

1. Create `agents/billing.py`:
```python
billing_assistant = {
    "id": "Assistant_BillingAssistant",
    "name": "Billing Support",
    "description": """Call this if:
        - Customer wants to check their current balance
        - Customer needs information about past invoices
        - Customer has questions about charges
        DO NOT CALL IF:
        - Technical support needed
        - Sales inquiries""",
    "system_message": """You are a billing support agent handling customer inquiries about balances and invoices.
    Keep sentences short and simple, suitable for voice conversation.
    
    Your tasks:
    - Check current outstanding balances
    - Explain any international call overcharges
    - Provide historical invoice information
    - Help customers understand their charges
    
    Make sure to:
    - Be professional and empathetic
    - Verify customer identity before sharing details
    - Explain charges clearly
    - Note that international calls may cause higher than usual charges""",
    "tools": [
        {
            "name": "check_outstanding_balance",
            "description": "Check customer's current outstanding balance and any overcharges from international calls",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"}
                },
                "required": ["account_id"]
            },
            "returns": lambda input: {
                "balance": "€80.75",
                "international_calls_charge": "€45.50",
                "due_date": "2025-02-01"
            }
        },
        {
            "name": "get_monthly_invoice",
            "description": "Get the invoice amount for a specific month",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"},
                    "month": {
                        "type": "string",
                        "description": "Month in YYYY-MM format"
                    }
                },
                "required": ["account_id", "month"]
            },
            "returns": lambda input: {
                "total_amount": "€85.25",
                "base_charges": "€40.00",
                "usage_charges": "€45.25",
                "statement_date": f"{input['month']}-15"
            }
        }
    ]
}
```

2. Update `chat.py` to import and register the new assistant:
```python
# Import the new billing assistant
from agents.billing import billing_assistant

async def setup_openai_realtime():
    # ... existing setup code ...

    # Register all agents with the realtime client
    openai_realtime.assistant.register_agent(activation_assistant)
    openai_realtime.assistant.register_agent(sales_assistant)
    openai_realtime.assistant.register_agent(technical_assistant)
    openai_realtime.assistant.register_agent(billing_assistant)  # Add the new billing assistant
    
    # Always register the root agent last
    # This ensures every agent knows about each other and the path to the root agent
    openai_realtime.assistant.register_root_agent(root_assistant)
```

Key aspects of this solution:
- Clear description of when to use (and not use) this agent
- Voice-optimized system message with clear tasks
- Two focused tools with specific purposes
- Proper error handling and customer verification
- Professional and empathetic tone
- Proper registration with the multi-agent system

## Troubleshooting

Common issues and solutions:

1. **Agent Communication**
   - Ensure Root Assistant's routing logic is working
   - Check if specialized agents stay within their roles
   - Verify agent handoffs are smooth

2. **Voice Interaction**
   - Keep responses concise and clear
   - Use professional language
   - Maintain conversation context

## Next Steps

Now that you've built a multi-agent system with specialized assistants, you can enhance it further by:
1. Adding more specialized agents (e.g., Retention Specialist)
2. Implementing complex workflows involving multiple agents
3. Enhancing agent responses for better voice interaction

### Coming Up: Voice RAG Workshop
In the next workshop, we'll explore how to ground your voice assistants with real documents and data. You'll learn how to:
- Add document retrieval capabilities to your agents
- Use RAG (Retrieval Augmented Generation) to provide accurate, document-based responses
- Handle queries about specific documents or knowledge bases
- Maintain voice-friendly responses while accessing detailed information

Continue to [Voice RAG Workshop](../03-voice-rag/README.md) to get started!
