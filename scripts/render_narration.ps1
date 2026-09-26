param(
    [Parameter(Mandatory = $true)][string]$CueJson,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$output = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null
$cues = Get-Content -LiteralPath $CueJson -Raw -Encoding UTF8 | ConvertFrom-Json
$voice = New-Object -ComObject SAPI.SpVoice
$voice.Rate = 2
$available = $voice.GetVoices()
if ($available.Count -gt 1) {
    $voice.Voice = $available.Item(1)
}

for ($index = 0; $index -lt $cues.Count; $index++) {
    $stream = New-Object -ComObject SAPI.SpFileStream
    $path = Join-Path $output ('cue-{0:D2}.wav' -f $index)
    $stream.Open($path, 3, $false)
    $voice.AudioOutputStream = $stream
    [void]$voice.Speak([string]$cues[$index].text)
    $stream.Close()
}
