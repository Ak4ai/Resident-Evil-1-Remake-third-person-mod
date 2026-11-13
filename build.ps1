param([switch]$Loader)
# Builds re1mod.dll (and the loader with -Loader). The mod is copied to the captures dir and reload.flag is
# raised, so a running game picks it up within ~15 frames.
$root = Split-Path $MyInvocation.MyCommand.Path
$cap = "$env:USERPROFILE\Tools\captures"
$game = "C:\Program Files (x86)\Steam\steamapps\common\Resident Evil Biohazard HD REMASTER"
$pk = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Directory | ? Name -like 'MartinStorsjo.LLVM-MinGW*').FullName
$cc = (Get-ChildItem $pk -Recurse -Filter 'i686-w64-mingw32-clang.exe' | Select -First 1).FullName

& $cc -O2 -shared -static -w -o "$root\mod\re1mod.dll" "$root\mod\mod.c" '-Wl,--kill-at'
if ($LASTEXITCODE -ne 0) { throw "mod build failed" }
Copy-Item "$root\mod\re1mod.dll" "$cap\re1mod.dll" -Force

if ($Loader) {
    & $cc -O2 -shared -static -w -o "$root\d3d9proxy\d3d9.dll" "$root\d3d9proxy\d3d9.c" '-Wl,--kill-at'
    if ($LASTEXITCODE -ne 0) { throw "loader build failed" }
    Copy-Item "$root\d3d9proxy\d3d9.dll" "$game\d3d9.dll" -Force
    "loader installed (restart the game once)"
} else {
    New-Item -ItemType File "$cap\reload.flag" -Force | Out-Null
    "mod built, reload requested"
}
