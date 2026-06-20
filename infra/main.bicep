/*
  FabricShield AI — Main Bicep Template
  Provisions all Azure resources for a production deployment.
  All secrets go to Key Vault; App Service uses Key Vault references.
*/

targetScope = 'resourceGroup'

// ── Parameters ────────────────────────────────────────────────────────────────
@description('Environment name: dev, staging, prod')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'prod'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Unique suffix for globally-unique resource names')
param uniqueSuffix string = uniqueString(resourceGroup().id)

@description('Entra ID tenant ID of the service provider (FabricShield)')
param serviceTenantId string

@description('App Registration client ID (multi-tenant)')
param clientId string

@description('App Registration client secret (will be stored in Key Vault)')
@secure()
param clientSecret string

@description('Power BI workspace ID')
param powerBiWorkspaceId string = ''

@description('Power BI report ID')
param powerBiReportId string = ''

@description('CORS allowed origins (comma-separated)')
param corsOrigins string = 'https://app.fabricshield.io'

// ── Variables ─────────────────────────────────────────────────────────────────
var prefix = 'fshield'
var resourcePrefix = '${prefix}-${environment}'
var appServicePlanName = '${resourcePrefix}-plan'
var backendAppName  = '${resourcePrefix}-api-${uniqueSuffix}'
var frontendAppName = '${resourcePrefix}-ui-${uniqueSuffix}'
var cosmosAccountName = '${prefix}cosmos${uniqueSuffix}'
var keyVaultName = '${prefix}kv${uniqueSuffix}'
var storageAccountName = '${prefix}sa${uniqueSuffix}'
var appInsightsName = '${resourcePrefix}-insights'
var logWorkspaceName = '${resourcePrefix}-law'

// ── Log Analytics Workspace ───────────────────────────────────────────────────
resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logWorkspaceName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 90
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ── Application Insights ──────────────────────────────────────────────────────
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logWorkspace.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ── Storage Account ───────────────────────────────────────────────────────────
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
    encryption: {
      services: {
        blob: { enabled: true }
        file: { enabled: true }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

// ── Key Vault ─────────────────────────────────────────────────────────────────
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: serviceTenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    networkAcls: {
      defaultAction: 'Allow'   // Tighten to 'Deny' + VNet rules for production
      bypass: 'AzureServices'
    }
  }
}

// ── Cosmos DB ─────────────────────────────────────────────────────────────────
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-02-15-preview' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      { locationName: location, failoverPriority: 0, isZoneRedundant: environment == 'prod' }
    ]
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    isVirtualNetworkFilterEnabled: false
    minimalTlsVersion: 'Tls12'
    backupPolicy: environment == 'prod' ? {
      type: 'Continuous'
      continuousModeProperties: {
        tier: 'Continuous7Days'
      }
    } : {
      type: 'Periodic'
      periodicModeProperties: {
        backupIntervalInMinutes: 240
        backupRetentionIntervalInHours: 8
        backupStorageRedundancy: 'Local'
      }
    }
    disableLocalAuth: true   // Managed Identity only — no key-based auth
  }
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-02-15-preview' = {
  parent: cosmosAccount
  name: 'fabricshield'
  properties: {
    resource: { id: 'fabricshield' }
    options: { throughput: 400 }
  }
}

// Containers with partition key = /tenant_id
var cosmosContainers = [
  { name: 'scan_results', partitionKey: '/tenant_id' }
  { name: 'approvals', partitionKey: '/tenant_id' }
  { name: 'audit_logs', partitionKey: '/tenant_id' }
  { name: 'tenant_config', partitionKey: '/tenant_id' }
]

resource cosmosContainersRes 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = [for c in cosmosContainers: {
  parent: cosmosDatabase
  name: c.name
  properties: {
    resource: {
      id: c.name
      partitionKey: { paths: [c.partitionKey], kind: 'Hash', version: 2 }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [{ path: '/*' }]
        excludedPaths: [{ path: '/"_etag"/?' }]
      }
    }
  }
}]

// ── App Service Plan ──────────────────────────────────────────────────────────
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: environment == 'prod' ? 'P2v3' : 'B2'
    tier: environment == 'prod' ? 'PremiumV3' : 'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// ── Backend App Service (FastAPI) ─────────────────────────────────────────────
resource backendApp 'Microsoft.Web/sites@2023-01-01' = {
  name: backendAppName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: environment == 'prod'
      minTlsVersion: '1.2'
      http20Enabled: true
      ftpsState: 'Disabled'
      healthCheckPath: '/health'
      appCommandLine: 'uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4'
      appSettings: [
        { name: 'ENVIRONMENT', value: environment }
        { name: 'AZURE_CLIENT_ID', value: clientId }
        { name: 'AZURE_TENANT_ID', value: serviceTenantId }
        { name: 'AZURE_CLIENT_SECRET', value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=azure-client-secret)' }
        { name: 'COSMOS_ENDPOINT', value: cosmosAccount.properties.documentEndpoint }
        { name: 'COSMOS_USE_MANAGED_IDENTITY', value: 'true' }
        { name: 'KEYVAULT_URL', value: keyVault.properties.vaultUri }
        { name: 'POWERBI_WORKSPACE_ID', value: powerBiWorkspaceId }
        { name: 'POWERBI_REPORT_ID', value: powerBiReportId }
        { name: 'CORS_ORIGINS', value: corsOrigins }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'MARKETPLACE_WEBHOOK_SECRET', value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=marketplace-webhook-secret)' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'PYTHON_ENABLE_WORKER_EXTENSIONS', value: '1' }
      ]
    }
  }
}

// ── Frontend App Service (React SPA) ─────────────────────────────────────────
resource frontendApp 'Microsoft.Web/sites@2023-01-01' = {
  name: frontendAppName
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'NODE|20-lts'
      alwaysOn: environment == 'prod'
      minTlsVersion: '1.2'
      http20Enabled: true
      ftpsState: 'Disabled'
      appCommandLine: 'pm2 serve /home/site/wwwroot 8080 --no-daemon --spa'
      appSettings: [
        { name: 'VITE_AZURE_CLIENT_ID', value: clientId }
        { name: 'VITE_API_BASE_URL', value: 'https://${backendAppName}.azurewebsites.net/api/v1' }
        { name: 'VITE_REDIRECT_URI', value: 'https://${frontendAppName}.azurewebsites.net' }
      ]
    }
  }
}

// ── RBAC Assignments ──────────────────────────────────────────────────────────

// Backend MSI → Key Vault Secrets User
resource kvSecretUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, backendApp.id, 'Key Vault Secrets User')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: backendApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Backend MSI → Cosmos DB Built-in Data Contributor
resource cosmosDataRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-02-15-preview' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, backendApp.id, 'cosmos-contributor')
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: backendApp.identity.principalId
    scope: cosmosAccount.id
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
output backendUrl string = 'https://${backendApp.properties.defaultHostName}'
output frontendUrl string = 'https://${frontendApp.properties.defaultHostName}'
output keyVaultName string = keyVault.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output backendManagedIdentityPrincipalId string = backendApp.identity.principalId
