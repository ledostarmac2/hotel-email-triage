$file = 'c:\Users\btarabocchia\Downloads\hotel-email-triage\agent_comms\from_codex.md'
$last = (Get-Item $file).LastWriteTime
while ($true) {
    Start-Sleep -Seconds 10
    $cur = (Get-Item $file).LastWriteTime
    if ($cur -ne $last) {
        Write-Output "CHANGED at $cur"
        $last = $cur
    }
}
