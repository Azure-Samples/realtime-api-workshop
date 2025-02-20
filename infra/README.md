# Azure AI Foundry

This project provides a Bicep template for deploying an Azure AI Foundry environment, which includes a hub, a project, and an Azure OpenAI GPT-4 real-time audio instance.

## Project Structure

```
infra
├── main.bicep
├── modules
│   ├── ai_hub.bicep
│   └── dependent_resources.bicep
└── README.md
```

## Prerequisites

- Azure subscription
- Azure CLI installed and configured
- Bicep CLI installed

## Deployment Instructions

1. Clone this repository to your local machine.
2. Navigate to the `infra` directory.
3. Authenticate with your Azure account using the Azure CLI:
   ```
   az login
   ```
4. Deploy the Bicep template using the following command:
   ```
   az deployment group create --resource-group <your-resource-group> --template-file main.bicep
   ```
