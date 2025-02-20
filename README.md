# Realtime API Workshop

Build voice-enabled AI assistants using Azure OpenAI's Realtime API. Create a multi-agent system for customer service applications.

## Workshop Modules

| Module                | Focus                                 | Documentation                                            |
| --------------------- | ------------------------------------- | -------------------------------------------------------- |
| 1. WebSocket Basics   | Real-time Communication Fundamentals  | [Guide](./presentation-material/00-websocket-basics/README.md)                 |
| 2. Function Calling   | Azure OpenAI Realtime API Integration | [Guide](./01-getting-started-function-calling/README.md) |
| 3. Multi-Agent System | Customer Service Implementation       | [Guide](./02-building-multi-agent-system/README.md)      |
| 4. Voice RAG          | Voice-Optimized Document Retrieval    | [Guide](./03-voice-rag/README.md)                        |


## Setup
1. Execute ``azd up`` from the root folder.
2. The above command will setup your python env, provision Azure AI foundry Hub, Project and GPT4o-realtime-audio instance and will initialize .env file.
3. Update the .env with the API Key of GPT4o-realtime-audio model. You can find the key in Azure portal
4. Move to respective modules to further run/work on the workshop modules.


## Additional resources

### SDKs & Libraries

The following SDKs and libraries can be used to integrate with the gpt-4o-realtime-api (preview) on Azure.

| SDK/Library                                                | Description                                            |
| ---------------------------------------------------------- | ------------------------------------------------------ |
| [`openai-python`](https://github.com/openai/openai-python) | The official Python library for the (Azure) OpenAI API |
| [`openai-dotnet`](https://github.com/openai/openai-dotnet) | The official .NET library for the (Azure) OpenAI API   |

### Accelerators & Templates

| Accelerator                                                                                        | Description                                                                                                                                                                                   |
| -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [VoiceRAG (aisearch-openai-rag-audio)](https://github.com/Azure-Samples/aisearch-openai-rag-audio) | A simple example implementation of the VoiceRAG pattern to power interactive voice generative AI experiences using RAG with Azure AI Search and Azure OpenAI's gpt-4o-realtime-preview model. |
| [On The Road CoPilot](https://github.com/Azure-Samples/on-the-road-copilot)                        | A minimal speech-to-structured output app built with Azure OpenAI Realtime API.                                                                                                               |


## Contributing

Contributions welcome via pull requests.