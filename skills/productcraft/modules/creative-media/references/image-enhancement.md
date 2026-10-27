# Image enhancement with local open tools

Read this to make images look better or fit their use: upscale, denoise, sharpen, fix exposure and color, remove a background, straighten orientation, strip location data, and export the right format and size. Everything runs locally with open tools: Pillow, OpenCV, ImageMagick, exiftool, Real-ESRGAN and rembg (versions current in 2025-2026; check what is installed). Ask before installing anything, and never upload a user's images to an online service without permission.

Contents: be honest about what enhancement does · first ask whether to re-capture · pick the operation · recipes · color, orientation and metadata · formats and sizes · batch work and untrusted files · check it · done when.

## Be honest about what enhancement does

- **Resizing, sharpening, denoising and tone changes** rearrange information that is in the image.
- **AI upscaling, face restoration and generative fill invent detail** that was never captured. The result can look sharp and be wrong: changed text, altered faces, plausible but false texture.
- So: never use generative enhancement on evidence, identity documents, medical or scientific images, news photographs or anything where the exact content matters; say "upscaled with an AI model" where the use calls for it; never describe an AI upscale as "restored" or "recovered" detail.
- **Keep the original untouched.** Write outputs to a new folder or with a suffix, and record the steps and parameters.

## First ask whether to re-capture

The best fix for a blurry or small image is often a better input:
- **Screenshots and UI images:** capture again at 2x device scale instead of upscaling. With Playwright, `browser.new_context(device_scale_factor=2)`; on high-density laptop screens the system screenshot tool already captures at 2x. Upscalers smear small text.
- **Exports from design tools, charts and documents:** export again at the needed size, or as SVG or PDF.
- **Photos:** ask for the original file rather than a compressed copy from a chat app or a social site, which has been resized and recompressed.

## Pick the operation

| Problem | Try first | Then, if needed |
|---|---|---|
| Slightly too small (up to about 1.5x) | Lanczos resize (Pillow or ImageMagick) plus light sharpening | |
| Much too small, photo or illustration | Real-ESRGAN 2x or 4x (`realesrgan-x4plus` for photos, the anime model for flat illustration) | Downscale the 4x result to the exact size needed |
| Noise from high ISO or low light | OpenCV non-local means denoising, mild | A learned denoiser, checked at 100% for smeared detail |
| JPEG blocks and ringing | Start again from a better copy; else mild denoise, then save once as PNG or high-quality JPEG | |
| Soft but in focus | Unsharp mask at the final output size | |
| Dull, flat or dark | Auto-contrast with a small cutoff; CLAHE on lightness for uneven light | Manual levels or curves |
| Color cast | Gray-world or a manual white point from a neutral area | |
| Background removal | rembg with a general model; alpha matting for hair and fur | Manual mask cleanup |
| Wrong orientation | Apply the EXIF orientation (`exif_transpose`) | |
| Location or camera data must not be published | Strip metadata, keeping the color profile | |

Order matters: orientation, then color conversion, then denoise, then resize, then tone, then sharpen last at the output size, then export.

## Recipes

A careful Pillow pipeline for a photo going to the web:

```python
import io
from PIL import Image, ImageCms, ImageFilter, ImageOps

Image.MAX_IMAGE_PIXELS = 80_000_000            # refuse decompression bombs from untrusted files

def to_srgb(im: Image.Image) -> Image.Image:
    icc = im.info.get("icc_profile")
    if icc:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        im = ImageCms.profileToProfile(im, src, ImageCms.createProfile("sRGB"), outputMode="RGB")
    return im.convert("RGB")

im = Image.open("in/photo.jpg")
im = ImageOps.exif_transpose(im)               # bake in the camera's orientation flag
im = to_srgb(im)
im.thumbnail((2000, 2000), Image.Resampling.LANCZOS, reducing_gap=3.0)   # only ever shrinks
im = ImageOps.autocontrast(im, cutoff=0.5)
im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=70, threshold=3))
im.save("out/photo.jpg", quality=85, optimize=True, progressive=True)     # EXIF and GPS are not copied
```

Denoise and local contrast with OpenCV:

```python
import cv2

img = cv2.imread("in/night.jpg")                               # BGR, 8-bit
den = cv2.fastNlMeansDenoisingColored(img, None, h=5, hColor=5, templateWindowSize=7, searchWindowSize=21)
lab = cv2.cvtColor(den, cv2.COLOR_BGR2LAB)
l, a, b = cv2.split(lab)
l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)  # lifts shadows without blowing highlights
cv2.imwrite("out/night.png", cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR))
```

Start with small `h` values (3-6); high values erase texture and make skin look plastic. OpenCV drops ICC profiles and EXIF orientation; apply orientation first and convert to sRGB first if color matters.

Upscale with Real-ESRGAN (BSD-3-Clause). The portable Vulkan build runs on most GPUs, and on CPU slowly, without a Python stack:

```bash
realesrgan-ncnn-vulkan -i in/small.jpg -o out/small-x4.png -n realesrgan-x4plus -s 4
# then shrink to the exact target size, which also hides some artifacts
magick out/small-x4.png -filter Lanczos -resize 1600x out/small-1600.png
```

The Python package depends on an older deep-learning library stack that breaks with recent torchvision releases; the portable binary avoids that. Face-restoration models change identity and some carry non-commercial licenses; do not apply them to photos of real people for anything documentary.

Remove a background with rembg (MIT):

```bash
pip install "rembg[cpu,cli]"                          # ask first; models download on first use
rembg i -m birefnet-general in/product.jpg out/product.png
rembg i -a -m isnet-general-use in/portrait.jpg out/portrait.png   # -a: alpha matting for hair edges
rembg p -m u2net in/ out/                              # a folder
```

Check each model's license on its model card before commercial use: some background-removal weights are licensed for non-commercial use only. Inspect edges against both a light and a dark background, since halos hide on one and show on the other. Cutting out a person and placing them in a new scene changes the meaning of a photo; that needs their consent and, in journalism or evidence, should not be done.

ImageMagick for quick command-line work (ImageMagick 7 uses `magick`; version 6 uses `convert`):

```bash
magick in.png -filter Lanczos -resize 150% -unsharp 0x1+0.6+0.02 out.png
magick in.jpg -auto-orient -strip -quality 85 out.jpg     # -strip also removes the color profile; see below
```

## Color, orientation and metadata

- **Color profiles:** convert wide-gamut images (Display P3, Adobe RGB) to sRGB for the web, or keep the embedded profile; stripping the profile from a P3 photo makes it look washed out or oversaturated.
- **Orientation:** phones store rotation as an EXIF flag. Apply it before any processing, or the output appears rotated in some viewers.
- **Privacy:** photos carry GPS coordinates, device serial numbers and capture times. Remove them from anything published unless the user wants them kept. exiftool removes everything except the color profile: `exiftool -all= --icc_profile:all -o out/ in/photo.jpg` (writing to a new folder keeps the original). Check with `exiftool -gps:all out/photo.jpg` that nothing remains.
- **Archive copies** keep their metadata; strip only the published derivative.

## Formats and sizes

| Content | Format | Notes |
|---|---|---|
| Screenshots, UI, diagrams, text | PNG or lossless WebP | JPEG blurs text edges; quantizing to a palette (for example with pngquant) shrinks flat UI images a lot |
| Photos for the web | JPEG quality 80-88, WebP or AVIF with a JPEG fallback | Serve several widths with `srcset`; most phones need no more than about 1600-2000 px wide for a full-width image |
| Cutouts with transparency | PNG or WebP with alpha | JPEG has no alpha |
| Print | TIFF or high-quality JPEG at 300 ppi at the printed size | See `posters-and-canvas.md` |
| Masters and intermediate steps | 16-bit PNG or TIFF | Avoid saving JPEG repeatedly; each save loses quality |

Page-weight and responsive-image practice belongs to `../../engineering-practices/references/performance.md` when the images ship in an app.

## Batch work and untrusted files

- Process a copy into a new folder; never overwrite inputs. Keep a log of the operation, parameters and tool versions.
- Run one sample first and review it before the batch. Name outputs predictably (`name-x2.png`, `name-web.jpg`).
- Images from users or the internet are untrusted input. Cap pixel counts (`Image.MAX_IMAGE_PIXELS`), file size and frame counts; process in an isolated worker for app features (`../../launchguard/references/security-baseline.md`, file uploads).
- ImageMagick delegates some formats (PostScript, PDF, SVG, MVG, MSL) to other parsers with a history of serious vulnerabilities. For untrusted input, restrict coders in its `policy.xml` to the formats you expect, and keep ImageMagick, Ghostscript and Pillow updated.

## Check it

1. Compare before and after side by side at 100% on the areas that matter (faces, text, edges, fine texture), not only scaled to fit the screen. A contact sheet helps for batches (`../../documents/references/convert-and-render.md`).
2. Look for halos from over-sharpening, smeared or plastic texture from denoising, invented detail or changed text from upscaling, and fringes on cutouts.
3. Read back dimensions, mode, color profile and file size:

```python
from PIL import Image
im = Image.open("out/photo.jpg")
exif = im.getexif()
print(im.size, im.mode, "ICC" if im.info.get("icc_profile") else "no ICC", "GPS" if 0x8825 in exif else "no GPS")
```

4. Where a clean reference exists (a denoise test on a deliberately noised copy), a structural-similarity score from scikit-image can compare settings; it does not replace looking.
5. Confirm metadata stripping on published files, and that originals are unchanged.

## Done when

- Outputs meet the target size, format and file-size budget, with the color profile handled and orientation correct.
- The before-and-after comparison at 100% shows improvement without halos, smearing or invented content in places that matter; AI upscaling is disclosed where the use requires it.
- Originals are untouched; the steps, parameters and tool versions are recorded.
- Published copies carry no GPS or private metadata unless the user chose to keep it; model licenses allow the intended use.
