# Define the .env file path
$envFilePath = ".env"

# Clear the contents of the .env file
Set-Content -Path $envFilePath -Value ""

# Append new values to the .env file
$azureOpenAiEndpoint = azd env get-value AZURE_OPENAI_ENDPOINT
$azureOpenAiRealtimeDeployment = azd env get-value AZURE_OPENAI_DEPLOYMENT

Add-Content -Path $envFilePath -Value "AZURE_OPENAI_ENDPOINT=$azureOpenAiEndpoint"
Add-Content -Path $envFilePath -Value "AZURE_OPENAI_DEPLOYMENT=$azureOpenAiRealtimeDeployment"
Add-Content -Path $envFilePath -Value "AZURE_OPENAI_API_KEY=<api-key>"