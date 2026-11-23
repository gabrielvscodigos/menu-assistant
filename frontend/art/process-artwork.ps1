# Turns the mascot artwork (art/waiter-source.png, white background) into the images the
# app uses: src/assets/waiter-full.png (whole figure, transparent background) and
# src/assets/waiter-avatar.png (head and shoulders, 160 x 160). Windows PowerShell only;
# uses the .NET imaging built into Windows, no extra tools.
#
#   powershell -File art/process-artwork.ps1        (from frontend/)
#
# With new artwork, adjust -Avatar (square crop in source pixels) and the tray-erasing
# rectangles below, then check the results.
param(
    [string] $Source = (Join-Path $PSScriptRoot 'waiter-source.png'),
    [string] $OutDir = (Join-Path $PSScriptRoot '..\src\assets'),
    # Avatar crop in source pixels: x, y, size (square). Empty to skip the avatar.
    [int[]] $Avatar = @(438, 92, 275)
)

Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class Artwork
{
    // Makes near-white pixels connected to the image border transparent. White areas
    // enclosed by the drawing (eyes, shirt) are not reached, so they stay white.
    public static Bitmap RemoveBackground(Bitmap source, int threshold)
    {
        var bmp = new Bitmap(source.Width, source.Height, PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(bmp)) { g.DrawImage(source, 0, 0, source.Width, source.Height); }
        var rect = new Rectangle(0, 0, bmp.Width, bmp.Height);
        var data = bmp.LockBits(rect, ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
        var bytes = new byte[data.Stride * bmp.Height];
        Marshal.Copy(data.Scan0, bytes, 0, bytes.Length);
        int w = bmp.Width, h = bmp.Height, stride = data.Stride;
        var seen = new bool[w * h];
        var queue = new Queue<int>();
        Func<int, int, bool> isBackground = (x, y) => {
            int i = y * stride + x * 4;
            return bytes[i] >= threshold && bytes[i + 1] >= threshold && bytes[i + 2] >= threshold;
        };
        for (int x = 0; x < w; x++) { queue.Enqueue(x); queue.Enqueue((h - 1) * w + x); }
        for (int y = 0; y < h; y++) { queue.Enqueue(y * w); queue.Enqueue(y * w + w - 1); }
        while (queue.Count > 0) {
            int p = queue.Dequeue();
            if (seen[p]) continue;
            seen[p] = true;
            int x = p % w, y = p / w;
            if (!isBackground(x, y)) continue;
            bytes[y * stride + x * 4 + 3] = 0;
            if (x > 0) queue.Enqueue(p - 1);
            if (x < w - 1) queue.Enqueue(p + 1);
            if (y > 0) queue.Enqueue(p - w);
            if (y < h - 1) queue.Enqueue(p + w);
        }
        Marshal.Copy(bytes, 0, data.Scan0, bytes.Length);
        bmp.UnlockBits(data);
        return bmp;
    }

    // Smallest rectangle containing every non-transparent pixel.
    public static Rectangle Bounds(Bitmap bmp)
    {
        int minX = bmp.Width, minY = bmp.Height, maxX = -1, maxY = -1;
        var rect = new Rectangle(0, 0, bmp.Width, bmp.Height);
        var data = bmp.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        var bytes = new byte[data.Stride * bmp.Height];
        Marshal.Copy(data.Scan0, bytes, 0, bytes.Length);
        bmp.UnlockBits(data);
        for (int y = 0; y < bmp.Height; y++)
            for (int x = 0; x < bmp.Width; x++)
                if (bytes[y * data.Stride + x * 4 + 3] > 0) {
                    if (x < minX) minX = x; if (x > maxX) maxX = x;
                    if (y < minY) minY = y; if (y > maxY) maxY = y;
                }
        return Rectangle.FromLTRB(minX, minY, maxX + 1, maxY + 1);
    }

    public static Bitmap CropResize(Bitmap source, Rectangle crop, int width, int height)
    {
        var result = new Bitmap(width, height, PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(result)) {
            g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.HighQuality;
            g.DrawImage(source, new Rectangle(0, 0, width, height), crop, GraphicsUnit.Pixel);
        }
        return result;
    }
}
'@

$original = [System.Drawing.Bitmap]::new($Source)
$clear = [Artwork]::RemoveBackground($original, 245)
$bounds = [Artwork]::Bounds($clear)
"bounds: x=$($bounds.X) y=$($bounds.Y) w=$($bounds.Width) h=$($bounds.Height)"

# Full figure: trimmed with a small margin, scaled to 480 px tall (2x a 240 px display).
$pad = 8
$full = [System.Drawing.Rectangle]::FromLTRB(
    [Math]::Max(0, $bounds.Left - $pad), [Math]::Max(0, $bounds.Top - $pad),
    [Math]::Min($clear.Width, $bounds.Right + $pad), [Math]::Min($clear.Height, $bounds.Bottom + $pad))
$height = 480
$width = [int][Math]::Round($full.Width * $height / $full.Height)
$out = [Artwork]::CropResize($clear, $full, $width, $height)
$out.Save((Join-Path $OutDir 'waiter-full.png'), [System.Drawing.Imaging.ImageFormat]::Png)
"full: ${width}x${height}"
$out.Dispose()

if ($Avatar.Count -eq 3) {
    # Erase the tray (left of the ear, below eye level) so the avatar shows only him.
    $g = [System.Drawing.Graphics]::FromImage($clear)
    $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
    $g.FillRectangle([System.Drawing.Brushes]::Transparent, 0, 250, 462, $clear.Height - 250)
    $g.FillRectangle([System.Drawing.Brushes]::Transparent, 0, 300, 472, $clear.Height - 300)
    $g.Dispose()
    $square = [System.Drawing.Rectangle]::new($Avatar[0], $Avatar[1], $Avatar[2], $Avatar[2])
    $avatarOut = [Artwork]::CropResize($clear, $square, 160, 160)
    $avatarOut.Save((Join-Path $OutDir 'waiter-avatar.png'), [System.Drawing.Imaging.ImageFormat]::Png)
    "avatar: 160x160 from x=$($Avatar[0]) y=$($Avatar[1]) size=$($Avatar[2])"
    $avatarOut.Dispose()
}

$clear.Dispose()
$original.Dispose()
