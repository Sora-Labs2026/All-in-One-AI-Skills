# Microscopy image servers: OMERO from Python

Read this when images live on an OMERO server (an institutional install or a public resource such as the Image Data Resource) and code must list projects or plates, read pixels or tiles, attach annotations, draw or read ROIs, store measurement tables or run batch scripts. Slide-level pathology methods are in `whole-slide-pathology.md`.

**Guardrail.** An image server is shared infrastructure that usually holds unpublished and sometimes clinical data. Read before write, write under your own namespace, never delete without the user's explicit approval of the exact objects, and keep credentials out of code and chat (`../../agent-safety/GUIDE.md`).

## Setup

```bash
# omero-py needs the ZeroC Ice 3.6 Python bindings; prebuilt wheels exist only for some Python versions and platforms
conda create -n omero -c conda-forge python=3.10 omero-py      # or pip with a matching zeroc-ice wheel, per the OMERO docs
python -c "import omero, omero.gateway; print(omero.__version__)"
```

- Ice is the usual install blocker. Use a dedicated environment and the Python version the current omero-py release supports; do not build Ice from source unless the docs say to.
- The server version and the client version should be compatible; check the server's version in the web client's about page.
- For bulk export and cloud-friendly access, many servers also expose images as OME-Zarr; prefer that over pulling every plane through the Python API when the server offers it.

## Connect

```python
import os
from omero.gateway import BlitzGateway

with BlitzGateway(os.environ["OMERO_USER"], os.environ["OMERO_PASSWORD"],
                  host=os.environ["OMERO_HOST"], port=4064, secure=True) as conn:
    if not conn.isConnected():
        raise SystemExit("login failed")       # connect() returns False rather than raising
    print(conn.getUser().getName(), conn.getGroupFromContext().getName())
```

- Credentials come from the environment or a keyring that the user set up, never literals. Prefer a read-only or least-privileged account for analysis.
- Sessions time out; long jobs should reconnect or keep the session alive and must close the connection at the end (the context manager does).
- Queries run in the current group. To search across all groups you can read, set `conn.SERVICE_OPTS.setOmeroGroup("-1")`; to write, switch to the target group explicitly.

## Data model

- Projects > Datasets > Images, and for high-content screening Screens > Plates > Wells > WellSamples (fields) > Images.
- An image has a pixels object with dimensions X, Y, Z (focal planes), C (channels) and T (time points), a pixel type, and physical sizes with units. Big images (whole slides) are pyramidal and must be read in tiles.
- Annotations attach to any object: map annotations (key-value pairs), tags, comments, file attachments and tables. A namespace string marks who wrote them and why.

## Read pixels efficiently

```python
image = conn.getObject("Image", image_id)
pixels = image.getPrimaryPixels()
size = (image.getSizeZ(), image.getSizeC(), image.getSizeT(), image.getSizeY(), image.getSizeX())
px_um = image.getPixelSizeX(units="MICROMETER")         # may be None: do not assume a scale

plane = pixels.getPlane(0, 0, 0)                         # argument order is z, c, t; returns a numpy array
zct = [(z, 1, 0) for z in range(image.getSizeZ())]
stack = list(pixels.getPlanes(zct))                      # one batched request instead of a loop of calls
tile = pixels.getTile(0, 0, 0, tile=(x, y, 512, 512))    # for large images
```

- The argument order is z, c, t for planes; mixing it up silently reads the wrong channel.
- Raw pixel values are what you analyze; rendered thumbnails and JPEG exports apply rendering settings and are for viewing only.
- Batch requests (`getPlanes`, `getTiles`) and run near the server when possible. Thousands of small round trips are slow for you and load the server for everyone.

## Write annotations, ROIs and tables

- **Namespaces.** Give every annotation your project's namespace, and before adding one, look for an existing annotation in that namespace on the same object, so reruns update instead of duplicating.
- **Map annotations** hold structured key-value results (analysis version, parameters, summary values). Keep keys stable across runs.

```python
from omero.gateway import MapAnnotationWrapper

NS = "org.example.lab/nuclei-count/v2"                  # your namespace, versioned with the analysis

def upsert_results(conn, image, pairs, apply=False):
    existing = [a for a in image.listAnnotations(ns=NS) if isinstance(a, MapAnnotationWrapper)]
    if not apply:                                        # dry run: report the plan
        return ("update" if existing else "create", image.getId(), pairs)
    if existing:
        existing[0].setValue([[k, str(v)] for k, v in pairs])
        existing[0].save()
    else:
        ann = MapAnnotationWrapper(conn)
        ann.setNs(NS)
        ann.setValue([[k, str(v)] for k, v in pairs])
        ann.save()
        image.linkAnnotation(ann)
```

Run it once without `apply`, show the planned creates and updates, then apply after approval and read one annotation back.
- **ROIs** hold shapes (rectangle, ellipse, line, point, polygon, mask) in pixel coordinates, optionally bound to a Z, C and T. Polygon points are a string of `x,y` pairs; masks need their bounding box and bytes. Read back one ROI after writing and draw it over the image to check placement.
- **OMERO.tables** store per-object measurements (for example one row per cell or well) linked to the image, plate or dataset, which keeps results queryable and next to the data. Define column types up front.
- **Server-side scripts** (OMERO.scripts) run batch jobs inside the server. Installing official scripts needs an administrator; a user script still runs with the user's permissions.

## Deletion and permissions

- `conn.deleteObjects(...)` is permanent and can cascade: deleting a container may delete its contents, annotations and ROIs depending on the options. Before any deletion, list the exact objects and what will cascade, show the list to the user, use a dry run where the installed version offers one, and proceed only on an explicit yes.
- Groups have permission levels (private, read-only, read-annotate, read-write). Do not move data between groups or change group permissions as a side effect of analysis; those are administrator decisions that can expose data.
- Clinical images on a research server still need de-identification and access control; file names and original-file metadata often carry identifiers.

## Checks (done when)

- The connection uses a least-privileged account with credentials from the environment and is closed at the end.
- The number of objects read and written is reported; writes carry a namespace and were verified by reading them back.
- Pixel reads use the correct z, c, t order and record physical sizes (or state that they are missing).
- No object was deleted, moved or re-permissioned without the user's explicit approval of the exact list.
