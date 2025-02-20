// Execute this main file to depoy Azure AI studio resources in the basic security configuraiton
targetScope = 'subscription'

// Parameters
@minLength(2)
@maxLength(12)
@description('Name for the AI resource and used to derive name of dependent resources.')
param aiHubName string = 'gpt4o-audio'

@description('Friendly name for your Azure AI resource')
param aiHubFriendlyName string = 'GPT4o audio workshop HUB'

@description('Description of your Azure AI resource dispayed in AI studio')
param aiHubDescription string = 'This is a resource for GPT4o audio workshop.'

@description('Location for the the resource group')
@allowed([
  'eastus2'
  'swedencentral'
])
@metadata({
  azd: {
    type: 'location'
  }
})
param location string
param resourceGroupName string = ''


@description('Set of tags to apply to all resources.')
param tags object = {}

@description('Capacity of the GPT4o realtime audio capacity.')
param capacity int = 30


// Variables
var name = toLower('${aiHubName}')


// Organize resources in a resource group
resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: !empty(resourceGroupName) ? resourceGroupName : 'rg-${name}-01'
  location: location
}

// Create a short, unique suffix, that will be unique to each resource group
var uniqueSuffix = substring(uniqueString(resourceGroup.id), 0, 4)

// Dependent resources for the Azure Machine Learning workspace
module aiDependencies 'modules/dependent_resources.bicep' = {
  name: 'dependencies-${name}-${uniqueSuffix}-deployment'
  scope: resourceGroup
  params: {
    location: location
    aiServicesName: 'ais${name}${uniqueSuffix}'
    capacity: capacity
  }
}

module aiHub 'modules/ai_hub.bicep' = {
  name: 'ai-${name}-${uniqueSuffix}-deployment'
  scope: resourceGroup
  params: {
    // workspace organization
    aiHubName: 'aih-${name}-${uniqueSuffix}'
    aiHubFriendlyName: aiHubFriendlyName
    aiHubDescription: aiHubDescription
    location: location
    tags: tags

    // dependent resources
    aiServicesId: aiDependencies.outputs.aiservicesID
    aiServicesTarget: aiDependencies.outputs.aiservicesTarget
  }
}

output AZURE_OPENAI_ENDPOINT string = aiDependencies.outputs.aiservicesTarget
output AZURE_OPENAI_DEPLOYMENT string = aiDependencies.outputs.deploymentName
