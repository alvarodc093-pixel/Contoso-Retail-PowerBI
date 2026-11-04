<#
.SYNOPSIS
  Comprueba que las medidas DAX del informe abierto en Power BI Desktop dan las
  mismas cifras que powerbi/datos/cifras_control.json (calculadas con SQL).

.DESCRIPTION
  1. Abre powerbi/ContosoRetail.pbip en Power BI Desktop y pulsa "Actualizar".
  2. Ejecuta:  powershell -ExecutionPolicy Bypass -File verificar_dax.ps1
  El script busca el motor local de Power BI, lanza una consulta DAX por año y
  compara Ventas, Margen %, Pedidos, Clientes, % online y Objetivo.
#>
$ErrorActionPreference = "Stop"

# Motor de Power BI Desktop: el puerto está en la carpeta de trabajo más reciente.
$carpetas = @(
    "$env:USERPROFILE\Microsoft\Power BI Desktop Store App\AnalysisServicesWorkspaces",
    "$env:LOCALAPPDATA\Microsoft\Power BI Desktop\AnalysisServicesWorkspaces"
) | Where-Object { Test-Path $_ }
$puertoArchivo = Get-ChildItem $carpetas -Recurse -Filter msmdsrv.port.txt |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $puertoArchivo) { throw "No encuentro Power BI Desktop abierto." }
$puerto = (Get-Content $puertoArchivo.FullName -Encoding Unicode).Trim()

# Librería cliente que trae el propio Power BI Desktop.
$pbi = Get-Process PBIDesktop | Select-Object -First 1
$dll = Join-Path (Split-Path $pbi.Path) "Microsoft.PowerBI.AdomdClient.dll"
Add-Type -Path $dll

$con = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection "Data Source=localhost:$puerto"
$con.Open()
$cmd = $con.CreateCommand()
$cmd.CommandText = @"
EVALUATE
SUMMARIZECOLUMNS (
    calendario[anio],
    "ventas", [Ventas],
    "margen_pct", [Margen %],
    "pedidos", [Pedidos],
    "clientes", [Clientes],
    "pct_online", [% online],
    "objetivo", [Objetivo]
)
"@
$r = $cmd.ExecuteReader()
$dax = @{}
while ($r.Read()) {
    $dax[[string]$r.GetValue(0)] = @{
        ventas = [double]$r.GetValue(1); margen_pct = [double]$r.GetValue(2)
        pedidos = [double]$r.GetValue(3); clientes = [double]$r.GetValue(4)
        pct_online = [double]$r.GetValue(5)
        objetivo = if ($r.IsDBNull(6)) { $null } else { [double]$r.GetValue(6) }
    }
}
$con.Close()

$control = Get-Content (Join-Path $PSScriptRoot "powerbi\datos\cifras_control.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$tolerancias = @{ ventas = 1; margen_pct = 0.0001; pedidos = 0; clientes = 0; pct_online = 0.0001; objetivo = 1 }
$fallos = 0
foreach ($anio in ($control.PSObject.Properties.Name | Sort-Object)) {
    $esperado = $control.$anio
    foreach ($k in $tolerancias.Keys) {
        $e = $esperado.$k; $d = $dax[$anio][$k]
        if ($null -eq $e -and $null -eq $d) { continue }
        if ($null -eq $e -or $null -eq $d -or [math]::Abs($e - $d) -gt $tolerancias[$k]) {
            "FALLO $anio $k : SQL=$e DAX=$d"; $fallos++
        }
    }
}
if ($fallos -eq 0) { "OK: las medidas DAX coinciden con SQL en los $($control.PSObject.Properties.Name.Count) años." }
else { "$fallos diferencias"; exit 1 }
