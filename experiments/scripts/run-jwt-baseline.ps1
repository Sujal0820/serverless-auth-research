
param(
    [int]$Requests = 10,
    [string]$OutputFile = "experiments/results/jwt-baseline.csv"
)

$ErrorActionPreference = "Stop"

# Resolve the project root relative to this script.
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$outputPath = Join-Path $projectRoot $OutputFile

# Read the API URL and Cognito client ID from Terraform outputs.
$terraformDir = Join-Path $projectRoot "infrastructure/terraform"
$apiUrl = (terraform -chdir="$terraformDir" output -raw research_api_url).Trim()
$clientId = (terraform -chdir="$terraformDir" output -raw cognito_client_id).Trim()

if (-not $apiUrl -or -not $clientId) {
    throw "Could not read the API URL or Cognito client ID from Terraform."
}

# Get a fresh access token without printing the password.
$securePassword = Read-Host "Enter the research test user's permanent password" -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)

try {
    $password = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)

    $authJson = aws cognito-idp initiate-auth `
        --client-id $clientId `
        --auth-flow USER_PASSWORD_AUTH `
        --auth-parameters "USERNAME=research-test-user,PASSWORD=$password" `
        --region eu-west-1 `
        --no-cli-pager

    $auth = $authJson | ConvertFrom-Json
    $accessToken = $auth.AuthenticationResult.AccessToken

    if (-not $accessToken) {
        throw "Cognito did not return an access token."
    }
}
finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $password = $null
    $securePassword.Dispose()
}

# Make sure the output folder exists.
New-Item -ItemType Directory -Force (Split-Path $outputPath) | Out-Null

$results = [System.Collections.Generic.List[object]]::new()

Write-Host "Starting JWT baseline test: $Requests requests"
Write-Host "API: $apiUrl"

for ($i = 1; $i -le $Requests; $i++) {
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $status = 0
    $requestId = ""
    $errorMessage = ""

    try {
        $response = Invoke-WebRequest `
            -Uri "$apiUrl/research" `
            -Method Post `
            -Headers @{ Authorization = "Bearer $accessToken" } `
            -ContentType "application/json" `
            -Body '{}' `
            -TimeoutSec 30

        $status = [int]$response.StatusCode
        $body = $response.Content | ConvertFrom-Json
        $requestId = $body.request_id
    }
    catch {
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        $errorMessage = $_.Exception.Message
    }
    finally {
        $stopwatch.Stop()
    }

    $results.Add([PSCustomObject]@{
        timestamp_utc = [DateTime]::UtcNow.ToString("o")
        request_number = $i
        scenario = "JWT_BASELINE"
        http_status = $status
        success = ($status -eq 200)
        client_latency_ms = [Math]::Round($stopwatch.Elapsed.TotalMilliseconds, 3)
        api_request_id = $requestId
        error = $errorMessage
    })

    Write-Host "Request $i/$Requests | HTTP $status | $([Math]::Round($stopwatch.Elapsed.TotalMilliseconds, 3)) ms"

    # Avoid creating an unnecessary burst of requests.
    Start-Sleep -Milliseconds 250
}


$results | Export-Csv -Path $outputPath -NoTypeInformation -Encoding utf8

$successful = @($results | Where-Object { $_.success })
$latencies = @(
    $successful |
    ForEach-Object { [double]$_.client_latency_ms } |
    Sort-Object
)

Write-Host ""
Write-Host "Test complete."
Write-Host "Results saved to: $outputPath"
Write-Host "Successful requests: $($successful.Count)/$Requests"

function Get-Percentile {
    param(
        [double[]]$Values,
        [double]$Percentile
    )

    if ($Values.Count -eq 0) {
        return $null
    }

    # Linear interpolation using position p/100 * (n - 1).
    $position = ($Percentile / 100) * ($Values.Count - 1)
    $lowerIndex = [int][Math]::Floor($position)
    $upperIndex = [int][Math]::Ceiling($position)

    if ($lowerIndex -eq $upperIndex) {
        return [double]$Values[$lowerIndex]
    }

    $fraction = $position - $lowerIndex

    return [double]$Values[$lowerIndex] +
        ($fraction * (
            [double]$Values[$upperIndex] -
            [double]$Values[$lowerIndex]
        ))
}

if ($latencies.Count -gt 0) {
    $mean = ($latencies | Measure-Object -Average).Average
    $p50 = Get-Percentile -Values $latencies -Percentile 50
    $p90 = Get-Percentile -Values $latencies -Percentile 90
    $p95 = Get-Percentile -Values $latencies -Percentile 95
    $minimum = $latencies[0]
    $maximum = $latencies[$latencies.Count - 1]

    Write-Host ""
    Write-Host "Client-observed latency statistics (successful requests):"
    Write-Host "Mean:   $([Math]::Round($mean, 3)) ms"
    Write-Host "P50:    $([Math]::Round($p50, 3)) ms"
    Write-Host "P90:    $([Math]::Round($p90, 3)) ms"
    Write-Host "P95:    $([Math]::Round($p95, 3)) ms"
    Write-Host "Min:    $([Math]::Round($minimum, 3)) ms"
    Write-Host "Max:    $([Math]::Round($maximum, 3)) ms"
}
