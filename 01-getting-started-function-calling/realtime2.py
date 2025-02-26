# Derived from https://github.com/openai/openai-realtime-console. Will integrate with Chainlit when more mature.

import os
import asyncio
import inspect
import re
import numpy as np
import json
import base64
import traceback

from datetime import datetime, timezone
from collections import defaultdict

import websockets
from chainlit.logger import logger
from chainlit.config import config

from assistant_service import AssistantService
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


def float_to_16bit_pcm(float32_array):
    """
    Converts a numpy array of float32 amplitude data to a numpy array in int16 format.

    :param float32_array: A numpy array of float32 representing amplitude data.
    :return: A numpy array of int16 representing PCM data.
    """
    int16_array = np.clip(float32_array, -1, 1) * 32767
    return int16_array.astype(np.int16)


def base64_to_array_buffer(base64_string):
    """
    Converts a base64 string to a numpy array buffer of type uint8.

    :param base64_string: Base64-encoded string.
    :return: A numpy array of uint8 data.
    """
    binary_data = base64.b64decode(base64_string)
    return np.frombuffer(binary_data, dtype=np.uint8)


def array_buffer_to_base64(array_buffer):
    """
    Converts a numpy array buffer to a base64 string. If the data is float32, it gets
    converted to int16 PCM before encoding.

    :param array_buffer: The numpy array to encode. Can be float32 or int16.
    :return: Base64-encoded string of the underlying PCM data.
    """
    if array_buffer.dtype == np.float32:
        array_buffer = float_to_16bit_pcm(array_buffer)
    elif array_buffer.dtype == np.int16:
        array_buffer = array_buffer.tobytes()
    else:
        array_buffer = array_buffer.tobytes()

    return base64.b64encode(array_buffer).decode("utf-8")


def merge_int16_arrays(left, right):
    """
    Merge two numpy arrays of int16 by concatenation.

    :param left: A numpy array of int16.
    :param right: A numpy array of int16.
    :return: A merged numpy array of int16.
    :raises ValueError: If the provided arrays are not numpy arrays of int16.
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
    A base class to manage event handlers and event dispatching.
    Allows registering, clearing, and dispatching custom events.
    """

    def __init__(self):
        self.event_handlers = defaultdict(list)

    def on(self, event_name, handler):
        """
        Register a handler function for a specific event.

        :param event_name: The name of the event to handle.
        :param handler: The function/coroutine to call when the event is dispatched.
        """
        self.event_handlers[event_name].append(handler)

    def clear_event_handlers(self):
        """
        Clear all registered event handlers.
        """
        self.event_handlers = defaultdict(list)

    def dispatch(self, event_name, event):
        """
        Dispatch an event to all registered handlers.

        :param event_name: The name of the event being dispatched.
        :param event: The event data.
        """
        for handler in self.event_handlers[event_name]:
            if inspect.iscoroutinefunction(handler):
                asyncio.create_task(handler(event))
            else:
                handler(event)

    async def wait_for_next(self, event_name):
        """
        Wait for the next occurrence of a specific event.

        :param event_name: The name of the event to wait for.
        :return: The event data once it occurs.
        """
        future = asyncio.Future()

        def handler(event):
            if not future.done():
                future.set_result(event)

        self.on(event_name, handler)
        return await future


class RealtimeAPI(RealtimeEventHandler):
    """
    Manages a WebSocket connection to the Azure OpenAI real-time endpoint.
    Supports sending and receiving events, and handling connection state.
    """

    def __init__(self):
        super().__init__()
        
        self.default_url = "wss://api.openai.com/v1/realtime"
        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        if endpoint.startswith("https"):
            endpoint = endpoint.replace("https://", "wss://")
        self.url = endpoint
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.credentials = DefaultAzureCredential()
        self.acquire_token = get_bearer_token_provider(
            self.credentials, "https://cognitiveservices.azure.com/.default"
        )
        self.api_version = "2024-10-01-preview"
        self.azure_deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        self.ws = None

    def is_connected(self):
        """
        Check if a WebSocket connection is currently established.
        """
        return self.ws is not None

    def log(self, *args):
        """
        Helper logger to prepend timestamp info to logs.
        """
        logger.debug(f"[Websocket/{datetime.now(timezone.utc).isoformat()}]", *args)

    async def connect(self, model=None):
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
        Internal task to continuously receive messages from the server.
        Dispatches corresponding events based on the message 'type'.
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
        Send an event to the server over the active WebSocket connection.

        :param event_name: Name of the event to send.
        :param data: Dictionary containing event-related data.
        :raises Exception: If not connected or if data is not a dictionary.
        """
        if not self.is_connected():
            raise Exception("RealtimeAPI is not connected")

        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise Exception("data must be a dictionary")

        event = {"event_id": self._generate_id("evt_"), "type": event_name, **data}
        self.dispatch(f"client.{event_name}", event)
        self.dispatch("client.*", event)
        self.log("sent:", event)
        await self.ws.send(json.dumps(event))

    def _generate_id(self, prefix):
        """
        Generate a unique timestamp-based ID.

        :param prefix: A prefix string for the ID.
        :return: A string representing the unique event ID.
        """
        return f"{prefix}{int(datetime.utcnow().timestamp() * 1000)}"

    async def disconnect(self):
        """
        Close the active WebSocket connection.
        """
        if self.ws:
            await self.ws.close()
            self.ws = None
            self.log(f"Disconnected from {self.url}")


class RealtimeConversation:
    """
    Holds and updates local state of the conversation items and responses,
    processing various conversation events to maintain a coherent state.

    Provides a high-level interface to interpret 'conversation.item' events,
    response creation events, and more.
    """

    default_frequency = config.features.audio.sample_rate

    # Mapping of event types to their processor methods
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
        "input_audio_buffer.speech_started": (
            lambda self, event: self._process_speech_started(event)
        ),
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
        Reset all internal conversation state.
        """
        self.item_lookup = {}
        self.items = []
        self.response_lookup = {}
        self.responses = []

        # Queued data to add to newly created items
        self.queued_speech_items = {}
        self.queued_transcript_items = {}
        self.queued_input_audio = None

    def queue_input_audio(self, input_audio):
        """
        Temporarily store input audio data so it can be appended
        to a user message once created.
        """
        self.queued_input_audio = input_audio

    def process_event(self, event, *args):
        """
        Dispatch an event to the appropriate handler function.

        :param event: The event dictionary with a 'type'.
        :param args: Additional arguments required by certain event processors.
        :raises Exception: If no processor is registered for the given event type.
        :return: A tuple (item, delta) if the processor modifies or creates items.
        """
        event_processor = self.EventProcessors.get(event["type"])
        if not event_processor:
            raise Exception(f"Missing conversation event processor for {event['type']}")
        return event_processor(self, event, *args)

    def get_item(self, id):
        """
        Retrieve an item from the conversation by its ID.

        :param id: The unique item ID.
        :return: The item dict if found, otherwise None.
        """
        return self.item_lookup.get(id)

    def get_items(self):
        """
        Get a copy of all tracked conversation items.
        """
        return self.items[:]

    # -----------------------------
    # Conversation Item Processors
    # -----------------------------

    def _process_item_created(self, event):
        """
        Handle creation of a new conversation item. Updates item lookup, merges
        any queued audio or transcript, and initializes internal formatting data.
        """
        item = event["item"]
        new_item = item.copy()

        # If item is new, add to lookup and main list
        if new_item["id"] not in self.item_lookup:
            self.item_lookup[new_item["id"]] = new_item
            self.items.append(new_item)

        # Initialize item formatting fields
        new_item["formatted"] = {"audio": [], "text": "", "transcript": ""}

        # Merge queued speech items
        if new_item["id"] in self.queued_speech_items:
            new_item["formatted"]["audio"] = self.queued_speech_items[new_item["id"]][
                "audio"
            ]
            del self.queued_speech_items[new_item["id"]]

        # Merge textual content
        if "content" in new_item:
            text_content = [
                c for c in new_item["content"] if c["type"] in ["text", "input_text"]
            ]
            for content in text_content:
                new_item["formatted"]["text"] += content["text"]

        # Merge queued transcripts
        if new_item["id"] in self.queued_transcript_items:
            new_item["formatted"]["transcript"] = self.queued_transcript_items[
                new_item["id"]
            ]["transcript"]
            del self.queued_transcript_items[new_item["id"]]

        # Set status for message, function calls, etc.
        if new_item["type"] == "message":
            if new_item["role"] == "user":
                new_item["status"] = "completed"
                if self.queued_input_audio:
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
        """
        Handle truncation of a conversation item. Typically used to
        cut audio data at a specific timestamp.
        """
        item_id = event["item_id"]
        audio_end_ms = event["audio_end_ms"]
        item = self.item_lookup.get(item_id)

        if not item:
            raise Exception(f'item.truncated: Item "{item_id}" not found')

        end_index = (audio_end_ms * self.default_frequency) // 1000
        item["formatted"]["transcript"] = ""
        item["formatted"]["audio"] = item["formatted"]["audio"][:end_index]

        return item, None

    def _process_item_deleted(self, event):
        """
        Handle deletion of a conversation item.
        """
        item_id = event["item_id"]
        item = self.item_lookup.get(item_id)
        if not item:
            raise Exception(f'item.deleted: Item "{item_id}" not found')

        del self.item_lookup[item["id"]]
        self.items.remove(item)
        return item, None

    def _process_input_audio_transcription_completed(self, event):
        """
        Handle completion of an input audio transcription.
        Merges transcript data into the conversation item.
        """
        item_id = event["item_id"]
        content_index = event["content_index"]
        transcript = event["transcript"]
        formatted_transcript = transcript or " "

        item = self.item_lookup.get(item_id)
        if not item:
            self.queued_transcript_items[item_id] = {"transcript": formatted_transcript}
            return None, None

        item["type"] = "conversation.item.input_audio_transcription.completed"
        item["content"][content_index]["transcript"] = transcript
        item["formatted"]["transcript"] = formatted_transcript

        return item, {"transcript": transcript}

    def _process_speech_started(self, event):
        """
        Handle the start of speech input.
        This logs the start time for later splicing of audio data.
        """
        item_id = event["item_id"]
        audio_start_ms = event["audio_start_ms"]
        self.queued_speech_items[item_id] = {"audio_start_ms": audio_start_ms}
        return None, None

    def _process_speech_stopped(self, event, input_audio_buffer):
        """
        Handle the stop of speech input.
        This extracts the relevant portion of the input audio buffer
        based on start/end timestamps.
        """
        item_id = event["item_id"]
        audio_end_ms = event["audio_end_ms"]

        speech_info = self.queued_speech_items[item_id]
        speech_info["audio_end_ms"] = audio_end_ms

        if input_audio_buffer:
            start_index = (
                speech_info["audio_start_ms"] * self.default_frequency
            ) // 1000
            end_index = (speech_info["audio_end_ms"] * self.default_frequency) // 1000
            speech_info["audio"] = input_audio_buffer[start_index:end_index]

        return None, None

    # -----------------------------
    # Response Event Processors
    # -----------------------------

    def _process_response_created(self, event):
        """
        Handle creation of a new response. A response object ties together output items.
        """
        response = event["response"]
        if response["id"] not in self.response_lookup:
            self.response_lookup[response["id"]] = response
            self.responses.append(response)
        return None, None

    def _process_output_item_added(self, event):
        """
        Handle the addition of a new output item to a response.
        """
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
        """
        Handle completion of an output item in a response.
        """
        item = event["item"]
        if not item:
            raise Exception('response.output_item.done: Missing "item"')

        found_item = self.item_lookup.get(item["id"])
        if not found_item:
            raise Exception(f'response.output_item.done: Item "{item["id"]}" not found')

        found_item["status"] = item["status"]
        return found_item, None

    def _process_content_part_added(self, event):
        """
        Handle addition of a new part of content (e.g., text, audio) to an existing item.
        """
        item_id = event["item_id"]
        part = event["part"]

        item = self.item_lookup.get(item_id)
        if not item:
            raise Exception(f'response.content_part.added: Item "{item_id}" not found')

        item["content"].append(part)
        return item, None

    def _process_audio_transcript_delta(self, event):
        """
        Handle incremental transcript updates for audio content.
        """
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
        """
        Handle incremental audio data updates for an output item.
        """
        item_id = event["item_id"]
        content_index = event["content_index"]
        delta = event["delta"]

        item = self.item_lookup.get(item_id)
        if not item:
            logger.debug(f'response.audio.delta: Item "{item_id}" not found')
            return None, None

        array_buffer = base64_to_array_buffer(delta)
        append_values = array_buffer.tobytes()
        # TODO: make it work
        # item['formatted']['audio'] = merge_int16_arrays(item['formatted']['audio'], append_values)

        return item, {"audio": append_values}

    def _process_text_delta(self, event):
        """
        Handle incremental text data updates for an output item.
        """
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
        """
        Handle incremental arguments for a function call item.
        """
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
    A higher-level client that manages:
      - Connecting to RealtimeAPI
      - Maintaining a conversation state through RealtimeConversation
      - Sending/receiving user messages, function/tool calls
      - Session creation and configuration updates
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
        self.session_config = {}
        self.transcription_models = [{"model": "whisper-1"}]
        self.default_server_vad_config = {
            "type": "server_vad",
            "threshold": 0.8,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 200,
        }
        self.realtime = RealtimeAPI()
        self.assistant = AssistantService()
        self.conversation = RealtimeConversation()
        self._reset_config()
        self._add_api_event_handlers()

    def _reset_config(self):
        """
        Reset the session configuration to default and clear internal state flags.
        """
        self.session_created = False
        self.tools = {}
        self.session_config = self.default_session_config.copy()
        self.input_audio_buffer = bytearray()
        return True

    def _add_api_event_handlers(self):
        """
        Register handlers for realtime events (both client and server).
        """
        self.realtime.on("client.*", self._log_event)
        self.realtime.on("server.*", self._log_event)

        # Session
        self.realtime.on("server.session.created", self._on_session_created)

        # Response and content
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

        # Delta events
        self.realtime.on("server.response.audio_transcript.delta", self._process_event)
        self.realtime.on("server.response.audio.delta", self._process_event)
        self.realtime.on("server.response.text.delta", self._process_event)
        self.realtime.on(
            "server.response.function_call_arguments.delta", self._process_event
        )

        self.realtime.on("server.response.output_item.done", self._on_output_item_done)

    def _log_event(self, event):
        """
        Log any event from the realtime connection and dispatch it for downstream listeners.
        """
        realtime_event = {
            "time": datetime.utcnow().isoformat(),
            "source": "client" if event["type"].startswith("client.") else "server",
            "event": event,
        }
        self.dispatch("realtime.event", realtime_event)

    def _on_session_created(self, event):
        """
        Mark the session as created once the server sends a session.created event.
        """
        self.session_created = True

    def _process_event(self, event, *args):
        """
        Proxy function to pass an event to RealtimeConversation for processing.
        Dispatches 'conversation.updated' if items are created/updated.
        """
        item, delta = self.conversation.process_event(event, *args)
        if item:
            self.dispatch("conversation.updated", {"item": item, "delta": delta})
        return item, delta

    def _on_speech_started(self, event):
        """
        Handle 'speech_started' event by marking the conversation as interrupted
        and updating conversation state.
        """
        self._process_event(event)
        self.dispatch("conversation.interrupted", event)

    def _on_speech_stopped(self, event):
        """
        Handle 'speech_stopped' event, pass input buffer for splicing audio data.
        """
        self._process_event(event, self.input_audio_buffer)

    def _on_item_created(self, event):
        """
        Handle 'item.created' event. If the item is completed, dispatch a completion event.
        """
        item, delta = self._process_event(event)
        self.dispatch("conversation.item.appended", {"item": item})
        if item and item["status"] == "completed":
            self.dispatch("conversation.item.completed", {"item": item})

    async def _on_output_item_done(self, event):
        """
        Handle 'output_item.done'. When an item is completed, check if it's a function/tool call
        that needs to be handled.
        """
        item, delta = self._process_event(event)
        if item and item["status"] == "completed":
            self.dispatch("conversation.item.completed", {"item": item})

        # If it's a tool call, run the tool
        if item and item.get("formatted", {}).get("tool"):
            await self._call_tool(item["formatted"]["tool"])

    async def _call_tool(self, tool):
        """
        Execute the requested tool/function. If it's an 'assistant' tool, switch to the agent.
        Otherwise, send the tool result as a conversation item.
        """
        try:
            json_arguments = json.loads(tool["arguments"])
            tool_name = tool["name"]

            # Use the assistant service to handle tool calls or agent calls
            result = await self.assistant.get_tool_response(
                tool_name=tool_name, parameters=json_arguments, call_id=tool["call_id"]
            )

            # If the tool name matches an 'assistant' agent, switch the session to that agent
            if re.search(r"assistant", tool_name, re.IGNORECASE):
                agent = self.assistant.get_agent(tool_name)
                logger.debug(f"Switching to agent {agent['id']}")
                await self.realtime.send(
                    "session.update",
                    {
                        "session": {
                            "instructions": agent["system_message"],
                            "tools": self.assistant.get_tools_for_assistant(tool_name),
                        }
                    },
                )
            else:
                # For non-agent tools, just return the result
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
            # If an error occurs during the tool call, send an error response
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
        # Create another response after processing the tool
        await self.create_response()

    def is_connected(self):
        """
        Checks if the underlying RealtimeAPI is connected.
        """
        return self.realtime.is_connected()

    def reset(self):
        """
        Disconnect, clear event handlers, and reset config/session state.
        """
        self.disconnect()
        self.realtime.clear_event_handlers()
        self._reset_config()
        self._add_api_event_handlers()
        return True

    async def connect(self):
        """
        Connect to the RealtimeAPI and setup the 'root' agent as the initial session state.
        """
        if self.is_connected():
            raise Exception("Already connected, use .disconnect() first")

        await self.realtime.connect()

        # Configure the root agent
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
        Wait until the session_created flag is set (i.e., server.session.created is received).
        """
        if not self.is_connected():
            raise Exception("Not connected, use .connect() first")
        while not self.session_created:
            await asyncio.sleep(0.001)
        return True

    async def disconnect(self):
        """
        Disconnect from the RealtimeAPI and clear local conversation state.
        """
        self.session_created = False
        self.conversation.clear()
        if self.realtime.is_connected():
            await self.realtime.disconnect()

    def get_turn_detection_type(self):
        """
        Return the type of turn detection in the current session config.
        """
        return self.session_config.get("turn_detection", {}).get("type")

    async def add_tool(self, definition, handler):
        """
        Dynamically add a tool/function to the session.

        :param definition: A dict describing the tool (including "name").
        :param handler: The Python function/coroutine that implements the tool.
        :raises Exception: If the tool is missing a name, already added, or handler is not callable.
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
        Remove an existing tool by name.
        """
        if name not in self.tools:
            raise Exception(f'Tool "{name}" does not exist, can not be removed.')
        del self.tools[name]
        return True

    async def delete_item(self, id):
        """
        Request deletion of a conversation item by ID.
        """
        await self.realtime.send("conversation.item.delete", {"item_id": id})
        return True

    async def update_session(self, **kwargs):
        """
        Update the session configuration, optionally extending or overriding current config.
        """
        self.session_config.update(kwargs)

        # Combine config tools and those added via add_tool()
        use_tools = [
            {**tool_definition, "type": "function"}
            for tool_definition in self.session_config.get("tools", [])
        ] + [
            {**self.tools[key]["definition"], "type": "function"} for key in self.tools
        ]

        session = {**self.session_config, "tools": use_tools}
        if self.realtime.is_connected():
            await self.realtime.send("session.update", {"session": session})
        return True

    async def create_conversation_item(self, item):
        """
        Create a conversation item (e.g., a user message, function call, etc.).
        """
        await self.realtime.send("conversation.item.create", {"item": item})

    async def send_user_message_content(self, content=[]):
        """
        Send a user message containing text or audio input content.
        Automatically triggers creation of a new response after the message.

        :param content: A list of content dicts, e.g. [{'type': 'input_audio', 'audio': ...}, ...]
        """
        if content:
            # Convert binary audio to base64 if necessary
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
        Incrementally push audio data to the input_audio_buffer on the server.

        :param array_buffer: The raw PCM audio (int16) to append.
        """
        if len(array_buffer) > 0:
            # Convert to base64 for sending
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
        Create a new response, potentially finalizing any pending user audio input if no turn detection.
        """
        if self.get_turn_detection_type() is None and len(self.input_audio_buffer) > 0:
            await self.realtime.send("input_audio_buffer.commit")
            self.conversation.queue_input_audio(self.input_audio_buffer)
            self.input_audio_buffer = bytearray()
        await self.realtime.send("response.create")
        return True

    async def cancel_response(self, id=None, sample_count=0):
        """
        Cancel an in-progress response. If no ID is provided, cancels the current response.
        Otherwise, truncates the existing item to end at sample_count in the audio.

        :param id: The ID of the conversation item to cancel (must be an assistant message).
        :param sample_count: Number of audio samples to retain in the item before truncation.
        :return: Dict with the canceled item or None.
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

            await self.realtime.send("response.cancel")

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

    async def wait_for_next_item(self):
        """
        Wait for the next conversation item to be appended.
        """
        event = await self.wait_for_next("conversation.item.appended")
        return {"item": event["item"]}

    async def wait_for_next_completed_item(self):
        """
        Wait for the next conversation item that has status='completed'.
        """
        event = await self.wait_for_next("conversation.item.completed")
        return {"item": event["item"]}
