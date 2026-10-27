# Medical imaging with DICOM: pydicom, volumes and derived objects

Read this when code reads, converts, analyzes or writes DICOM files (CT, MR, PET, X-ray, ultrasound, mammography, secondary captures, segmentations, structured reports), builds 3D volumes from a series, talks to a PACS or a DICOMweb server, or prepares images for a model. De-identification is in `clinical-deidentification.md`, public imaging archives in `public-imaging-data.md`, and whole-slide microscopy in `whole-slide-pathology.md`.

**Guardrail.** This is engineering and research practice, not diagnosis. Images and model outputs are never read as a clinical finding for a person. Work on de-identified copies, never on the only copy, and never write to a clinical PACS without explicit permission.

## Which tool

| Need | Use | Not for |
|---|---|---|
| Read and edit headers, pull pixels from single files, write simple files | pydicom | Building correctly oriented volumes by hand when a reader can do it |
| A series as a 3D image with spacing, origin and direction; resampling; NIfTI output | SimpleITK (or ITK) | Editing DICOM attributes |
| Batch conversion to NIfTI with JSON sidecars (neuroimaging, BIDS) | `dcm2niix` command-line tool | Keeping DICOM-only metadata such as private tags |
| NIfTI read and write, affines | nibabel | DICOM input |
| Standard derived objects: segmentations (SEG), structured reports (SR), parametric maps, microscopy annotations | highdicom | Ad hoc hand-built SOP instances |
| DIMSE networking: C-ECHO, C-FIND, C-MOVE, C-GET, C-STORE | pynetdicom | Web-based archives |
| DICOMweb: QIDO-RS search, WADO-RS retrieve, STOW-RS store | dicomweb-client | Classic DIMSE PACS |
| Deep-learning loading and transforms | MONAI (`LoadImage`, `Spacingd`, `Orientationd`) | Header editing |
| Look at the result | 3D Slicer, OHIF, Weasis, or a test PACS such as Orthanc | Judging a clinical finding |
| Validate a file against the standard | `dciodvfy` from dicom3tools | |

## Setup and versions

```bash
python -m pip install "pydicom>=3" numpy
python -m pip install pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg pylibjpeg-rle   # compressed pixel data (or python-gdcm)
python -m pip install SimpleITK highdicom
python -c "import pydicom; print(pydicom.__version__)"
```

- pydicom 3.0 (2024) needs Python 3.10 or later. Pixel functions moved to `pydicom.pixels` (`apply_modality_lut`, `apply_voi_lut`, `pixel_array`, `iter_pixels`); `pydicom.pixel_data_handlers` is deprecated and scheduled for removal in 4.0. `save_as(write_like_original=...)` gave way to `enforce_file_format`. Code written for 2.x often still runs but warns; check the installed version before copying examples.
- Decoding compressed pixel data needs a plugin (pylibjpeg family or GDCM). "Unable to decode pixel data" means the plugin for that transfer syntax is missing, not that the file is broken.
- highdicom builds on pydicom and follows the standard closely; read its docs for the current constructor signatures.

## The data model in five lines

- Patient > Study (`StudyInstanceUID`) > Series (`SeriesInstanceUID`) > Instance (`SOPInstanceUID`). A file is usually one instance; an enhanced multi-frame instance can hold a whole volume.
- The SOP Class (`SOPClassUID`) says what the object is: CT image, MR image, SEG, SR, secondary capture.
- Each attribute is a tag `(gggg,eeee)` with a value representation (VR). Sequences (VR `SQ`) nest whole datasets; odd groups are vendor-private tags owned by a private creator string.
- The transfer syntax (`ds.file_meta.TransferSyntaxUID`) fixes byte order, implicit or explicit VR, and pixel compression.
- `FrameOfReferenceUID` ties images that share one patient coordinate system; segmentations and registrations depend on it.

## Read headers fast and safely

```python
from pydicom import dcmread

ds = dcmread(path, stop_before_pixels=True)          # metadata scans: skip the pixel bytes
modality = ds.get("Modality")                        # None when absent, no AttributeError
uids = dcmread(path, specific_tags=["StudyInstanceUID", "SeriesInstanceUID"])   # read only what you need
```

- Use `stop_before_pixels=True` or `specific_tags` when indexing thousands of files; it is the largest speed-up available.
- Use `force=True` only for files known to lack the 128-byte preamble. On other files it "succeeds" on garbage.
- Read private attributes through their block, never by a hard-coded element number: `ds.private_block(0x0029, "SIEMENS CSA HEADER")`. Element offsets differ between files.
- Group files by `SeriesInstanceUID`, not by folder. Folders mix series, and one series can span folders.

## Pixel values: apply the pipeline in order

Stored values become meaningful values only after the modality transform. CT stored values are not Hounsfield units until `RescaleSlope` and `RescaleIntercept` are applied.

```python
import numpy as np
from pydicom import dcmread
from pydicom.pixels import apply_modality_lut, apply_voi_lut

ds = dcmread(path)
stored = ds.pixel_array                              # shape: (rows, cols), (frames, rows, cols) or (..., samples)
values = apply_modality_lut(stored, ds).astype(np.float32)   # CT: Hounsfield units; PET: often needs SUV scaling separately
shown = apply_voi_lut(values, ds, index=0)           # the file's first window, for display only
if ds.PhotometricInterpretation == "MONOCHROME1":    # low values display white
    shown = shown.max() - shown
```

- **Do not min-max normalize each image.** It destroys the unit (HU) and makes two scans incomparable. For models, clip to a fixed task window (for example a lung or soft-tissue window) and scale with constants.
- `PixelRepresentation` 1 means signed integers. Doing arithmetic in the stored `uint16` or `int16` dtype overflows silently; cast to float first.
- `BitsStored` can be smaller than `BitsAllocated`; high bits may hold overlay data in old files.
- Color: check `PhotometricInterpretation` (`RGB`, `YBR_FULL`, `YBR_FULL_422`, `PALETTE COLOR`). Decoders and pydicom versions differ in whether they convert YBR to RGB for you; convert exactly once and check a known color.
- PET SUV needs patient weight, injected dose, decay correction and timing attributes; compute it with a tested function and state the formula.
- PNG or JPEG exports are for viewing. Keep DICOM or NIfTI as the analysis source and never feed 8-bit windowed exports to a model that should see HU.

## From a series to a 3D volume

Let a reader do it unless you have a reason not to:

```python
import SimpleITK as sitk

reader = sitk.ImageSeriesReader()
series_ids = reader.GetGDCMSeriesIDs(folder)
files = reader.GetGDCMSeriesFileNames(folder, series_ids[0])
reader.SetFileNames(files)
image = reader.Execute()                    # rescale already applied: do not apply it again
print(image.GetSize(), image.GetSpacing(), image.GetOrigin(), image.GetDirection())
volume = sitk.GetArrayFromImage(image)      # numpy order is (z, y, x)
sitk.WriteImage(image, "ct.nii.gz")
```

When you must sort slices yourself:

```python
import numpy as np

def position_along_normal(ds):
    row, col = np.array(ds.ImageOrientationPatient[:3], float), np.array(ds.ImageOrientationPatient[3:], float)
    return float(np.dot(np.cross(row, col), np.array(ds.ImagePositionPatient, float)))

slices = sorted(datasets, key=position_along_normal)
gaps = np.diff([position_along_normal(s) for s in slices])
assert np.allclose(gaps, gaps[0], atol=1e-3), "uneven spacing, duplicates or mixed acquisitions"
```

- Sort by position projected on the slice normal. `InstanceNumber` and the raw z coordinate are wrong for oblique and some sagittal or coronal acquisitions.
- One series can hold several volumes: echoes, time points, diffusion directions, contrast phases, or a localizer. Split on `EchoNumbers`, `TemporalPositionIdentifier`, `AcquisitionNumber` or `ImageType` before stacking.
- `SliceThickness` is not slice spacing. Use the gaps between positions.
- `PixelSpacing` is `[row spacing, column spacing]`, that is `[y, x]` in millimeters.
- DICOM patient coordinates are LPS (x to the patient's left, y to posterior, z to head). NIfTI, nibabel and 3D Slicer use RAS. Flipping between them is the most common cause of mirrored segmentations; check a lateral landmark in a viewer.
- Enhanced multi-frame objects keep per-frame geometry in `PerFrameFunctionalGroupsSequence`; use a reader that understands them (SimpleITK recent versions, highdicom, or `dcm2niix`).

## Writing derived data

- Never overwrite an original. Write new files with new `SOPInstanceUID` and `SeriesInstanceUID`; keep the `StudyInstanceUID` and `FrameOfReferenceUID` only when the new series truly belongs to that study and space.
- Generate UIDs with `pydicom.uid.generate_uid()` (pass `prefix=None` for a UUID-derived `2.25.` UID, or your organization's registered root). Never invent UIDs by editing digits.
- Build SEG, SR and parametric maps with highdicom so references, segment descriptions and coded concepts are valid. A segmentation saved as a fake CT series, or as a mask PNG, loses its link to the images it describes.
- Record lossy compression: if pixels were ever lossy-compressed, `LossyImageCompression` is `01` and must stay so. Do not recompress lossy data for analysis.

## PACS and DICOMweb

- A hospital PACS is a production clinical system. Read only, with the owner's permission, throttled, outside peak hours. Develop against a local test server (Orthanc in a container, loaded with de-identified or public data).
- C-MOVE needs the remote archive configured to know your AE title, host and port; C-GET does not. Most "it connects but nothing arrives" problems are AE configuration, not code.
- DICOMweb is HTTP: authenticate with tokens kept out of code (`../../agent-safety/GUIDE.md`), paginate QIDO searches (`limit`, `offset`), and retry only idempotent reads.
- Never C-STORE or STOW-RS into a clinical archive, and never delete there, without explicit approval of the exact objects.

## Untrusted files

- The 128-byte preamble can carry another file format's header. A file can be both valid DICOM and a valid Windows executable (CVE-2019-11687). Never execute or open received files with anything but a DICOM reader, and scan them like any upload. Some legitimate files use the preamble for a TIFF header (dual-format whole-slide files), so do not zero it blindly.
- Parsers meet truncated files, huge declared lengths and deep nesting. Catch exceptions per file, log the file and reason, and continue; do not let one bad file stop a batch silently or kill the run.

## Performance and scale

- A 512 x 512 int16 slice is 0.5 MB; a 1,000-slice CT is about 0.5 GB as int16 and 1 GB as float32. Process one series at a time and free arrays.
- Metadata indexing: parallel processes with `stop_before_pixels=True`, results to Parquet (`../../data-engineering/references/storage-formats-and-zarr.md`).
- Decode compressed frames lazily with `pydicom.pixels.iter_pixels(path)` instead of materializing every frame.

## Checks (done when)

- The installed pydicom, SimpleITK and decoder versions are recorded.
- CT values are plausible after the modality transform (air near -1000 HU, water near 0 HU, fat negative).
- Volumes have the expected slice count, uniform spacing and a direction matrix that a viewer shows the right way round (check left and right on a known landmark).
- Derived objects open in an independent viewer, reference the correct series, and pass `dciodvfy` or the highdicom round trip.
- Any file that leaves the machine passed `clinical-deidentification.md`, including `../scripts/dicom_phi_check.py` with no unresolved HIGH findings.
- Nothing was written to, or deleted from, a clinical archive.
