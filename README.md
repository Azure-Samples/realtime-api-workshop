# Realtime API Workshop

Build voice-enabled AI assistants using Azure OpenAI's Realtime API. Create a multi-agent system for customer service applications.

## Workshop Modules

| Module                | Focus                                 | Documentation                                            |
| --------------------- | ------------------------------------- | -------------------------------------------------------- |
| 1. Function Calling   | Azure OpenAI Realtime API Integration | [Guide](./01-getting-started-function-calling/README.md) |
| 2. Multi-Agent System | Customer Service Implementation       | [Guide](./02-building-multi-agent-system/README.md)      |
| 3. Voice RAG          | Voice-Optimized Document Retrieval    | [Guide](./03-voice-rag/README.md)                        |


## Setup
### Using Azure Developer CLI
1. Execute ``azd up`` from the root folder.
2. The above command will setup your python env, provision Azure AI foundry Hub, Project and GPT4o-realtime-audio instance and will initialize .env file.
3. Update the .env with the API Key of GPT4o-realtime-audio model. You can find the key in Azure portal
4. Make a copy of the `.env` file and put it in the respective module folder
5. Move to respective modules to further run/work on the workshop modules.

### Using Devcontainer
1. Install & Run Docker
2. Run devcontainer using VSCode
3. When devcontainer has setup, run `pip install -r requirements.txt`
4. Setup an Azure AI Foundry Hub + Project using the Azure Portal | [Guide](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/create-projects?tabs=ai-studio)
5. Create a deployment of either `gpt-4o-realtime-preview` or `gpt-4o-mini-realtime-preview` | [Guide](https://learn.microsoft.com/en-us/azure/ai-services/openai/realtime-audio-quickstart)
6. Update the .env with the API Key of GPT4o-realtime-audio model. You can find the key in Azure AI Foundry portal under the deployment
7. Make a copy of the `.env` file and put it in the respective module folder 
8. Move to respective modules to further run/work on the workshop modules.

## Additional resources

### WebSocket Basics
Real-time Communication Fundamentals  | [Guide](./presentation-material/00-websocket-basics/README.md)  

### SDKs & Libraries

The following SDKs and libraries can be used to integrate with the gpt-4o-realtime-api (preview) on Azure.

| SDK/Library                                                | Description                                            |
| ---------------------------------------------------------- | ------------------------------------------------------ |
| [`openai-python`](https://github.com/openai/openai-python) | The official Python library for the (Azure) OpenAI API |
| [`openai-dotnet`](https://github.com/openai/openai-dotnet) | The official .NET library for the (Azure) OpenAI API   |
| [`openai-java`](https://github.com/openai/openai-java) | The official Java library for the (Azure) OpenAI API   |


### Accelerators & Templates

| Accelerator                                                                                        | Description                                                                                                                                                                                   |
| -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [VoiceRAG (aisearch-openai-rag-audio)](https://github.com/Azure-Samples/aisearch-openai-rag-audio) | A simple example implementation of the VoiceRAG pattern to power interactive voice generative AI experiences using RAG with Azure AI Search and Azure OpenAI's gpt-4o-realtime-preview model. |
| [On The Road CoPilot](https://github.com/Azure-Samples/on-the-road-copilot)                        | A minimal speech-to-structured output app built with Azure OpenAI Realtime API.                                                                                                               |


## Contributing

Contributions welcome via pull requests.