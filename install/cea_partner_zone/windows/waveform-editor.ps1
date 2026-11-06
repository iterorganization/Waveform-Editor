# Waveform-Editor launcher for Windows.
# Connects to altair with SSH, starts the GUI there and opens it in the browser of
# this laptop. Run it by double-clicking waveform-editor.cmd. Close the window to stop.

param(
    [string]$Login = "",
    [string]$Server = "altair.partenaires.cea.fr",
    [int]$Port = 5006
)

$ErrorActionPreference = "Stop"
# The modules of the Waveform-Editor and NICE on altair
$ModulePath = "/home/MS013565/public/easybuild/modules/all"
$LoginFile = Join-Path $HOME ".waveform-editor-login"

if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Write-Host "The ssh program was not found. Install it in Windows settings:"
    Write-Host "  Settings > System > Optional features > Add > OpenSSH Client"
    Read-Host "Press Enter to close"
    exit 1
}

# The login on altair, asked once and remembered
if (-not $Login -and (Test-Path $LoginFile)) {
    $Login = (Get-Content $LoginFile -Raw).Trim()
}
if (-not $Login) {
    $Login = (Read-Host "Your login on $Server (for example MS013565)").Trim()
    Set-Content -Path $LoginFile -Value $Login
}

# Take the first free local port from $Port on
function Test-PortFree([int]$p) {
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $p)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    }
}
while (-not (Test-PortFree $Port)) { $Port++ }
$Url = "http://localhost:$Port"

Write-Host "Connecting to $Server as $Login. Log in as for x2go."
Write-Host "The GUI opens in your browser when it is ready ($Url)."
Write-Host "To stop: press Ctrl+C or close this window."
Write-Host ""

# Whether the GUI answers through the forward. The favicon is served without
# building a GUI session; no proxy, as a proxy cannot reach localhost
function Test-GuiReady([string]$Url) {
    try {
        $request = [System.Net.WebRequest]::Create("$Url/favicon.ico")
        $request.Proxy = $null
        $request.Timeout = 5000
        $request.GetResponse().Close()
        return $true
    } catch {
        return $false
    }
}

# LogLevel=ERROR hides the failed checks while the GUI starts
$sshArgs = @(
    "-t",
    "-o", "LogLevel=ERROR",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=60",
    "-L", "127.0.0.1:${Port}:/home/$Login/.waveform-editor.sock",
    "$Login@$Server",
    # A login shell has the module command. ssh joins these words with spaces,
    # so that the remote shell gets the command between single quotes as one
    "bash", "-l", "-c",
    "'module", "use", $ModulePath, "&&", "module", "load", "Waveform-Editor", "&&",
    "exec", "waveform-editor", "gui", "--socket", "--local-port", "$Port'"
)
$ssh = Start-Process ssh -ArgumentList $sshArgs -NoNewWindow -PassThru

# Open the browser once the GUI answers, while ssh runs in this window
$opened = $false
while (-not $ssh.HasExited) {
    if (-not $opened -and (Test-GuiReady $Url)) {
        $opened = $true
        Write-Host ""
        Write-Host "Opening $Url in your browser (the page takes about 10 s to appear)."
        Write-Host ""
        try {
            Start-Process $Url
        } catch {
            Write-Host "Could not open the browser: open $Url yourself."
        }
    }
    Start-Sleep -Seconds 1
}

Write-Host ""
Read-Host "The GUI has stopped. Press Enter to close"
