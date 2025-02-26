# Derived from https://github.com/openai/openai-realtime-console. Will integrate with Chainlit when more mature.

import os
import re
import json
import base64
import asyncio
import inspect
import traceback
from datetime import datetime, timezone
from collections import defaultdict

import numpy as np
import websockets
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from chainlit.logger import logger
from chainlit.config import config

from assistant_service import AssistantService


def float_to_16bit_pcm(float32_array):
    """
    Converts a numpy array of float32 amplitude data to a numpy array in int16 format.

    :param float32_array: Numpy array of dtype float32.
    :return: Numpy array of dtype int16.
    """
    int16_array = np.clip(float32_array, -1, 1) * 32767
    return int16_array.astype(np.int16)


def base64_to_array_buffer(base64_string):
    """
    Converts a base64-encoded string to a numpy array buffer of dtype uint8.

    :param base64_string: Base64-encoded string.
    :return: Numpy array of dtype uint8.
    """
    binary_data = base64.b64decode(base64_string)
    return np.frombuffer(binary_data, dtype=np.uint8)


def array_buffer_to_base64(array_buffer):
    """
    Converts a numpy array buffer to a base64-encoded string.
    If the array is float32, it is first converted to 16-bit PCM.

    :param array_buffer: A numpy array (float32, int16, or any type).
    :return: Base64-encoded string.
    """
    if array_buffer.dtype == np.float32:
        # Convert float32 data to int16 PCM before encoding
        array_buffer = float_to_16bit_pcm(array_buffer)
    else:
        # Otherwise just grab its bytes
        array_buffer = array_buffer.tobytes()

    return base64.b64encode(array_buffer).decode("utf-8")


def merge_int16_arrays(left, right):
    """
    Merges two numpy arrays of dtype int16 by concatenating them.

    :param left: Numpy array of int16.
    :param right: Numpy array of int16.
    :return: A new concatenated numpy array of int16.
    :raises ValueError: If either array is not an int16 numpy array.
    """
    if (
        isinstance(left, np.ndarray)
        and left.dtype == np.int16
        and isinstance(right, np.ndarray)
        and right.dtype == np.int16
    ):
        return np.concatenate((left, right))
    else:
        raise ValueError("Both items must be numpy arrays of int16")


class RealtimeEventHandler:
    """
    A generic event dispatcher/handler system.
    Allows registration and asynchronous or synchronous dispatching of event handlers.
    """

    def __init__(self):
        self.event_handlers = defaultdict(list)

    def on(self, event_name, handler):
        """
        Register a handler for a specific event name.

        :param event_name: The event name string (e.g. "server.*", "client.*").
        :param handler: A callable to be triggered upon the event.
        """
        self.event_handlers[event_name].append(handler)

    def clear_event_handlers(self):
        """
        Clear all registered event handlers.
        """
        self.event_handlers = defaultdict(list)

    def dispatch(self, event_name, event):
        """
        Dispatch an event to all handlers that are registered under event_name.
        If the handler is a coroutine, it is scheduled with create_task.
        Otherwise, it is called directly.

        :param event_name: The event name.
        :param event: The event data (usually a dictionary).
        """
        for handler in self.event_handlers[event_name]:
            if inspect.iscoroutinefunction(handler):
                asyncio.create_task(handler(event))
            else:
                handler(event)

    async def wait_for_next(self, event_name):
        """
        Wait (async) for the next occurrence of a particular event name,
        and return that event's data once it arrives.

        :param event_name: The event name to wait for.
        :return: The event data.
        """
        future = asyncio.Future()

        def handler(event):
            if not future.done():
                future.set_result(event)

        self.on(event_name, handler)
        return await future


class RealtimeAPI(RealtimeEventHandler):
    """
    Handles the low-level connection to the Realtime WebSocket API for
    Azure-based or OpenAI-based streaming events. Inherits from RealtimeEventHandler
    for dispatching received events.
    """

    def __init__(self):
        super().__init__()

        # Default to OpenAI's URL if no environment variable is set, though Azure usage is typical
        self.default_url = "wss://api.openai.com/v1/realtime"

        # Azure environment variables
        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        if endpoint.startswith("https"):
            endpoint = endpoint.replace("https://", "wss://")
        self.url = endpoint
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.credentials = DefaultAzureCredential()
        self.acquire_token = get_bearer_token_provider(
            self.credentials, "https://cognitiveservices.azure.com/.default"
        )

        # API version and deployment for Azure
        self.api_version = "2024-10-01-preview"
        self.azure_deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        self.ws = None

    def is_connected(self):
        """
        Checks if the WebSocket connection is currently established.
        """
        return self.ws is not None

    def log(self, *args):
        """
        Helper for logging with a consistent prefix.
        """
        logger.debug(f"[Websocket/{datetime.utcnow().isoformat()}]", *args)

    async def connect(
        self,
        model=None,
    ):
        """
        Establishes a WebSocket connection to the specified model.

        :param model: Model name or deployment name to connect to.
        :raises Exception: If already connected or if connection fails.
        """
        if not model:
            model = self.azure_deployment

        if self.is_connected():
            raise Exception("Already connected")
        headers = (
            {"api-key": self.api_key}
            if self.api_key != ""
            else {"Authorization": f"Bearer {self.acquire_token()}"}
        )
        self.ws = await websockets.connect(
            f"{self.url}/openai/realtime?api-version={self.api_version}&deployment={model}",
            additional_headers=headers,
        )
        self.log(f"Connected to {self.url}")
        asyncio.create_task(self._receive_messages())

    async def _receive_messages(self):
        """
        Continuously listens for incoming messages on the WebSocket,
        dispatching them through the event system.
        """
        async for message in self.ws:
            event = json.loads(message)
            if event["type"] == "error":
                logger.error("ERROR", message)

            self.log("received:", event)
            self.dispatch(f"server.{event['type']}", event)
            self.dispatch("server.*", event)

    async def send(self, event_name, data=None):
        """
        Sends a message/event over the WebSocket to the server.

        :param event_name: The event name/type to send.
        :param data: The event payload (must be a dictionary).
        :raises Exception: If the WebSocket is not connected or the data is not a dictionary.
        """
        if not self.is_connected():
            raise Exception("RealtimeAPI is not connected")

        data = data or {}
        if not isinstance(data, dict):
            raise Exception("data must be a dictionary")

        event = {"event_id": self._generate_id("evt_"), "type": event_name, **data}
        self.dispatch(f"client.{event_name}", event)
        self.dispatch("client.*", event)
        self.log("sent:", event)

        await self.ws.send(json.dumps(event))

    def _generate_id(self, prefix):
        """
        Generates a simple event or item ID using the current timestamp.

        :param prefix: A prefix string (e.g. "evt_", "item_").
        :return: A string ID.
        """
        return f"{prefix}{int(datetime.utcnow().timestamp() * 1000)}"

    async def disconnect(self):
        """
        Closes the WebSocket connection and sets internal state to None.
        """
        if self.ws:
            await self.ws.close()
            self.ws = None
            self.log(f"Disconnected from {self.url}")


class RealtimeConversation:
    """
    Tracks and manages conversation items, responses, and state for real-time
    transcriptions, audio data, and messages. Acts as an in-memory store for
    in-progress and completed conversation elements.

    The class defines a mapping of event types to processing methods, which
    manipulate local conversation state accordingly.
    """

    default_frequency = config.features.audio.sample_rate

    EventProcessors = {
        "conversation.item.created": lambda self, event: self._process_item_created(
            event
        ),
        "conversation.item.truncated": lambda self, event: self._process_item_truncated(
            event
        ),
        "conversation.item.deleted": lambda self, event: self._process_item_deleted(
            event
        ),
        "conversation.item.input_audio_transcription.completed": (
            lambda self, event: self._process_input_audio_transcription_completed(event)
        ),
        "input_audio_buffer.speech_started": lambda self,
        event: self._process_speech_started(event),
        "input_audio_buffer.speech_stopped": (
            lambda self, event, input_audio_buffer: self._process_speech_stopped(
                event, input_audio_buffer
            )
        ),
        "response.created": lambda self, event: self._process_response_created(event),
        "response.output_item.added": lambda self,
        event: self._process_output_item_added(event),
        "response.output_item.done": lambda self, event: self._process_output_item_done(
            event
        ),
        "response.content_part.added": lambda self,
        event: self._process_content_part_added(event),
        "response.audio_transcript.delta": lambda self,
        event: self._process_audio_transcript_delta(event),
        "response.audio.delta": lambda self, event: self._process_audio_delta(event),
        "response.text.delta": lambda self, event: self._process_text_delta(event),
        "response.function_call_arguments.delta": (
            lambda self, event: self._process_function_call_arguments_delta(event)
        ),
    }

    def __init__(self):
        self.clear()

    def clear(self):
        """
        Resets internal conversation state, clearing all items, responses, and queued data.
        """
        self.item_lookup = {}
        self.items = []
        self.response_lookup = {}
        self.responses = []
        self.queued_speech_items = {}
        self.queued_transcript_items = {}
        self.queued_input_audio = None

    def queue_input_audio(self, input_audio):
        """
        Temporarily store an input audio buffer for association with a new user message item.
        """
        self.queued_input_audio = input_audio

    def process_event(self, event, *args):
        """
        Routes an incoming event through the appropriate event processor
        (defined in EventProcessors). Returns the processed item and any delta.

        :param event: Event dictionary with a "type" key.
        :return: (item, delta) where item is the modified or created item, and
                 delta is additional data gleaned from the event (e.g. transcript).
        :raises Exception: If no processor is found for the event type.
        """
        event_processor = self.EventProcessors.get(event["type"])
        if not event_processor:
            raise Exception(f"Missing conversation event processor for {event['type']}")
        return event_processor(self, event, *args)

    def get_item(self, id):
        """
        Retrieve an item by its ID from the item lookup.

        :param id: Item ID.
        :return: The item dictionary or None if not found.
        """
        return self.item_lookup.get(id)

    def get_items(self):
        """
        Get a shallow copy of the list of items in the conversation.
        """
        return self.items[:]

    # ------------------------------
    # Event Processor Implementations
    # ------------------------------

    def _process_item_created(self, event):
        item = event["item"]
        new_item = item.copy()

        # If this item has not been seen before, add it to the lookup
        if new_item["id"] not in self.item_lookup:
            self.item_lookup[new_item["id"]] = new_item
            self.items.append(new_item)

        # Add a 'formatted' key to store different derived data
        new_item["formatted"] = {"audio": [], "text": "", "transcript": ""}

        # If there's queued speech for this item, attach it
        if new_item["id"] in self.queued_speech_items:
            new_item["formatted"]["audio"] = self.queued_speech_items[new_item["id"]][
                "audio"
            ]
            del self.queued_speech_items[new_item["id"]]

        # Accumulate any text content that was part of this item
        if "content" in new_item:
            text_content = [
                c for c in new_item["content"] if c["type"] in ["text", "input_text"]
            ]
            for content in text_content:
                new_item["formatted"]["text"] += content["text"]

        # If there's queued transcript data for this item, attach it
        if new_item["id"] in self.queued_transcript_items:
            new_item["formatted"]["transcript"] = self.queued_transcript_items[
                new_item["id"]
            ]["transcript"]
            del self.queued_transcript_items[new_item["id"]]

        # Define status and/or additional fields depending on the item type
        if new_item["type"] == "message":
            if new_item["role"] == "user":
                new_item["status"] = "completed"
                if self.queued_input_audio:
                    # If we had queued input audio, attach it and reset the queue
                    new_item["formatted"]["audio"] = self.queued_input_audio
                    self.queued_input_audio = None
            else:
                new_item["status"] = "in_progress"

        elif new_item["type"] == "function_call":
            new_item["formatted"]["tool"] = {
                "type": "function",
                "name": new_item["name"],
                "call_id": new_item["call_id"],
                "arguments": "",
            }
            new_item["status"] = "in_progress"

        elif new_item["type"] == "function_call_output":
            new_item["status"] = "completed"
            new_item["formatted"]["output"] = new_item["output"]

        return new_item, None

    def _process_item_truncated(self, event):
        item_id = event["item_id"]
        audio_end_ms = event["audio_end_ms"]
        item = self.item_lookup.get(item_id)

        if not item:
            raise Exception(f'item.truncated: Item "{item_id}" not found')

        end_index = (audio_end_ms * self.default_frequency) // 1000

        # Truncate transcript and audio
        item["formatted"]["transcript"] = ""
        item["formatted"]["audio"] = item["formatted"]["audio"][:end_index]

        return item, None

    def _process_item_deleted(self, event):
        item_id = event["item_id"]
        item = self.item_lookup.get(item_id)

        if not item:
            raise Exception(f'item.deleted: Item "{item_id}" not found')

        del self.item_lookup[item["id"]]
        self.items.remove(item)

        return item, None

    def _process_input_audio_transcription_completed(self, event):
        item_id = event["item_id"]
        content_index = event["content_index"]
        transcript = event["transcript"] or ""
        formatted_transcript = transcript if transcript else " "

        item = self.item_lookup.get(item_id)
        if not item:
            # If the item isn't yet in memory, queue up its transcript
            self.queued_transcript_items[item_id] = {"transcript": formatted_transcript}
            return None, None

        # Adjust item to reflect transcription completion
        item["type"] = "conversation.item.input_audio_transcription.completed"
        item["content"][content_index]["transcript"] = transcript
        item["formatted"]["transcript"] = formatted_transcript

        return item, {"transcript": transcript}

    def _process_speech_started(self, event):
        """
        Handler for beginning of speech in the input audio buffer.
        """
        item_id = event["item_id"]
        audio_start_ms = event["audio_start_ms"]
        self.queued_speech_items[item_id] = {"audio_start_ms": audio_start_ms}
        return None, None

    def _process_speech_stopped(self, event, input_audio_buffer):
        """
        Handler for end of speech in the input audio buffer.
        Associates the captured audio segment to the relevant item.
        """
        item_id = event["item_id"]
        audio_end_ms = event["audio_end_ms"]
        speech = self.queued_speech_items[item_id]
        speech["audio_end_ms"] = audio_end_ms

        if input_audio_buffer:
            start_index = (speech["audio_start_ms"] * self.default_frequency) // 1000
            end_index = (speech["audio_end_ms"] * self.default_frequency) // 1000
            speech["audio"] = input_audio_buffer[start_index:end_index]

        return None, None

    def _process_response_created(self, event):
        response = event["response"]

        if response["id"] not in self.response_lookup:
            self.response_lookup[response["id"]] = response
            self.responses.append(response)

        return None, None

    def _process_output_item_added(self, event):
        response_id = event["response_id"]
        item = event["item"]
        response = self.response_lookup.get(response_id)

        if not response:
            raise Exception(
                f'response.output_item.added: Response "{response_id}" not found'
            )

        response["output"].append(item["id"])
        return None, None

    def _process_output_item_done(self, event):
        item = event["item"]

        if not item:
            raise Exception('response.output_item.done: Missing "item"')

        found_item = self.item_lookup.get(item["id"])
        if not found_item:
            raise Exception(f'response.output_item.done: Item "{item["id"]}" not found')

        found_item["status"] = item["status"]
        return found_item, None

    def _process_content_part_added(self, event):
        item_id = event["item_id"]
        part = event["part"]
        item = self.item_lookup.get(item_id)

        if not item:
            raise Exception(f'response.content_part.added: Item "{item_id}" not found')

        item["content"].append(part)
        return item, None

    def _process_audio_transcript_delta(self, event):
        item_id = event["item_id"]
        content_index = event["content_index"]
        delta = event["delta"]
        item = self.item_lookup.get(item_id)

        if not item:
            raise Exception(
                f'response.audio_transcript.delta: Item "{item_id}" not found'
            )

        item["content"][content_index]["transcript"] += delta
        item["formatted"]["transcript"] += delta

        return item, {"transcript": delta}

    def _process_audio_delta(self, event):
        item_id = event["item_id"]
        content_index = event["content_index"]
        delta = event["delta"]
        item = self.item_lookup.get(item_id)

        if not item:
            logger.debug(f'response.audio.delta: Item "{item_id}" not found')
            return None, None

        # Convert the base64 chunk to a bytes object
        array_buffer = base64_to_array_buffer(delta)
        append_values = array_buffer.tobytes()

        # Merge or append audio here if needed.
        # item['formatted']['audio'] = merge_int16_arrays(item['formatted']['audio'], some_int16_buffer)

        return item, {"audio": append_values}

    def _process_text_delta(self, event):
        item_id = event["item_id"]
        content_index = event["content_index"]
        delta = event["delta"]
        item = self.item_lookup.get(item_id)

        if not item:
            raise Exception(f'response.text.delta: Item "{item_id}" not found')

        item["content"][content_index]["text"] += delta
        item["formatted"]["text"] += delta

        return item, {"text": delta}

    def _process_function_call_arguments_delta(self, event):
        item_id = event["item_id"]
        delta = event["delta"]
        item = self.item_lookup.get(item_id)

        if not item:
            raise Exception(
                f'response.function_call_arguments.delta: Item "{item_id}" not found'
            )

        item["arguments"] += delta
        item["formatted"]["tool"]["arguments"] += delta

        return item, {"arguments": delta}


class RealtimeClient(RealtimeEventHandler):
    """
    High-level client that coordinates the RealtimeAPI connection and
    RealtimeConversation state. Provides methods to manage sessions, tools,
    and conversation flow (e.g., sending messages, handling function calls).

    Inherits from RealtimeEventHandler to dispatch 'realtime.event' and
    'conversation' events to external listeners.
    """

    def __init__(self, system_prompt: str):
        super().__init__()
        self.system_prompt = system_prompt
        self.default_session_config = {
            "modalities": ["text", "audio"],
            "instructions": self.system_prompt,
            "voice": "shimmer",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": {"type": "server_vad"},
            "tools": [],
            "tool_choice": "auto",
            "temperature": 0.8,
            "max_response_output_tokens": 4096,
        }

        # Additional config data
        self.session_config = {}
        self.transcription_models = [{"model": "whisper-1"}]
        self.default_server_vad_config = {
            "type": "server_vad",
            "threshold": 0.8,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 200,
        }

        # Realtime API wrapper and conversation state
        self.realtime = RealtimeAPI()
        self.assistant = AssistantService()
        self.conversation = RealtimeConversation()

        # Internal initialization
        self._reset_config()
        self._add_api_event_handlers()

    def _reset_config(self):
        """
        Resets session flags and merges default session config.
        """
        self.session_created = False
        self.tools = {}
        self.session_config = self.default_session_config.copy()
        self.input_audio_buffer = bytearray()
        return True

    def _add_api_event_handlers(self):
        """
        Registers handlers on the RealtimeAPI for both client and server events.
        """
        # Logging for all events
        self.realtime.on("client.*", self._log_event)
        self.realtime.on("server.*", self._log_event)

        # Session
        self.realtime.on("server.session.created", self._on_session_created)

        # Responses
        self.realtime.on("server.response.created", self._process_event)
        self.realtime.on("server.response.output_item.added", self._process_event)
        self.realtime.on("server.response.content_part.added", self._process_event)

        # Input audio
        self.realtime.on(
            "server.input_audio_buffer.speech_started", self._on_speech_started
        )
        self.realtime.on(
            "server.input_audio_buffer.speech_stopped", self._on_speech_stopped
        )

        # Conversation items
        self.realtime.on("server.conversation.item.created", self._on_item_created)
        self.realtime.on("server.conversation.item.truncated", self._process_event)
        self.realtime.on("server.conversation.item.deleted", self._process_event)
        self.realtime.on(
            "server.conversation.item.input_audio_transcription.completed",
            self._process_event,
        )

        # Audio / text deltas
        self.realtime.on("server.response.audio_transcript.delta", self._process_event)
        self.realtime.on("server.response.audio.delta", self._process_event)
        self.realtime.on("server.response.text.delta", self._process_event)
        self.realtime.on(
            "server.response.function_call_arguments.delta", self._process_event
        )

        # Completion of output items
        self.realtime.on("server.response.output_item.done", self._on_output_item_done)

    # -----------------------------
    # Event Handlers
    # -----------------------------

    def _log_event(self, event):
        """
        Logs any realtime event as a structured dictionary, then dispatches
        a 'realtime.event' for higher-level consumption.
        """
        realtime_event = {
            "time": datetime.utcnow().isoformat(),
            "source": "client" if event["type"].startswith("client.") else "server",
            "event": event,
        }
        self.dispatch("realtime.event", realtime_event)

    def _on_session_created(self, event):
        self.session_created = True

    def _process_event(self, event, *args):
        """
        Passes an event to the RealtimeConversation's process_event to update
        local conversation state. Dispatches 'conversation.updated' if an item changes.
        """
        item, delta = self.conversation.process_event(event, *args)
        if item:
            self.dispatch("conversation.updated", {"item": item, "delta": delta})
        return item, delta

    def _on_speech_started(self, event):
        """
        Called when the server indicates that speech has started in the audio buffer.
        """
        self._process_event(event)
        self.dispatch("conversation.interrupted", event)

    def _on_speech_stopped(self, event):
        """
        Called when the server indicates that speech has stopped in the audio buffer.
        """
        self._process_event(event, self.input_audio_buffer)

    def _on_item_created(self, event):
        """
        Called when a conversation item is created.
        Dispatches 'conversation.item.appended' if the item is new.
        Also checks if the item is 'completed' upon creation (like user messages).
        """
        item, delta = self._process_event(event)
        self.dispatch("conversation.item.appended", {"item": item})
        if item and item["status"] == "completed":
            self.dispatch("conversation.item.completed", {"item": item})

    async def _on_output_item_done(self, event):
        """
        Called when a server indicates an output item is completed.
        If it's a function call, triggers the tool or agent logic.
        """
        item, delta = self._process_event(event)
        if item and item["status"] == "completed":
            self.dispatch("conversation.item.completed", {"item": item})

        if item and item.get("formatted", {}).get("tool"):
            await self._call_tool(item["formatted"]["tool"])

    async def _call_tool(self, tool):
        """
        Executes a tool (function) call, possibly delegating to an Agent in the AssistantService.
        Sends the result back to the conversation as 'function_call_output'.
        """
        try:
            # Convert arguments from JSON
            json_arguments = json.loads(tool["arguments"])
            tool_name = tool["name"]

            # Use the AssistantService to handle tool calls, possibly routing to a different agent
            result = await self.assistant.get_tool_response(
                tool_name=tool_name, parameters=json_arguments, call_id=tool["call_id"]
            )

            # If the tool name suggests switching to a new agent (like "assistantXYZ"),
            # update the session instructions and available tools
            if re.search(r"assistant", tool_name, re.IGNORECASE):
                agent = self.assistant.get_agent(tool_name)
                logger.debug(f"Switching to agent {agent['id']}")
                await self.realtime.send(
                    "session.update",
                    {
                        "session": {
                            # Overwrite system instructions with the agent's system message
                            "instructions": agent["system_message"],
                            # Include additional tools for the new agent
                            "tools": self.assistant.get_tools_for_assistant(tool_name),
                        }
                    },
                )
            else:
                # For a regular tool call, just send the output back
                await self.realtime.send(
                    "conversation.item.create",
                    {
                        "item": {
                            "type": "function_call_output",
                            "call_id": tool["call_id"],
                            "output": json.dumps(result),
                        }
                    },
                )
        except Exception as e:
            logger.error(traceback.format_exc())
            await self.realtime.send(
                "conversation.item.create",
                {
                    "item": {
                        "type": "function_call_output",
                        "call_id": tool["call_id"],
                        "output": json.dumps({"error": str(e)}),
                    }
                },
            )

        # After the tool call or agent swap, signal the creation of a new response
        await self.create_response()

    # -----------------------------
    # Connection / Session Methods
    # -----------------------------

    def is_connected(self):
        """
        Check if the underlying RealtimeAPI is connected.
        """
        return self.realtime.is_connected()

    def reset(self):
        """
        Disconnect and re-initialize. Clears all conversation state.
        """
        self.disconnect()
        self.realtime.clear_event_handlers()
        self._reset_config()
        self._add_api_event_handlers()
        return True

    async def connect(self):
        """
        Establish a RealtimeAPI connection and set the root agent's
        instructions and tools in the session config.
        """
        if self.is_connected():
            raise Exception("Already connected, use .disconnect() first")

        await self.realtime.connect()

        # Set up the root agent and its tools
        root_agent = self.assistant.get_agent("root")
        root_tools = self.assistant.get_tools_for_assistant("root")
        self.session_config.update(
            {
                "instructions": root_agent["system_message"],
                "tools": root_tools,
            }
        )
        await self.update_session()
        return True

    async def wait_for_session_created(self):
        """
        Blocks until the session creation is acknowledged by the server.
        """
        if not self.is_connected():
            raise Exception("Not connected, use .connect() first")

        while not self.session_created:
            await asyncio.sleep(0.001)
        return True

    async def disconnect(self):
        """
        Disconnect from the RealtimeAPI and clear conversation state.
        """
        self.session_created = False
        self.conversation.clear()
        if self.realtime.is_connected():
            await self.realtime.disconnect()

    def get_turn_detection_type(self):
        """
        Returns the 'type' from the current turn detection config.
        """
        return self.session_config.get("turn_detection", {}).get("type")

    # -----------------------------
    # Tool Management
    # -----------------------------

    async def add_tool(self, definition, handler):
        """
        Adds a tool with a given definition and a handler callable.
        Updates the session to include the new tool.

        :param definition: A dictionary describing the tool (must have "name").
        :param handler: The Python function to call when this tool is invoked.
        :raises Exception: If tool definition is invalid or already exists.
        :return: The newly added tool dictionary.
        """
        if not definition.get("name"):
            raise Exception("Missing tool name in definition")

        name = definition["name"]
        if name in self.tools:
            raise Exception(
                f'Tool "{name}" already added. Please use .removeTool("{name}") before trying to add again.'
            )

        if not callable(handler):
            raise Exception(f'Tool "{name}" handler must be a function')

        self.tools[name] = {"definition": definition, "handler": handler}
        await self.update_session()
        return self.tools[name]

    def remove_tool(self, name):
        """
        Removes a tool by name from the session.

        :param name: The tool name.
        :raises Exception: If the tool is not registered.
        """
        if name not in self.tools:
            raise Exception(f'Tool "{name}" does not exist, cannot be removed.')

        del self.tools[name]
        return True

    # -----------------------------
    # Conversation & Session
    # -----------------------------

    async def delete_item(self, id):
        """
        Deletes an item (e.g., a message) from the conversation by its ID.

        :param id: ID of the item to delete.
        """
        await self.realtime.send("conversation.item.delete", {"item_id": id})
        return True

    async def update_session(self, **kwargs):
        """
        Updates the session configuration with any kwargs provided
        and sends the updated session to the server.

        :param kwargs: Session configuration overrides.
        """
        self.session_config.update(kwargs)

        # Merge session tools from self.tools plus any session-configured tools
        use_tools = [
            {**tool_def, "type": "function"}
            for tool_def in self.session_config.get("tools", [])
        ] + [
            {**self.tools[key]["definition"], "type": "function"} for key in self.tools
        ]

        session = {**self.session_config, "tools": use_tools}
        if self.realtime.is_connected():
            await self.realtime.send("session.update", {"session": session})
        return True

    async def create_conversation_item(self, item):
        """
        Creates a new conversation item (e.g., a user message or system message).

        :param item: A dictionary describing the conversation item (type, role, content, etc.).
        """
        await self.realtime.send("conversation.item.create", {"item": item})

    async def send_user_message_content(self, content=[]):
        """
        Creates a user message with the given content and then requests a new response.

        :param content: A list of content parts. For audio, data is base64-encoded.
        """
        if content:
            for c in content:
                if c["type"] == "input_audio":
                    if isinstance(c["audio"], (bytes, bytearray)):
                        c["audio"] = array_buffer_to_base64(c["audio"])

            await self.realtime.send(
                "conversation.item.create",
                {
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": content,
                    }
                },
            )

        await self.create_response()
        return True

    async def append_input_audio(self, array_buffer):
        """
        Appends incoming audio data to the realtime input audio buffer.
        Internally extends self.input_audio_buffer as well.

        :param array_buffer: The raw audio data as a bytearray or numpy array.
        """
        if len(array_buffer) > 0:
            await self.realtime.send(
                "input_audio_buffer.append",
                {
                    "audio": array_buffer_to_base64(np.array(array_buffer)),
                },
            )
            self.input_audio_buffer.extend(array_buffer)

        return True

    async def create_response(self):
        """
        Sends a request to create a new response if turn detection is off
        or any audio data has arrived. This is how the server knows it's time
        for the assistant to respond.
        """
        # If turn detection is disabled and we have audio, commit the buffer first
        if self.get_turn_detection_type() is None and len(self.input_audio_buffer) > 0:
            await self.realtime.send("input_audio_buffer.commit")
            self.conversation.queue_input_audio(self.input_audio_buffer)
            self.input_audio_buffer = bytearray()

        # Then create the response
        await self.realtime.send("response.create")
        return True

    async def cancel_response(self, id=None, sample_count=0):
        """
        Cancels the current or specified response.
        Optionally truncates any existing audio output if sample_count is given.

        :param id: The ID of the item to cancel (e.g., an assistant message).
        :param sample_count: Number of audio samples to keep before truncation.
        :return: A dict with the canceled item if found.
        :raises Exception: If the item is not a message or not from the assistant.
        """
        if not id:
            await self.realtime.send("response.cancel")
            return {"item": None}
        else:
            item = self.conversation.get_item(id)
            if not item:
                raise Exception(f'Could not find item "{id}"')
            if item["type"] != "message":
                raise Exception('Can only cancelResponse messages with type "message"')
            if item["role"] != "assistant":
                raise Exception(
                    'Can only cancelResponse messages with role "assistant"'
                )

            # Cancel the response
            await self.realtime.send("response.cancel")

            # Truncate existing audio in the conversation item
            audio_index = next(
                (i for i, c in enumerate(item["content"]) if c["type"] == "audio"), -1
            )
            if audio_index == -1:
                raise Exception("Could not find audio on item to cancel")

            await self.realtime.send(
                "conversation.item.truncate",
                {
                    "item_id": id,
                    "content_index": audio_index,
                    "audio_end_ms": int(
                        (sample_count / self.conversation.default_frequency) * 1000
                    ),
                },
            )
            return {"item": item}

    # -----------------------------
    # Awaitable Helpers
    # -----------------------------

    async def wait_for_next_item(self):
        """
        Awaits the next newly appended item in the conversation.

        :return: Dictionary with the new item under the "item" key.
        """
        event = await self.wait_for_next("conversation.item.appended")
        return {"item": event["item"]}

    async def wait_for_next_completed_item(self):
        """
        Awaits the next item in the conversation that is marked 'completed'.

        :return: Dictionary with the completed item under the "item" key.
        """
        event = await self.wait_for_next("conversation.item.completed")
        return {"item": event["item"]}
