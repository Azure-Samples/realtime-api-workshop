#!/usr/bin/env python
import asyncio
import websockets
import json
from typing import Optional


class WebSocketClient:
    def __init__(self, uri: str = "ws://localhost:8765"):
        self.uri = uri
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

    async def receive_messages(self):
        """Handle incoming messages from the server"""
        try:
            while True:
                message = await self.websocket.recv()
                data = json.loads(message)

                # Pretty print different message types
                if data["type"] == "welcome":
                    print(f"\n {data['message']}")
                elif data["type"] == "game_update":
                    print(
                        f"\r Ball position: x={data['position']['x']:.1f}, y={data['position']['y']:.1f}",
                        end="",
                    )

        except websockets.exceptions.ConnectionClosed:
            print("\n Connection to server closed")
        except Exception as e:
            print(f"\n Error: {str(e)}")

    async def connect(self):
        """Connect to the WebSocket server"""
        try:
            self.websocket = await websockets.connect(self.uri)
            print(f"\n Connected to {self.uri}")
            await self.receive_messages()
        except Exception as e:
            print(f"\n Connection error: {str(e)}")


async def main():
    """Main function to run the client"""
    client = WebSocketClient()
    await client.connect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Goodbye!")
