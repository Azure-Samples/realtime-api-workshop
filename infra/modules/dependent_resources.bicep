// Creates Azure dependent resources for Azure AI studio

@description('Azure region of the deployment')
param location string = resourceGroup().location

@description('AI services name')
param aiServicesName string

resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: aiServicesName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  properties: {
    apiProperties: {
      statisticsEnabled: false
    }
  }
}

@description('Name of the deployment ')
param modeldeploymentname string = 'gpt-4o-realtime-preview'

@description('The model being deployed')
param model string = 'gpt-4o-realtime-preview'

@description('Version of the model being deployed')
param modelversion string = '2024-12-17'

@description('Capacity for specific model used')
param capacity int = 30

resource azopenaideployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServices
  name: modeldeploymentname
  properties: {
      model: {
          format: 'OpenAI'
          name: model
          version: modelversion
      }
  }
  sku: {
    name: 'GlobalStandard'
    capacity: capacity
  }
}

output aiservicesID string = aiServices.id
output aiservicesTarget string = aiServices.properties.endpoint
output deploymentName string = modeldeploymentname
