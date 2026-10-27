# Astronomy with Astropy

Read this when code handles physical units in astronomy, celestial coordinates and catalog cross-matching, time scales and barycentric corrections, FITS images and tables, world coordinate systems (WCS) or cosmological distances.

## Setup and versions

- Astropy 6.x (2023 to 2024) and 7.x (from late 2024) are the current lines; 7.x supports only recent Python versions. Check `astropy.__version__` and read that version's documentation for anything below that looks version-sensitive.
- Affiliated packages cover common next steps: `astroquery` (archive and catalog queries), `photutils` (photometry), `specutils` (spectra), `reproject` (regridding images between WCS), `regions`, `ccdproc`, `astroplan` (observation planning).
- **Offline and reproducible environments.** Astropy may download Earth-orientation (IERS) tables for UT1 and polar motion when transforming to Earth-based frames for recent dates, and updated leap-second tables. Bundled tables ship in the `astropy-iers-data` package. On machines without network access, set `astropy.utils.iers.conf.auto_download = False`, accept and report the reduced precision for dates beyond the bundled tables, and pin `astropy-iers-data` for reproducibility. `EarthLocation.of_site` also downloads a site registry; give explicit coordinates instead.

## Units and quantities

```python
import astropy.units as u
from astropy import constants as const

wavelength = 656.28 * u.nm
frequency = wavelength.to(u.THz, equivalencies=u.spectral())
energy = wavelength.to(u.eV, equivalencies=u.spectral())
velocity = (6563.5 * u.AA).to(u.km / u.s, equivalencies=u.doppler_optical(6562.8 * u.AA))
flux_nu = (2.0e-17 * u.erg / u.s / u.cm**2 / u.AA).to(u.mJy, equivalencies=u.spectral_density(wavelength))
```

- Arithmetic on `Quantity` checks dimensions; a `UnitConversionError` is a found bug, not an obstacle to suppress with `.value`.
- Domain conversions need explicit equivalencies: `spectral()`, `spectral_density(wav)`, `doppler_radio`, `doppler_optical`, `doppler_relativistic`, `parallax()`, `temperature()`, `brightness_temperature(freq)`, `dimensionless_angles()`.
- Magnitudes are logarithmic units (`u.mag`, `u.ABmag`, `u.STmag`); adding magnitudes is not adding fluxes.
- Enforce units at function boundaries with `@u.quantity_input`; use `QTable` when table columns should be full `Quantity` objects.
- In hot loops, convert once and strip units with `x.to_value(u.m)`; `Quantity` arithmetic has overhead.
- Constants come with units and a cited source (`const.G`, `const.c`); the values follow a specific CODATA and IAU release, recorded in `astropy.constants`.

## Time

```python
from astropy.time import Time
import astropy.units as u
from astropy.coordinates import SkyCoord, EarthLocation

t = Time("2026-03-20T03:15:00", scale="utc")
print(t.tt.isot, t.tdb.jd, (t.tai - t.utc).to(u.s))       # TAI - UTC in seconds (leap seconds)
site = EarthLocation.from_geodetic(lon=-155.4681 * u.deg, lat=19.8253 * u.deg, height=4205 * u.m)
star = SkyCoord(ra=279.2347 * u.deg, dec=38.7837 * u.deg, frame="icrs")
t_bary = t.tdb + t.light_travel_time(star, kind="barycentric", location=site)
rv_correction = star.radial_velocity_correction(kind="barycentric", obstime=t, location=site)
```

- Scales matter: UTC (with leap seconds), TAI, TT, TDB (barycentric dynamical time, for solar-system and pulsar or exoplanet timing), UT1 (Earth rotation).
- `Time` stores two doubles internally. A single float Julian date near 2.46 million days resolves only about 50 microseconds; keep `Time` objects (or `jd1` and `jd2`) for precise work.
- Python `datetime` arithmetic ignores leap seconds; `Time` handles them.
- Warnings about "dubious year" mean dates outside the leap-second table's validity; read them.

## Coordinates and cross-matching

- Build arrays of coordinates in one `SkyCoord`, never loops of scalars: vectorized transforms are orders of magnitude faster.
- Pick frames explicitly: ICRS for modern catalogs, FK5 with an equinox for older ones, Galactic, and the several ecliptic variants (geocentric, barycentric, mean or true), which are not interchangeable.
- `AltAz` needs `obstime` and `location`; atmospheric refraction is applied only when you pass pressure (and ideally temperature, humidity, wavelength).
- **Epochs and proper motion.** Catalogs refer to different epochs (Gaia DR3 positions are at J2016.0). For high proper-motion objects, propagate with `apply_space_motion(new_obstime=...)` before matching, supplying distance and radial velocity where known, and read any warnings about missing values.

```python
from astropy.coordinates import SkyCoord
import astropy.units as u

idx, sep2d, _ = sources.match_to_catalog_sky(catalog)       # nearest neighbor for every source
matched = sep2d < 1.0 * u.arcsec                           # always apply a separation limit
pairs = sources.search_around_sky(catalog, 2.0 * u.arcsec)  # all pairs within a radius
```

- Nearest-neighbor matching always returns a match; without a separation limit every source "matches" something. Choose the limit from the astrometric uncertainties of both catalogs and check for one-to-many matches.

## FITS files

```python
from astropy.io import fits

with fits.open("image.fits") as hdul:          # memory-mapped by default
    hdul.info()
    header = hdul[0].header
    data = hdul[0].data.copy()                 # copy before the file closes if you keep the array
exptime = header.get("EXPTIME")
```

- **Axis order:** NumPy indexes `data[y, x]`, with the last axis being `NAXIS1`. FITS header pixel conventions (`CRPIX`) are 1-based; Astropy WCS methods `pixel_to_world` and `world_to_pixel` are 0-based and take `x` first.
- **Scaling:** `BSCALE` and `BZERO` are applied on read and produce floats; pass `do_not_scale_image_data=True` to keep the raw integers.
- **Byte order:** FITS data are big-endian. Some libraries need native order: `data.astype(data.dtype.newbyteorder("="))` (NumPy 2 removed the array method `newbyteorder`).
- **Writing:** `writeto(..., overwrite=False)` is the default; keep it, so raw data is never replaced. Add `checksum=True` to write integrity keywords. Repair non-standard headers deliberately with `verify("fix")` and note it.
- Large or compressed images: use `.section[...]` to read cutouts without loading everything.

## World coordinate systems

```python
from astropy.wcs import WCS
from astropy.nddata import Cutout2D
import astropy.units as u

w = WCS(header)
sky = w.pixel_to_world(1023.5, 511.0)
x, y = w.world_to_pixel(sky)                    # round trip: should reproduce the input pixel
cutout = Cutout2D(data, position=sky, size=(64, 64), wcs=w)   # keeps a matching WCS
```

- `w.celestial` drops spectral or other axes; SIP distortion terms in headers are honored by the high-level methods.
- Check a WCS with a round trip and with a few known sources at catalog positions.
- Regrid images with `reproject` (`reproject_exact` conserves flux; interpolation-based methods do not).

## Tables

- `Table.read("catalog.fits", hdu=1)`; `QTable` keeps units as `Quantity`; ECSV is the text format that preserves units, data types and metadata.
- `join`, `vstack`, `hstack` and masked values handle catalog manipulation; `to_pandas()` drops units, so convert to plain values with explicit unit names first.

## Cosmology

```python
from astropy.cosmology import Planck18, FlatLambdaCDM, z_at_value
import astropy.units as u

d_l = Planck18.luminosity_distance(1.5)
age = Planck18.age(1.5)
z = z_at_value(Planck18.luminosity_distance, 10 * u.Gpc, zmax=10)   # bracket for multi-valued functions
toy = FlatLambdaCDM(H0=70 * u.km / u.s / u.Mpc, Om0=0.3)
```

- Name the cosmology in every report; results differ measurably between parameter sets.
- Watch little-h conventions (`Mpc/h`) in catalogs and simulations; convert explicitly.

## Data access, citation and terms

- Archive queries (`astroquery` for MAST, Gaia, SIMBAD, VizieR, IRSA and others) are network calls: cache results, respect rate limits, and record query parameters and the data release.
- Follow each archive's acknowledgment and citation policy, and respect proprietary periods on recent observations.
- Astropy asks users to cite its papers; `astropy.__citation__` prints the entries.

## Checks (done when)

- [ ] Quantities carry units end to end; conversions use explicit equivalencies; no `.value` used to silence a unit error.
- [ ] Time scale stated for every time; precise timing kept in `Time` objects; IERS behavior known for the environment.
- [ ] Cross-matches use a justified separation limit, handle epochs and report duplicates.
- [ ] FITS reads respect axis order, scaling and byte order; raw files were never overwritten.
- [ ] WCS checked with a round trip and known sources; the cosmology is named in results.

## Anti-patterns

- Loops over scalar `SkyCoord` objects.
- Nearest-neighbor matches without a separation limit.
- Float Julian dates for sub-millisecond timing.
- Mixing 0-based and 1-based pixel coordinates.
- Silent IERS downloads in a pipeline that must be reproducible offline.
