# Define variables
$remoteHost = "10.250.66.78"
$remoteUser = "appuser"
$remotePath = "/var/lib/jenkins/workspace/BUILD_DEPLOY_FRONTEND/dist"

$localPath = "$env:USERPROFILE\Downloads"
$extractPath = "C:\sit"

# === Blacklist patterns (case-insensitive wildcards) ===
$blacklist = @("backup*", "temp*", "*.tmp.zip")

# === Get file list from remote ===
$sshCmd = "find $remotePath -maxdepth 1 -type f -name '*.zip' -printf '%TY-%Tm-%Td %TH:%TM %s %p\n'"
$fileListRaw = & ssh -q "$remoteUser@$remoteHost" $sshCmd

if (-not $fileListRaw) {
    Write-Host "< No .zip files found or SSH connection failed." -ForegroundColor Red
    exit
}

# === Parse files ===
$fileEntries = @()
$fileListRaw -split "`n" | ForEach-Object {
    $parts = $_ -split '\s+', 4
    if ($parts.Count -eq 4) {
        $name = [System.IO.Path]::GetFileName($parts[3])
        $match = $false
        foreach ($pattern in $blacklist) {
            if ($name -like $pattern) { $match = $true; break }
        }
        if (-not $match) {
            $fileEntries += [PSCustomObject]@{
                Name = $name
                Date = "$($parts[0]) $($parts[1])"
                Size = $parts[2] # in bytes
                FullPath = $parts[3]
            }
        }
    }
}

if ($fileEntries.Count -eq 0) {
    Write-Host "< No zip files to show after applying blacklist." -ForegroundColor Red
    exit
}

# === Find longest filename length ===
$maxNameLength = ($fileEntries | Measure-Object -Property Name -Maximum).Maximum.Length

# === Display file list ===
Write-Host "`nAvailable ZIP files:" -ForegroundColor Magenta
for ($i = 0; $i -lt $fileEntries.Count; $i++) {
    $f = $fileEntries[$i]

    # Human-readable size
    $bytes = [double]$f.Size
    switch ($bytes) {
        { $_ -ge 1GB } { $sizeStr = "{0:N1} GB" -f ($bytes / 1GB); break }
        { $_ -ge 1MB } { $sizeStr = "{0:N1} MB" -f ($bytes / 1MB); break }
        { $_ -ge 1KB } { $sizeStr = "{0:N1} KB" -f ($bytes / 1KB); break }
        default        { $sizeStr = "$bytes B" }
    }

    # Print nicely aligned
    $fmt = "{0,3}) {1,-$maxNameLength} {2,10}  {3}"
    Write-Host ($fmt -f $i, $f.Name, "($sizeStr)", $f.Date)
}

# === Select file ===
do {
    Write-Host "`n> Enter the index of the file to download: " -NoNewLine -ForegroundColor Yellow
    $selection = Read-Host
    if ([string]::IsNullOrWhiteSpace($selection)) {
        $selection = '0'
    }
} while (-not ($selection -match '^\d+$') -or [int]$selection -ge $fileEntries.Count)

$selected = $fileEntries[$selection]
$remoteFile = "`"$($selected.FullPath)`""
$localFile = Join-Path -Path $localPath -ChildPath $selected.Name

# === Download using scp ===
Write-Host "`n< Downloading '$($selected.Name)'..." -ForegroundColor Cyan
scp -q ${remoteUser}@${remoteHost}:$remoteFile "$localFile"

if ($LASTEXITCODE -ne 0) {
    Write-Host "< Download failed!" -ForegroundColor Red
    exit
}

Write-Host "< Download complete: $localFile" -ForegroundColor Green

# === Compute and show SHA256 hash ===
Write-Host "`n< Verifying file integrity with SHA256..." -ForegroundColor Cyan
try {
    $hash = Get-FileHash -Algorithm SHA256 -Path $localFile
    Write-Host "< SHA256: $($hash.Hash)" -ForegroundColor Green
} catch {
    Write-Host "< Failed to compute hash: $_" -ForegroundColor Red
}

# Extract the file using 7-Zip
$sevenZipCommand = "7z x $localFile -o$extractPath -y"
Write-Host "`n$> Extracting $localFile to $extractPath" -ForegroundColor Cyan
Invoke-Expression $sevenZipCommand

# Check if the extraction was successful
$contents = Test-Path -Path "$extractPath\*"
if (-Not($content)) {
    Write-Host "`n< File extracted successfully to $extractPath" -ForegroundColor Green
} else {
    Write-Host "`n< Extraction failed." -ForegroundColor Red
}

