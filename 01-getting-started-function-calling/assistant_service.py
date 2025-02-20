"""Service for managing AI assistants."""

import json
import re
import logging

# ---------------------------
# LOGGER SETUP
# ---------------------------

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ---------------------------
# ASSISTANT SERVICE CLASS
# ---------------------------


class AssistantService:
    """
    A service for managing AI assistants and their interactions.

    This class allows for:
    - Registration of different 'agent' objects, each representing
      an AI assistant with specific capabilities and tools.
    - Retrieval of agents by their IDs.
    - Retrieval of an agent's tools.
    - Execution of a specified tool, with parameters,
      to produce a result within a conversation context.

    Attributes:
        language (str): The default language for the service (e.g., "English").
        agents (dict): A dictionary holding all registered agents, keyed by their IDs.
    """

    def __init__(self, language: str = "English"):
        """
        Initialize an AssistantService instance.

        Args:
            language (str, optional): The default language for the service.
                                      Defaults to "English".
        """
        self.language = language
        self.agents = {}

    # ---------------------------
    # AGENT TOOL RETRIEVAL
    # ---------------------------

    def get_tools_for_assistant(self, id: str):
        """
        Retrieve a list of tools for a specific assistant.

        Args:
            id (str): The unique identifier of the assistant.

        Returns:
            list: A list of tool definitions (dictionaries) containing
                  'type', 'name', 'parameters', and 'description'.
        """
        return [
            {
                "type": "function",
                "name": tool["name"],
                "parameters": tool["parameters"],
                "description": tool["description"],
            }
            for tool in self.agents[id]["tools"]
        ]

    # ---------------------------
    # AGENT REGISTRATION
    # ---------------------------

    def register_agent(self, agent: dict):
        """
        Register a new agent in the service. The agent's system message
        is formatted based on the service language, and the agent is also
        stored as the root agent for compatibility.

        Args:
            agent (dict): A dictionary representing the agent's configuration.
                          Must include 'id', 'tools', and 'system_message'.
        """
        agent["system_message"] = self.format_string(
            agent["system_message"], {"language": self.language}
        )
        self.agents[agent["id"]] = agent
        # Also register as root for compatibility
        self.agents["root"] = agent

    # ---------------------------
    # AGENT RETRIEVAL
    # ---------------------------

    def get_agent(self, id: str):
        """
        Retrieve an agent by its ID.

        Args:
            id (str): The unique identifier of the agent.

        Returns:
            dict or None: The agent configuration if found, otherwise None.
        """
        return self.agents.get(id)

    # ---------------------------
    # TOOL EXECUTION
    # ---------------------------

    async def get_tool_response(self, tool_name: str, parameters: dict, call_id: str):
        """
        Execute a tool function and return its response for a given conversation call.

        Args:
            tool_name (str): The name of the tool to execute.
            parameters (dict): Parameters required for the tool's execution.
            call_id (str): A unique identifier for the current conversation turn.

        Returns:
            dict or None: A structured response containing the tool output, or
                          None if the specified tool cannot be found.
        """
        logger.debug(
            f"getToolResponse: tool_name={tool_name}, parameters={parameters}, call_id={call_id}"
        )

        # Search for the tool in any registered agent
        tool = None
        for agent in self.agents.values():
            for t in agent["tools"]:
                if t["name"] == tool_name:
                    tool = t
                    break
            if tool:
                break

        # Handle the case where the tool was not found
        if not tool:
            logger.error(f"Tool {tool_name} not found")
            return None

        # Execute the tool
        content = tool["returns"](parameters)
        logger.debug(f"Tool {tool_name} returned content: {content}")

        # Construct the response
        response = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": content,
            },
        }
        return response

    # ---------------------------
    # HELPER METHODS
    # ---------------------------

    def format_string(self, text: str, params: dict):
        """
        Safely format a string using the given parameters.

        Args:
            text (str): The text to format.
            params (dict): A dictionary of key-value pairs for formatting.

        Returns:
            str: The formatted text, or the original text if formatting is not possible.
        """
        if not text:
            return text
        return text.format(**params)
