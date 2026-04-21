# Cria 3 atalhos na Area de Trabalho para acesso rapido ao IAprendo
$ProjectPath = 'C:\Dev\IAprendo_Sales_Agent'
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$WshShell = New-Object -ComObject WScript.Shell

# Detectar caminho do editor (Cursor ou VS Code)
$editorPaths = @(
    "$env:LOCALAPPDATA\Programs\cursor\Cursor.exe",
    "$env:LOCALAPPDATA\Programs\Cursor\Cursor.exe",
    "$env:LOCALAPPDATA\Programs\Microsoft VS Code\Code.exe",
    "$env:ProgramFiles\Microsoft VS Code\Code.exe",
    "${env:ProgramFiles(x86)}\Microsoft VS Code\Code.exe"
)
$editorExe = $editorPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

# Atalho 1: Editor (Cursor/VS Code)
if ($editorExe) {
    $editorName = if ($editorExe -like '*Cursor.exe') { 'Cursor' } else { 'VS Code' }
    $s1 = $WshShell.CreateShortcut((Join-Path $DesktopPath 'IAprendo - Codigo.lnk'))
    $s1.TargetPath = $editorExe
    $s1.Arguments = '"' + $ProjectPath + '"'
    $s1.WorkingDirectory = $ProjectPath
    $s1.Description = "Abrir projeto IAprendo no $editorName"
    $s1.IconLocation = "$editorExe,0"
    $s1.Save()
    Write-Host "[OK] Atalho 1 criado: IAprendo - Codigo.lnk (usando $editorName)"
} else {
    Write-Host "[AVISO] Cursor/VS Code nao encontrado - atalho 1 nao criado"
}

# Atalho 2: Iniciar IAlex
$s2 = $WshShell.CreateShortcut((Join-Path $DesktopPath 'IAprendo - Iniciar IAlex.lnk'))
$s2.TargetPath = Join-Path $ProjectPath 'start-ialex.bat'
$s2.WorkingDirectory = $ProjectPath
$s2.Description = 'Iniciar IAlex (WhatsApp agent)'
$s2.IconLocation = "$env:SystemRoot\System32\shell32.dll,138"
$s2.Save()
Write-Host "[OK] Atalho 2 criado: IAprendo - Iniciar IAlex.lnk"

# Atalho 3: Dashboard Streamlit
$s3 = $WshShell.CreateShortcut((Join-Path $DesktopPath 'IAprendo - Dashboard.lnk'))
$s3.TargetPath = Join-Path $ProjectPath 'start-dashboard.bat'
$s3.WorkingDirectory = $ProjectPath
$s3.Description = 'Abrir dashboard Streamlit do IAprendo'
$s3.IconLocation = "$env:SystemRoot\System32\shell32.dll,13"
$s3.Save()
Write-Host "[OK] Atalho 3 criado: IAprendo - Dashboard.lnk"

Write-Host ""
Write-Host "===== Atalhos criados na Area de Trabalho: ====="
Write-Host "Desktop: $DesktopPath"
