$ErrorActionPreference = "Stop"
$base = "https://reports.adnermo.online"
$credential = Join-Path $env:LOCALAPPDATA 'STS2_Things\private\reports-admin-password.txt'
if (-not (Test-Path -LiteralPath $credential)) { throw "Admin secret file missing" }
$password = (Get-Content -Raw -LiteralPath $credential).Trim()
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$failures = New-Object System.Collections.Generic.List[string]
function Expect([bool]$ok, [string]$name) {
    if ($ok) { Write-Output "PASS $name" } else { $script:failures.Add($name); Write-Output "FAIL $name" }
}
function Send([string]$path,[string]$method='GET',[object]$body=$null,[bool]$origin=$false) {
    $p = @{Uri="$base$path";Method=$method;WebSession=$session;SkipHttpErrorCheck=$true;TimeoutSec=20}
    if($origin) { $p.Headers = @{ Origin=$base } }
    if($null -ne $body){$p.Body=($body|ConvertTo-Json -Depth 16 -Compress);$p.ContentType='application/json'}
    return Invoke-WebRequest @p
}
$html = Send '/admin'
Expect ($html.StatusCode -eq 200 -and $html.Content.Contains('尖塔观察站') -and $html.Content.Contains('了解每一次不寻常')) 'dashboard html and design'
$unauth = Send '/api/admin/stats'
Expect ($unauth.StatusCode -eq 401) 'anonymous stats denied'
$unauthDetail = Send '/api/admin/reports/00000000-0000-0000-0000-000000000000'
Expect ($unauthDetail.StatusCode -eq 401) 'anonymous details denied'
$loginMissingOrigin = Send '/api/admin/login' 'POST' @{password=$password}
Expect ($loginMissingOrigin.StatusCode -eq 403) 'login origin enforced'
$login = Send '/api/admin/login' 'POST' @{password=$password} $true
Expect ($login.StatusCode -eq 200) 'admin login successful'
$me = Send '/api/admin/me'
Expect ($me.StatusCode -eq 200) 'authenticated session accepted'
$stats = Send '/api/admin/stats'
Expect ($stats.StatusCode -eq 200) 'authenticated statistics'
$id = [guid]::NewGuid().ToString('N')
$report = @{
 schema=1;source='sts2_things';client_report_id=$id;description='Admin integration smoke report';reported_at=(Get-Date).ToUniversalTime().ToString('O')
 run=@{schema=1;game_version='test-0.107';mod_version='dev';events=@(@{at=(Get-Date).ToUniversalTime().ToString('O');kind='room_entered';act_index=1;floor=5});state=@{seed='admin-smoke';ascension=9;current_act_index=1;route=@()}}
}
$upload=Send '/api/reports' 'POST' $report
Expect ($upload.StatusCode -eq 201) 'anonymous report intake'
$reportId=($upload.Content|ConvertFrom-Json).report_id
if(!$reportId) {throw 'Upload did not return receipt'}
$found=Send ('/api/admin/reports?q='+$reportId)
Expect ($found.StatusCode -eq 200 -and ($found.Content|ConvertFrom-Json).total -eq 1) 'report search'
$detail=Send "/api/admin/reports/$reportId"
Expect ($detail.StatusCode -eq 200 -and ($detail.Content|ConvertFrom-Json).report.payload.run.state.seed -eq 'admin-smoke') 'report details'
$csrf=Invoke-WebRequest -Uri "$base/api/admin/reports/$reportId" -Method PATCH -WebSession $session -SkipHttpErrorCheck -TimeoutSec 20 -Headers @{Origin='https://evil.invalid'} -ContentType 'application/json' -Body '{"status":"investigating"}'
Expect ($csrf.StatusCode -eq 403) 'cross origin mutation blocked'
$patch=Send "/api/admin/reports/$reportId" 'PATCH' @{status='investigating';developer_note='reproduced with seed'} $true
Expect ($patch.StatusCode -eq 200) 'status and developer note patch'
$detail2=Send "/api/admin/reports/$reportId"
$d2=($detail2.Content|ConvertFrom-Json).report
Expect ($d2.status -eq 'investigating' -and $d2.developer_note -eq 'reproduced with seed') 'triage data persisted'
$delete=Send "/api/admin/reports/$reportId" 'DELETE' @{} $true
Expect ($delete.StatusCode -eq 200) 'delete test report'
$gone=Send "/api/admin/reports/$reportId"
Expect ($gone.StatusCode -eq 404) 'deletion verified'
$logout=Send '/api/admin/logout' 'POST' @{} $true
Expect ($logout.StatusCode -eq 200) 'logout'
$loggedOut=Send '/api/admin/stats'
Expect ($loggedOut.StatusCode -eq 401) 'session invalidated in browser'
if($failures.Count){throw "FAILED: $($failures -join ', ')"}
Write-Output 'ALL ADMIN SMOKE CHECKS PASSED'