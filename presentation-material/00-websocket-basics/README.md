# WebSocket Basics Workshop

A quick hands-on introduction to WebSocket communication through practical examples.

## Quick Start

### Setting Up

Choose one of the following methods to run the demo:

#### Option 1: Using uv (Recommended)
[uv](https://github.com/astral-sh/uv) is a fast Python package installer and runner. If you haven't installed it yet:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then run the server directly (this will automatically install dependencies):
```bash
cd 00-websocket-basics
uv run server.py
```

In a new terminal, start the web client:
```bash
cd 00-websocket-basics
uv run -m http.server 8000
```

#### Option 2: Using pip
1. Install dependencies: (Skip this step if you have done azd up from the root folder)
   ```bash
   pip install -r requirements.txt
   ```

2. Start the WebSocket server:
   ```bash
   python server.py
   ```

3. In a new terminal, start the web client:
   ```bash
   cd 00-websocket-basics
   python -m http.server 8000
   ```

### Accessing the Demo

Open your browser and visit:
```
http://localhost:8000
```

## What to Observe

### 1. Bouncing Ball Demo
- Watch the ball's movement - it updates in real-time without any visible delay
- Open multiple browser windows - notice how they all stay perfectly synchronized
- Open the browser's Developer Tools (Network tab) and observe:
  - A single WebSocket connection staying open
  - No continuous HTTP requests needed for updates

### 2. HTTP vs WebSocket Comparison
Try both methods to get the ball's position:

**WebSocket (Already running)**
- Smooth, continuous updates
- Single persistent connection
- Minimal network overhead

**HTTP Polling (Try it out)**
1. Click the "Start HTTP Polling" button (default interval: 100ms)
2. Experiment with different polling intervals (100ms, 500ms, 1000ms)
3. Observe:
   - Increased network traffic
   - Less smooth updates at higher intervals
   - Higher latency compared to WebSocket
   - More server load due to frequent new connections

## Key Takeaways

- WebSockets provide real-time updates with minimal latency
- Single persistent connection vs multiple HTTP requests
- Perfect for:
  - Live data streaming
  - Real-time synchronization
  - Bi-directional communication

## Next Steps

Now that we understand how WebSockets enable real-time communication, let's explore how this technology powers voice-to-voice interactions in the [Real-time API](../01-getting-started-function-calling/README.md). You'll see how WebSockets facilitate seamless streaming of audio data between users, enabling natural conversations with minimal latency.
