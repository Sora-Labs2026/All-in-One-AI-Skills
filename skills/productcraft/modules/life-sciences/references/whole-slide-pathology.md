# Whole-slide pathology: reading, tiling, stain handling and QC

Read this when the input is a whole-slide image (WSI) of a tissue section, H&E, IHC or multiplexed immunofluorescence, and the task is tissue detection, tile extraction, stain normalization, nucleus or tissue models, slide-level prediction or dataset preparation. Image servers such as OMERO are in `microscopy-image-servers.md`; DICOM WSI headers follow `dicom-imaging.md`.

**Guardrail.** Research and engineering only. A model score on a slide is not a pathology diagnosis. Slide labels and file names often carry patient identifiers; strip them before sharing (`clinical-deidentification.md`).

## Formats and readers

A WSI is a pyramid: level 0 at full resolution, then downsampled levels, stored as tiles. Formats include Aperio SVS, Hamamatsu NDPI and VMS, 3DHISTECH MRXS (a folder plus an index file, both required), Leica SCN, Ventana BIF, Philips iSyntax (vendor SDK), generic tiled TIFF, OME-TIFF and OME-Zarr, and DICOM WSI (VL Whole Slide Microscopy, one instance per level).

| Reader | Strengths | License and notes |
|---|---|---|
| OpenSlide (`openslide-python`, `openslide-bin` wheels) | The standard reader for vendor formats; 4.0 (2023) added DICOM WSI | LGPL-2.1; C library |
| tiffslide | Pure Python, OpenSlide-like API, reads from cloud storage through fsspec | BSD-3; TIFF-based formats only |
| wsidicom | DICOM WSI, including DICOMweb sources | Apache-2.0 |
| Bio-Formats (Java, via bindings or `bfconvert`) | Very wide format coverage, conversion to OME-TIFF | GPL-2.0; JVM required |
| cuCIM | GPU-accelerated reading and transforms | Apache-2.0; NVIDIA GPUs |

Pipeline libraries: **histolab** (Apache-2.0; tissue masks and random, grid or score-based tilers, simple and readable), **TIAToolbox** (BSD-3; tiling, stain normalization, pretrained patch and nucleus models, broad tooling), **PathML** (GPL-2.0; preprocessing pipelines with HDF5 storage, HoVer-Net, multiplexed imaging with Mesmer cell segmentation). GPL code shipped inside a product carries copyleft obligations; check before adopting it. QuPath (GPL-3.0, desktop) is the usual tool for pathologists to annotate and review.

## Resolution: work in microns per pixel

```python
import openslide

slide = openslide.OpenSlide("case.svs")
mpp_x = float(slide.properties.get(openslide.PROPERTY_NAME_MPP_X, "nan"))   # microns per pixel at level 0
print(slide.dimensions, slide.level_count, slide.level_downsamples, mpp_x)

target_mpp = 0.5                                       # about "20x"; state the value, not the objective name
level = slide.get_best_level_for_downsample(target_mpp / mpp_x)
```

- Choose tile size and resolution in microns per pixel (MPP), not by level index or "magnification". Level structure and objective metadata differ between scanners, and the objective-power field is often missing or wrong. If MPP is missing, stop and ask; do not assume 0.25.
- When the nearest level is not exactly the target MPP, read at the next finer level and resize, and record the actual scale.
- `read_region((x, y), level, (w, h))` takes `(x, y)` in **level-0 coordinates** and `(w, h)` in pixels **of the chosen level**. Mixing the two is the classic off-by-a-downsample bug.
- It returns RGBA; transparent pixels outside the scanned area must be composited onto white before conversion to RGB, or they become black "tissue".

```python
from PIL import Image

def read_rgb(slide, x0, y0, level, size):
    rgba = slide.read_region((x0, y0), level, (size, size))
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, rgba).convert("RGB")
```

## The standard workflow

1. **Inventory and QC slides:** format, MPP, dimensions, stain, scanner, associated images; flag slides with missing MPP, failed focus or tissue missing.
2. **Tissue mask on a thumbnail:** threshold on saturation or grayscale (Otsu), then morphological opening and hole filling, then remove small objects. histolab's `TissueMask` and TIAToolbox's tissue masking do this. Look at the mask over the thumbnail for every new site or stain.
3. **Tile grid at fixed MPP:** for example 256 or 512 pixels at 0.5 MPP, keeping tiles above a tissue fraction (commonly 50 to 80 percent) inside the mask. Save coordinates and the parameters, not only image files.
4. **Tile QC:** blur (variance of the Laplacian), pen marks (strong blue, green or black hues), tissue folds, bubbles and out-of-focus regions. Report how many tiles each filter removed.
5. **Stain handling** (below), then features or a model, then aggregation to the slide (attention-based multiple-instance learning is the common default for slide labels).
6. **Evaluate at the patient level** with the split rules below.

Preview before extracting: draw the tile grid on the thumbnail (histolab `locate_tiles`, or your own overlay) and check it covers tissue and skips background and pen.

## Stain variation

H&E color differs by lab, staining batch and scanner, and a model learns those differences as shortcuts.

- **Normalization** maps each tile to a reference appearance: Reinhard (color statistics in Lab space, fast, crude), Macenko (stain vectors from optical density, the common default), Vahadane (sparse non-negative factorization, more robust, slower). Fit the reference on a tissue-rich tile from the training data and keep it fixed. Estimating stain vectors on tiles that are mostly background or pen produces garbage; estimate per slide on tissue tiles.
- **Augmentation** in HED or HSV space during training often generalizes as well as or better than normalization; many pipelines do both or only augmentation.
- These methods are for brightfield H&E. IHC needs stain-specific handling (color deconvolution with the right vectors), and fluorescence channels are intensities, not colors.

## Splits and shortcuts

- One patient can have many slides and blocks: split by patient. Hold out whole sites or scanners to test generalization, because site, scanner and stain batch are easy shortcuts.
- Labels from reports are slide- or case-level; do not treat every tile in a positive slide as positive when training tile classifiers without saying so.
- See `../../ml-engineering/references/evaluation-and-leakage.md` for group splits and comparisons with confidence intervals.

## Scale and storage

- A 100,000 by 80,000 pixel slide is 8 gigapixels, about 24 GB as raw RGB. Never read level 0 whole. Read tiles, in parallel workers that each open their own slide handle.
- Millions of tile PNGs strain file systems. Store tiles or features in HDF5 or Zarr with coordinates and slide IDs (`../../data-engineering/references/storage-formats-and-zarr.md`), and regenerate tiles from coordinates when needed.
- Pretrained pathology foundation models are often gated or licensed for non-commercial research only. Record the model, version and license next to extracted features.

## Privacy

- Associated images (`slide.associated_images["label"]` and `"macro"`) often show the paper label with the patient name, accession number or barcode. Drop them, and the matching DICOM WSI label instances, before sharing.
- File names, TIFF `ImageDescription` fields and vendor metadata can hold accession numbers, dates, operator names and scanner serials. Rename files to study IDs and review the metadata dump.

## Checks (done when)

- MPP, tile size, level and resize factor are recorded per slide; slides without MPP are listed, not guessed.
- Tissue masks and tile grids were inspected on thumbnails for each site and stain.
- Tile QC filters report counts removed; the stain method and its reference tile are saved.
- Splits are by patient, with site or scanner held out for the generalization check.
- Label and macro images and identifying metadata are gone from anything shared; tool, model and dataset licenses are listed.
