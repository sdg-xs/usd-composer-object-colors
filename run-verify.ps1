param(
    [string]$Test = '',
    [string]$KitRoot = 'C:\kit-app-template\_build\windows-x86_64\release\kit'
)
$ErrorActionPreference = 'Stop'
$cache = Join-Path (Split-Path $KitRoot -Parent) 'extscache'
$usd = Get-ChildItem -LiteralPath $cache -Directory -Filter 'omni.usd.libs-*' | Select-Object -First 1
if (-not $usd) { throw "No omni.usd.libs extension found in $cache" }
$bootstrap = @'
import os, runpy, sys
kit, usd, root, test = sys.argv[1:]
sys.argv = [test or 'unittest']
handles = [os.add_dll_directory(kit), os.add_dll_directory(os.path.join(usd, 'bin'))]
sys.path[:0] = [root, usd]
if test:
    runpy.run_path(os.path.join(root, test), run_name='__main__')
else:
    import unittest
    suite = unittest.defaultTestLoader.discover(os.path.join(root, 'tests'), pattern='test_*.py')
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
'@
& (Join-Path $KitRoot 'python\python.exe') -c $bootstrap $KitRoot $usd.FullName $PSScriptRoot $Test
exit $LASTEXITCODE
