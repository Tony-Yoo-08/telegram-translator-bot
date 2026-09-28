Set-Location "C:\Users\yth31\Desktop\ide개발탭\overseas-mission-system"
$html = Get-Content -Raw -Encoding UTF8 index.html
# Add auto-login session script
$injected = '<script>sessionStorage.setItem("MISSION_CONTROL_AUTH_TOKEN", "YWRtaW46MTIz"); sessionStorage.setItem("CURRENT_USER_LABEL", "총괄 관제 (부장/총무/서무 공용)");</script></head>'
$html = $html -replace '</head>', $injected
Set-Content -Path test_view.html -Value $html -Encoding UTF8

$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$proc = Start-Process -FilePath $edge -ArgumentList "--headless=new", "--virtual-time-budget=6000", "--screenshot", "--window-size=1400,900", "file:///C:/Users/yth31/Desktop/ide%EA%B0%9C%EB%B0%9C%ED%83%AD/overseas-mission-system/test_view.html" -PassThru -Wait

Remove-Item test_view.html -Force -ErrorAction SilentlyContinue
