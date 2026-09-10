# Deterministic, editable brand artwork; no external graphics packages required.
Add-Type -AssemblyName System.Drawing
$brandDirectory = Join-Path $PSScriptRoot '../custom_components/smart_ev_charging/brand'
$null = New-Item -ItemType Directory -Path $brandDirectory -Force
foreach ($size in @(256, 512)) {
    $bitmap = New-Object System.Drawing.Bitmap($size, $size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.ScaleTransform(($size / 256), ($size / 256))
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $navy = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml('#102D40'))
    $mint = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml('#4DE1AB'))
    $white = New-Object System.Drawing.Pen([System.Drawing.Color]::White, 10)
    $white.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $white.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $graphics.FillEllipse($navy, 8, 8, 240, 240)
    $graphics.DrawArc($white, 47, 47, 162, 162, 290, 290)
    $bolt = [System.Drawing.PointF[]]@(
        [System.Drawing.PointF]::new(137, 56), [System.Drawing.PointF]::new(89, 132),
        [System.Drawing.PointF]::new(122, 132), [System.Drawing.PointF]::new(110, 193),
        [System.Drawing.PointF]::new(167, 112), [System.Drawing.PointF]::new(135, 112)
    )
    $graphics.FillPolygon($mint, $bolt)
    $graphics.DrawLine($white, 192, 51, 207, 67)
    $name = if ($size -eq 256) { 'icon.png' } else { 'icon@2x.png' }
    $bitmap.Save((Join-Path $brandDirectory $name), [System.Drawing.Imaging.ImageFormat]::Png)
    $white.Dispose()
    $mint.Dispose()
    $navy.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
}
