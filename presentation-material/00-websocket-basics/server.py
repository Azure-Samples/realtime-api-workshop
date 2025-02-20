#!/usr/bin/env python
import asyncio
import websockets
import json
import random
from aiohttp import web
import aiohttp_cors

# Store connected clients
clients = set()
game_state = {"ball_position": {"x": 50, "y": 50}, "direction": {"x": 1, "y": 1}}


async def update_game():
    """Update game state and broadcast to all clients"""
    while True:
        # Update ball position
        game_state["ball_position"]["x"] += game_state["direction"]["x"] * 2
        game_state["ball_position"]["y"] += game_state["direction"]["y"] * 2

        # Bounce off walls
        if (
            game_state["ball_position"]["x"] >= 100
            or game_state["ball_position"]["x"] <= 0
        ):
            game_state["direction"]["x"] *= -1
        if (
            game_state["ball_position"]["y"] >= 100
            or game_state["ball_position"]["y"] <= 0
        ):
            game_state["direction"]["y"] *= -1

        if clients:  # Only broadcast if there are connected clients
            message = json.dumps(
                {"type": "game_update", "position": game_state["ball_position"]}
            )
            websockets.broadcast(clients, message)

        await asyncio.sleep(0.05)  # Update every 50ms


async def websocket_handler(websocket):
    """Handle individual WebSocket connections"""
    try:
        # Register client
        clients.add(websocket)
        print(f"Client connected. Total clients: {len(clients)}")

        # Send welcome message
        await websocket.send(
            json.dumps(
                {
                    "type": "welcome",
                    "message": "Connected to WebSocket server",
                    "position": game_state["ball_position"],
                }
            )
        )

        # Keep connection alive and handle disconnection
        try:
            await websocket.wait_closed()
        finally:
            clients.remove(websocket)
            print(f"Client disconnected. Total clients: {len(clients)}")

    except websockets.exceptions.ConnectionClosedError:
        print("Client connection closed unexpectedly")
    except Exception as e:
        print(f"Error in websocket handler: {str(e)}")


# REST API Routes
async def get_ball_position(request):
    """REST endpoint to get current ball position"""
    return web.Response(
        text=json.dumps({"position": game_state["ball_position"]}),
        content_type="application/json",
    )


async def init_rest_app():
    """Initialize REST API application"""
    app = web.Application()

    # Configure CORS
    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        },
    )

    # Add routes
    cors.add(app.router.add_get("/ball-position", get_ball_position))

    return app


async def start_rest_server():
    """Start the REST server"""
    app = await init_rest_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8080)
    await site.start()
    print("REST server started at http://localhost:8080")


async def start_websocket_server():
    """Start the WebSocket server"""
    async with websockets.serve(websocket_handler, "localhost", 8765):
        await asyncio.Future()  # run forever


async def main():
    """Start both WebSocket and REST servers"""
    # Start the game update loop
    asyncio.create_task(update_game())

    # Start both servers
    await asyncio.gather(start_websocket_server(), start_rest_server())


if __name__ == "__main__":
    asyncio.run(main())
