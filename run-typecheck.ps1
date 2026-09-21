$ErrorActionPreference = 'Stop'
$python = 'C:\kit-app-template\_build\windows-x86_64\release\kit\python\python.exe'
$bootstrap = @'
import runpy, sys
sys.path.insert(0, 'verification/typecheck')
sys.argv = ['mypy', '--config-file', 'pyproject.toml']
runpy.run_module('mypy', run_name='__main__')
'@
& $python -c $bootstrap
exit $LASTEXITCODE
