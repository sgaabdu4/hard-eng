$ErrorActionPreference = 'Stop'

$items = @(
    node "$PSScriptRoot/windows-installer-assets-contract.mjs" --powershell-json |
        ConvertFrom-Json
)
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
foreach ($item in $items) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseInput(
        [string]$item.source,
        [ref]$tokens,
        [ref]$errors
    ) | Out-Null
    if ($errors.Count -ne 0) {
        Write-Error "$($item.name): $($errors[0].Message)"
        exit 1
    }
}
Write-Output "windows-installer-powershell: PASS scripts=$($items.Count)"
