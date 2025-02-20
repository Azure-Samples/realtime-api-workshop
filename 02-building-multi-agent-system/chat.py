import chainlit as cl
from uuid import uuid4
from chainlit.logger import logger
from dotenv import load_dotenv

from realtime2 import RealtimeClient

from agents.activation import activation_assistant
from agents.sales import sales_assistant
from agents.root import root_assistant
from agents.technical import technical_assistant

load_dotenv(override=True)


async def setup_openai_realtime():
    """
    Initialize and configure the OpenAI Realtime Client with event handlers.

    This function sets up the realtime client with necessary event handlers for:
    - Conversation updates (handling audio transcription and streaming)
    - Item completion (managing chat context with transcriptions)
    - Conversation interruption (managing audio playback cancellation)
    - Error handling

    It also registers all available agents (activation, sales, technical, root) with the client.
    """
    # Create a RealtimeClient with an empty system prompt.
    openai_realtime = RealtimeClient(system_prompt="")

    # Generate and store a unique track ID for audio streaming.
    cl.user_session.set("track_id", str(uuid4()))

    async def handle_conversation_updated(event):
        """
        Handle real-time updates to the conversation.

        Args:
            event (dict): Event data containing 'item' and 'delta' information
                - item: Contains event type and related data
                - delta: Contains incremental changes (audio, transcript, or arguments)

        This handler is primarily used for:
        - Processing audio transcriptions and sending them to the client
        - Streaming audio back to the client
        - Managing function arguments as they arrive
        """
        item = event.get("item")
        delta = event.get("delta")

        # Process incoming transcription and send as a user message in the chat.
        if (
            item
            and "input_audio_transcription" in item.get("type", "")
            and delta
            and "transcript" in delta
        ):
            msg = cl.Message(content=delta["transcript"], author="user")
            msg.type = "user_message"
            await msg.send()

        # Handle streaming audio, transcripts, and function arguments.
        if delta:
            if "audio" in delta:
                audio_chunk = delta["audio"]  # PCM 16-bit audio bytes
                await cl.context.emitter.send_audio_chunk(
                    cl.OutputAudioChunk(
                        mimeType="pcm16",
                        data=audio_chunk,
                        track=cl.user_session.get("track_id"),
                    )
                )
            if "transcript" in delta:
                # Potential future handling of incremental transcripts.
                pass
            if "arguments" in delta:
                # Potential future handling of function arguments.
                pass

    async def handle_item_completed(item):
        """
        Process completed conversation items and update the chat context.

        Args:
            item (dict): The completed conversation item containing type and content information

        This handler specifically manages audio message transcriptions, ensuring
        they are properly displayed in the chat context once completed.
        """
        if item["item"]["type"] == "message":
            content = item["item"]["content"][0]
            if content["type"] == "audio":
                await cl.Message(content=content["transcript"]).send()

    async def handle_conversation_interrupt(event):
        """
        Handle conversation interruptions by resetting audio playback.

        Args:
            event (dict): The interruption event (currently unused)
        """
        # Generate a new track ID for the next audio chunk sequence.
        cl.user_session.set("track_id", str(uuid4()))
        # Send an interrupt signal to stop current audio playback (v2.0.0+).
        await cl.context.emitter.send_audio_interrupt()

    async def handle_error(event):
        """
        Log errors that occur during the conversation.

        Args:
            event (dict): The error event to be logged
        """
        logger.error(event)

    # Register event handlers with the RealtimeClient.
    openai_realtime.on("conversation.updated", handle_conversation_updated)
    openai_realtime.on("conversation.item.completed", handle_item_completed)
    openai_realtime.on("conversation.interrupted", handle_conversation_interrupt)
    openai_realtime.on("error", handle_error)

    # Make the RealtimeClient accessible via the user session.
    cl.user_session.set("openai_realtime", openai_realtime)

    # Register all the agent handlers with the RealtimeClient.
    openai_realtime.assistant.register_agent(activation_assistant)
    openai_realtime.assistant.register_agent(sales_assistant)
    openai_realtime.assistant.register_agent(technical_assistant)

    # Register the root agent last to ensure every agent knows each other.
    openai_realtime.assistant.register_root_agent(root_assistant)
    # coros = [openai_realtime.add_tool(tool_def, tool_handler) for tool_def, tool_handler in root_tools]
    # await asyncio.gather(*coros)


@cl.on_chat_start
async def start():
    """
    Initialize the chat session by setting up the OpenAI Realtime client.

    This function is triggered when a new chat session begins and ensures all
    necessary components are properly initialized.
    """
    await setup_openai_realtime()


@cl.on_message
async def on_message(message: cl.Message):
    """
    Process incoming chat messages and forward them to the realtime client.

    Args:
        message (cl.Message): The incoming chat message

    This handler:
    - Checks if the realtime client is connected
    - Forwards text messages to the realtime client
    - Provides feedback if voice mode isn't activated
    """
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")

    if openai_realtime and openai_realtime.is_connected():
        await openai_realtime.send_user_message_content(
            [{"type": "input_text", "text": message.content}]
        )
    else:
        await cl.Message(
            content="Please activate voice mode before sending messages!"
        ).send()


@cl.on_audio_start
async def on_audio_start():
    """
    Initialize audio streaming session.

    This handler is triggered when audio streaming begins and ensures
    the realtime client is properly connected for audio processing.
    """
    try:
        openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")
        await openai_realtime.connect()
        logger.info("Connected to Azure OpenAI Realtime API")
        return True
    except Exception as e:
        await cl.ErrorMessage(
            content=f"Failed to connect to Azure OpenAI Realtime API: {e}"
        ).send()
        return False


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    """
    Process incoming audio chunks and forward them to the realtime client.

    Args:
        chunk (cl.InputAudioChunk): A chunk of audio data to be processed

    This handler ensures continuous audio streaming by forwarding chunks
    to the realtime client for processing.
    """
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")

    if openai_realtime:
        if openai_realtime.is_connected():
            await openai_realtime.append_input_audio(chunk.data)
        else:
            logger.info("RealtimeClient is not connected")


@cl.on_audio_end
@cl.on_chat_end
@cl.on_stop
async def on_end():
    """
    Clean up resources when the audio session ends.

    This handler ensures proper cleanup of the realtime client connection
    when the audio streaming session is terminated.
    """
    openai_realtime: RealtimeClient = cl.user_session.get("openai_realtime")

    if openai_realtime and openai_realtime.is_connected():
        await openai_realtime.disconnect()
