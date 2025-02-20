#!/bin/bash

# Define the .env file path
ENV_FILE_PATH=".env"

# Clear the contents of the .env file
> $ENV_FILE_PATH

# Append new values to the .env file
echo "AZURE_OPENAI_ENDPOINT=$(azd env get-value AZURE_OPENAI_ENDPOINT)" >> $ENV_FILE_PATH
echo "AZURE_OPENAI_DEPLOYMENT=$(azd env get-value AZURE_OPENAI_DEPLOYMENT)" >> $ENV_FILE_PATH
echo "AZURE_OPENAI_API_KEY=$(azd env get-value AZURE_OPENAI_API_KEY)" >> $ENV_FILE_PATH