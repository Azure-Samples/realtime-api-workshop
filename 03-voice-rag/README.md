# Implement VoiceRAG

## Overview

In this exercise, you will implement a RAG (Retrieval Augmented Generation) solution with native audio input and output leveraging an existing [solution accelerator](https://github.com/Azure-Samples/aisearch-openai-rag-audio) that provides a simple front-end and back-end implementation. The back-end is a proxy that implements tools/functions to provide RAG and to connect with the real-time API.

## Prerequisites

- Azure OpenAI
    - Real-time model: gpt-4o-realtime-preview
    - Embedding model: text-embeddings-ada-002 or text-embedding-003-large/text-embedding-003-small
- Azure AI Search
- Azure Blob Storage
- Development environment (_or leverage the preconfigured VSCode Dev Container_)
    - Python 3.9+
    - Node.js
    - Git
    - [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) (optional, needed for identity based authentication)

## Create an Azure AI Search index 

_If you don't have access to the Azure Portal or other policies prevent you from creating an Azure AI Search index, you can skip this step and ask the coaches for a preconfigured Azure AI Search index._

In this step we will generate a vector index based on your own documents. If you don't want to leverage your own documents, you can download [this sample dataset](https://github.com/Azure-Samples/aisearch-openai-rag-audio/tree/main/data).

1. Navigate to your Azure AI Search in the [Azure Portal](https://portal.azure.com).
1. On the "Overview" page, select "Import and vectorize data" in the top bar.
1. Select Azure Blob Storage as the data source and select your storage account.
1. Select your Azure OpenAI service and the embedding model you want to use.
1. Don't select "Vectorize images" and "Extract text from images" for this exercise.
1. Optionally you can change the schedule to your own preference, or leave it at "Once". If your region supports semantic ranker, you will see an option to enable semantic ranker. Keep this option enabled. 
1. Change the name of your vector store to reflect your documents and select the "Create" button. Store the name of this vector store, as you will need this later.

After a few minutes, your index will be populated with chunks and vectors from your documents. 

1. Go back to the main page of your Azure AI Search.
2. Copy and store the URL of your AI Search, you will need this later.
3. If you want to leverage key based authentication, navigate to "Settings -> Keys". Create a new query key and copy and store this value.
4. If you want to leverage user identity authentication, navigate to "Access control (IAM)" and grant your user the "Search Service Contributor" role.

> [!NOTE]
> For more details on ingesting data in Azure AI Search using "Import and vectorize data", here's a [quickstart](https://learn.microsoft.com/en-us/azure/search/search-get-started-portal-import-vectors).

## VoiceRAG webapplication

Now we have a preconfigured Azure AI Search index, we can run the VoiceRAG sample. In this exercise we will run the sample locally, but you can also deploy it to Azure in a later stage.

### Setup your development environment

The easiest way to setup your development environment is to leverage the provided VSCode Dev Container. This container is preconfigured with all the necessary tools and dependencies to run the sample. You can run this Dev Container locally in VSCode or in GitHub Codespaces.

#### GitHub Codespaces

[![Open in GitHub Codespaces](https://img.shields.io/static/v1?style=for-the-badge&label=GitHub+Codespaces&message=Open&color=brightgreen&logo=github)](https://github.com/codespaces/new?hide_repo_select=true&ref=main&skip_quickstart=true&machine=basicLinux32gb&repo=860141324&devcontainer_path=.devcontainer%2Fdevcontainer.json)

Once the Codespace opens (this may take several minutes), open a new terminal and proceed to [configure the environment](#configure-the-environment).

#### Local (DevContainer)

You can run the project in your local VS Code Dev Container using the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Start Docker Desktop (install it if not already installed)
1. Open the project:

    [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/azure-samples/aisearch-openai-rag-audio)
1. In the VSCode window that opens, once the project files show up (this may take several minutes), open a new terminal, and proceed to [deploying the app](#deploying-the-app).


#### Local (Manual)

1. Make sure you meet the prerequisites mentioned earlier.

1. Clone the repository in your development environment.

```bash
git clone https://github.com/Azure-Samples/aisearch-openai-rag-audio.git
```

1. Navigate to the `aisearch-openai-rag-audio` directory.

### Configure the environment

1. Create a `.env` file in the `/app/backend` folder of the project and add the following environment variables, replacing the placeholders with your own services:

```
AZURE_OPENAI_ENDPOINT=https://<YOUR_OPENAI_ENDPOINT>.openai.azure.com
AZURE_OPENAI_REALTIME_DEPLOYMENT=<YOUR_OPENAI_REALTIME_MODEL_DEPLOYMENT>
AZURE_SEARCH_ENDPOINT=https://<YOUR_SEARCH_SERVICE>.search.windows.net
AZURE_SEARCH_INDEX=<YOUR_INDEX_NAME>
```

If your region supports semantic ranker, you can add the following environment variable to enable semantic search for more relevant results:

```
AZURE_SEARCH_SEMANTIC_CONFIGURATION=<YOUR_INDEX_NAME>-semantic-configuration
```

1. There are multiple ways to authenticate your application with Azure services: key based authentication and identity based authentication.

    - **Key based authentication**: This method uses API keys to authenticate. It's straightforward but less secure because the keys need to be stored and managed securely. If you are using key based authentication, set the following environment variables in your `.env` file:

        ```
        AZURE_OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>
        AZURE_SEARCH_API_KEY=<YOUR_SEARCH_API_KEY>
        ```

    - **Identity based authentication**: This method uses Microsoft Entra ID to authenticate. It's more secure as it doesn't require storing sensitive keys. This will require the [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli), as we will use the Azure CLI credential locally.
    
    To use identity based authentication, log in to your Azure account and select your subscription.

    ```bash
    az login
    ```
    
    > [!IMPORTANT]
    > In order to use identity based authentication, you should grant your user the "Search Service Contributor" role in the Azure AI Search service and the "OpenAI Contributor" role in the Azure OpenAI service. 

### Run the solution

1. Run this command to start the app:

   Windows:

   ```pwsh
   pwsh .\scripts\start.ps1
   ```

   Linux/Mac/DevContainer/GitHub CodeSpaces:

   ```bash
   ./scripts/start.sh
   ```

1. The app is available on [http://localhost:8765](http://localhost:8765).

   Once the app is running, when you navigate to the URL above you should see the start screen of the app. To try out the app, click the "Start conversation button", say "Hello", and then ask a question about your data like "What are the perks at Contoso?" if you use the sample documents.


### Troubleshooting
- If you encounter any issues, please check the logs in the terminal where you started the app.
- If you encounter any issues with speech recognition, please check if the right microphone is selected. Best is to set your preferred microphone as the default microphone in your OS system settings.
- If you encounter any issues during the conversation, please restart the application. The conversation state is persisted within the memory and might cause issues.

Great, now you have the sample up and running! This sample is a great starting point to build your own VoiceRAG solution. If you have more time, here are some advanced exercises to further tailor the accelerator to your needs:

1. [Prompt Engineering](advanced-exercises.md#prompt-engineering)
2. [Modify the interface](advanced-exercises.md#modify-the-interface)
3. [Function Calling](advanced-exercises.md#function-calling)