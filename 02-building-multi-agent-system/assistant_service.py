import json
import re
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AssistantService:
    """A service for managing AI assistants and their interactions.

    This service handles the registration, configuration, and coordination of multiple AI assistants,
    including their tools and inter-assistant communication capabilities. It supports a hierarchical
    structure where assistants can delegate tasks to other assistants.

    Args:
        language (str, optional): The primary language for assistant communications. Defaults to "English".
    """

    def __init__(self, language: str = "English"):
        self.language = language
        self.agents = {}

    def get_tools_for_assistant(self, id):
        """Retrieve all available tools for a specific assistant.

        This method combines the assistant's own tools with other assistants represented as tools,
        enabling inter-assistant communication and task delegation.

        Args:
            id (str): The unique identifier of the assistant

        Returns:
            list: A list of tool definitions including both real tools and other assistants as tools
        """
        # Get the specified agent's tools
        agent_real_tools = self.agents[id]["tools"]

        # Represent other agents as "tools" to allow switching/communication
        other_agents_as_tools = []
        for agent_id, agent_data in self.agents.items():
            if agent_id != id:
                other_agents_as_tools.append(
                    {
                        "name": agent_data["id"],
                        "description": agent_data["description"],
                        "parameters": {"type": "object", "properties": {}},
                        "returns": lambda unused: agent_data["id"],
                    }
                )

        # Combine the real tools and agents-as-tools, then build final definitions
        combined_tools = agent_real_tools + other_agents_as_tools
        tools_definitions = [
            {
                "type": "function",
                "name": tool["name"],
                "parameters": tool["parameters"],
                "description": tool["description"],
            }
            for tool in combined_tools
        ]

        return tools_definitions

    def register_agent(self, agent):
        """Register a new agent in the service.

        This method adds a new agent to the service, formatting its system message
        with the configured language.

        Args:
            agent (dict): Agent configuration including ID, system message, and tools
        """
        # Format the system message with the current service language
        agent["system_message"] = self.format_string(
            agent["system_message"], {"language": self.language}
        )
        # Store the agent in the agents dictionary
        self.agents[agent["id"]] = agent

    def get_agent(self, id):
        """Retrieve an agent by its ID.

        Args:
            id (str): The unique identifier of the agent

        Returns:
            dict: The agent configuration if found, None otherwise
        """
        return self.agents.get(id)

    def register_root_agent(self, root_agent):
        """Register the root agent and configure inter-agent communication.

        This method:
        1. Adds a tool to all other agents to switch back to the root agent
        2. Registers the root agent both under its ID and under "root"
        3. Formats the root agent's system message with the configured language

        Args:
            root_agent (dict): Root agent configuration including ID, system message, and tools
        """
        # Ensure every other agent has a tool to switch back to the root agent
        for agent_id, agent_data in self.agents.items():
            agent_data["tools"].append(
                {
                    "name": root_agent["id"],
                    "description": (
                        f"If the customer asks any question that is outside of "
                        f"your work scope, DO use this to switch back to "
                        f"{root_agent['id']}."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                    "returns": lambda unused: root_agent["id"],
                }
            )

        # Format and register the root agent's system message
        root_agent["system_message"] = self.format_string(
            root_agent["system_message"], {"language": self.language}
        )

        # Register the root agent under both its own ID and "root"
        self.agents["root"] = self.agents[root_agent["id"]] = root_agent

    async def get_tool_response(self, tool_name, parameters, call_id):
        """Execute a tool or switch to another agent based on the tool name.

        This method handles both actual tool execution and inter-agent switching.
        For agent switches, it configures the new agent's session with appropriate
        tools and instructions.

        Args:
            tool_name (str): Name of the tool to execute or agent to switch to
            parameters (dict): Parameters for the tool execution
            call_id (str): Unique identifier for the tool call

        Returns:
            dict: Tool execution result or agent switch configuration
        """
        print(
            f"getToolResponse: tool_name={tool_name}, parameters={parameters}, call_id={call_id}"
        )

        # Collect all tools from all agents
        all_tools = [
            tool for agent_data in self.agents.values() for tool in agent_data["tools"]
        ]
        # Also collect all agents as "tools"
        all_agents_as_tools = [
            {
                "name": agent_data["id"],
                "description": agent_data["description"],
                "parameters": {"type": "object", "properties": {}},
                "returns": lambda unused: agent_data["id"],
            }
            for agent_data in self.agents.values()
        ]

        # Merge into one list for searching
        all_available_tools = all_tools + all_agents_as_tools

        # Find the requested tool by name
        tool = next((t for t in all_available_tools if t["name"] == tool_name), None)

        # If the tool name indicates a switch to another agent
        if re.search(r"assistant", tool_name, re.IGNORECASE):
            target_agent = self.agents[tool_name]
            logger.debug(f"Switching to agent {target_agent['id']}")

            # Construct a session update message for switching context
            config_message = {
                "type": "session.update",
                "session": {
                    "turn_detection": {"type": "server_vad"},
                    "instructions": self.format_string(
                        target_agent["system_message"], {"language": self.language}
                    ),
                    # Include all relevant tools for the target agent
                    "tools": self.get_tools_for_assistant(tool_name),
                },
            }
            return config_message

        # Otherwise, we are executing a normal tool
        content = tool["returns"](parameters)
        logger.debug(f"Tool {tool_name} returned content: {content}")

        response = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": content,
            },
        }
        return response

    def format_string(self, text, params):
        """Format a string with given parameters.

        Args:
            text (str): The template string to format
            params (dict): Parameters to insert into the template

        Returns:
            str: The formatted string
        """
        # This can be extended to provide common instructions or guidelines
        return text.format(**params)
