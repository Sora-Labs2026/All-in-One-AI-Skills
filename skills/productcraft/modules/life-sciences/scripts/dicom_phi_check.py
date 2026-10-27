#!/usr/bin/env python3
"""Check DICOM headers for identifying data left after de-identification.

Reads DICOM Part 10 files (128-byte preamble, "DICM", file meta group) with the
Python standard library only. It walks every data element, including nested
sequences, and reports attributes that still carry identifying values: patient
names and IDs, birth dates, addresses, accession and order numbers, staff names,
institution and device details, dates, free-text fields, private tags, ages over
89, UIDs outside an expected root, and header flags that warn about burned-in
text or recognizable faces in the pixel data.

It is a header check only. It never decodes pixel data, so burned-in text,
faces in 3D head volumes, label images on slides and embedded documents still
need their own review. A clean result is evidence for a review, not proof of
de-identification under HIPAA Safe Harbor, Expert Determination or GDPR.

Values are not printed unless --show-values is given, so the report itself does
not copy identifiers into logs or a chat.

Read-only: no file is modified, nothing is sent over the network.

Exit codes: 0 no HIGH findings (and no WARN findings with --strict);
1 findings at or above the threshold; 2 usage error, a file that could not be
parsed, or no DICOM files found.
"""

import argparse
import json
import mmap
import os
import re
import struct
import sys
import zlib

VERSION = "1.0"

UNDEFINED = 0xFFFFFFFF
ITEM = (0xFFFE, 0xE000)
ITEM_DELIM = (0xFFFE, 0xE00D)
SEQ_DELIM = (0xFFFE, 0xE0DD)
LONG_VRS = {"OB", "OD", "OF", "OL", "OV", "OW", "SQ", "SV", "UC", "UN", "UR", "UT", "UV"}
TEXT_VRS = {"AE", "AS", "CS", "DA", "DS", "DT", "IS", "LO", "LT", "PN", "SH", "ST", "TM", "UC", "UI", "UR", "UT"}
ILLEGAL_PRIVATE_GROUPS = {0x0001, 0x0003, 0x0005, 0x0007, 0xFFFF}

TS_IMPLICIT_LE = "1.2.840.10008.1.2"
TS_EXPLICIT_LE = "1.2.840.10008.1.2.1"
TS_DEFLATED_LE = "1.2.840.10008.1.2.1.99"
TS_EXPLICIT_BE = "1.2.840.10008.1.2.2"
STANDARD_UID_PREFIX = "1.2.840.10008."

SEVERITIES = ("HIGH", "WARN", "INFO")

# tag: (keyword, VR, category, severity)
# HIGH: identifies the patient directly. WARN: needs a decision or a review.
CHECKED = {
    # patient identifiers
    (0x0010, 0x0010): ("PatientName", "PN", "identifier", "HIGH"),
    (0x0010, 0x0020): ("PatientID", "LO", "identifier", "HIGH"),
    (0x0010, 0x0030): ("PatientBirthDate", "DA", "identifier", "HIGH"),
    (0x0010, 0x0032): ("PatientBirthTime", "TM", "identifier", "HIGH"),
    (0x0010, 0x1000): ("OtherPatientIDs", "LO", "identifier", "HIGH"),
    (0x0010, 0x1001): ("OtherPatientNames", "PN", "identifier", "HIGH"),
    (0x0010, 0x1002): ("OtherPatientIDsSequence", "SQ", "identifier", "HIGH"),
    (0x0010, 0x1005): ("PatientBirthName", "PN", "identifier", "HIGH"),
    (0x0010, 0x1040): ("PatientAddress", "LO", "identifier", "HIGH"),
    (0x0010, 0x1050): ("InsurancePlanIdentification", "LO", "identifier", "HIGH"),
    (0x0010, 0x1060): ("PatientMotherBirthName", "PN", "identifier", "HIGH"),
    (0x0010, 0x1090): ("MedicalRecordLocator", "LO", "identifier", "HIGH"),
    (0x0010, 0x2154): ("PatientTelephoneNumbers", "SH", "identifier", "HIGH"),
    (0x0010, 0x2155): ("PatientTelecomInformation", "LT", "identifier", "HIGH"),
    (0x0008, 0x0050): ("AccessionNumber", "SH", "identifier", "HIGH"),
    (0x0038, 0x0010): ("AdmissionID", "LO", "identifier", "HIGH"),
    (0x0040, 0x2016): ("PlacerOrderNumberImagingServiceRequest", "LO", "identifier", "HIGH"),
    (0x0040, 0x2017): ("FillerOrderNumberImagingServiceRequest", "LO", "identifier", "HIGH"),
    (0x0040, 0xA123): ("PersonName", "PN", "identifier", "HIGH"),
    # locations tied to the patient
    (0x0010, 0x2152): ("RegionOfResidence", "LO", "location", "WARN"),
    (0x0038, 0x0300): ("CurrentPatientLocation", "LO", "location", "WARN"),
    (0x0038, 0x0400): ("PatientInstitutionResidence", "LO", "location", "WARN"),
    # staff
    (0x0008, 0x0090): ("ReferringPhysicianName", "PN", "staff", "WARN"),
    (0x0008, 0x0092): ("ReferringPhysicianAddress", "ST", "staff", "WARN"),
    (0x0008, 0x0094): ("ReferringPhysicianTelephoneNumbers", "SH", "staff", "WARN"),
    (0x0008, 0x1048): ("PhysiciansOfRecord", "PN", "staff", "WARN"),
    (0x0008, 0x1050): ("PerformingPhysicianName", "PN", "staff", "WARN"),
    (0x0008, 0x1060): ("NameOfPhysiciansReadingStudy", "PN", "staff", "WARN"),
    (0x0008, 0x1070): ("OperatorsName", "PN", "staff", "WARN"),
    (0x0032, 0x1032): ("RequestingPhysician", "PN", "staff", "WARN"),
    (0x0040, 0x0006): ("ScheduledPerformingPhysicianName", "PN", "staff", "WARN"),
    (0x0040, 0x1010): ("NamesOfIntendedRecipientsOfResults", "PN", "staff", "WARN"),
    (0x0040, 0xA075): ("VerifyingObserverName", "PN", "staff", "WARN"),
    (0x0070, 0x0084): ("ContentCreatorName", "PN", "staff", "WARN"),
    # site and device
    (0x0008, 0x0080): ("InstitutionName", "LO", "site", "WARN"),
    (0x0008, 0x0081): ("InstitutionAddress", "ST", "site", "WARN"),
    (0x0008, 0x1040): ("InstitutionalDepartmentName", "LO", "site", "WARN"),
    (0x0008, 0x1010): ("StationName", "SH", "site", "WARN"),
    (0x0018, 0x1000): ("DeviceSerialNumber", "LO", "site", "WARN"),
    (0x0002, 0x0016): ("SourceApplicationEntityTitle", "AE", "site", "WARN"),
    # study-level identifiers that often equal hospital numbers
    (0x0020, 0x0010): ("StudyID", "SH", "study-id", "WARN"),
    (0x0040, 0x0009): ("ScheduledProcedureStepID", "SH", "study-id", "WARN"),
    (0x0040, 0x0253): ("PerformedProcedureStepID", "SH", "study-id", "WARN"),
    (0x0040, 0x1001): ("RequestedProcedureID", "SH", "study-id", "WARN"),
    # free text that people type identifiers into
    (0x0008, 0x1030): ("StudyDescription", "LO", "free-text", "WARN"),
    (0x0008, 0x103E): ("SeriesDescription", "LO", "free-text", "WARN"),
    (0x0008, 0x2111): ("DerivationDescription", "ST", "free-text", "WARN"),
    (0x0008, 0x4000): ("IdentifyingComments", "LT", "free-text", "WARN"),
    (0x0010, 0x21B0): ("AdditionalPatientHistory", "LT", "free-text", "WARN"),
    (0x0010, 0x4000): ("PatientComments", "LT", "free-text", "WARN"),
    (0x0018, 0x1030): ("ProtocolName", "LO", "free-text", "WARN"),
    (0x0020, 0x4000): ("ImageComments", "LT", "free-text", "WARN"),
    (0x0032, 0x1060): ("RequestedProcedureDescription", "LO", "free-text", "WARN"),
    (0x0032, 0x4000): ("StudyComments", "LT", "free-text", "WARN"),
    (0x0040, 0x0254): ("PerformedProcedureStepDescription", "LO", "free-text", "WARN"),
    (0x0040, 0x0280): ("CommentsOnThePerformedProcedureStep", "ST", "free-text", "WARN"),
    (0x0040, 0x1002): ("ReasonForTheRequestedProcedure", "LO", "free-text", "WARN"),
    (0x0040, 0x2400): ("ImagingServiceRequestComments", "LT", "free-text", "WARN"),
    (0x0040, 0xA160): ("TextValue", "UT", "free-text", "WARN"),
}

# Date and date-time attributes, used when the VR is not in the file (implicit VR).
# With explicit VR every DA and DT element is checked.
DATE_TAGS = {
    (0x0008, 0x0012): ("InstanceCreationDate", "DA"),
    (0x0008, 0x0015): ("InstanceCoercionDateTime", "DT"),
    (0x0008, 0x0020): ("StudyDate", "DA"),
    (0x0008, 0x0021): ("SeriesDate", "DA"),
    (0x0008, 0x0022): ("AcquisitionDate", "DA"),
    (0x0008, 0x0023): ("ContentDate", "DA"),
    (0x0008, 0x002A): ("AcquisitionDateTime", "DT"),
    (0x0010, 0x21D0): ("LastMenstrualDate", "DA"),
    (0x0018, 0x1012): ("DateOfSecondaryCapture", "DA"),
    (0x0018, 0x1200): ("DateOfLastCalibration", "DA"),
    (0x0018, 0x9074): ("FrameAcquisitionDateTime", "DT"),
    (0x0018, 0x9151): ("FrameReferenceDateTime", "DT"),
    (0x0038, 0x0020): ("AdmittingDate", "DA"),
    (0x0040, 0x0002): ("ScheduledProcedureStepStartDate", "DA"),
    (0x0040, 0x0244): ("PerformedProcedureStepStartDate", "DA"),
    (0x0040, 0x0250): ("PerformedProcedureStepEndDate", "DA"),
    (0x0040, 0xA030): ("VerificationDateTime", "DT"),
    (0x0040, 0xA032): ("ObservationDateTime", "DT"),
    (0x0040, 0xA120): ("DateTime", "DT"),
    (0x0040, 0xA121): ("Date", "DA"),
}

# Instance UIDs, used when the VR is not in the file. With explicit VR every UI element is checked.
UID_TAGS = {
    (0x0002, 0x0003): "MediaStorageSOPInstanceUID",
    (0x0004, 0x1511): "ReferencedSOPInstanceUIDInFile",
    (0x0008, 0x0014): "InstanceCreatorUID",
    (0x0008, 0x0018): "SOPInstanceUID",
    (0x0008, 0x1155): "ReferencedSOPInstanceUID",
    (0x0020, 0x000D): "StudyInstanceUID",
    (0x0020, 0x000E): "SeriesInstanceUID",
    (0x0020, 0x0052): "FrameOfReferenceUID",
    (0x0020, 0x0200): "SynchronizationFrameOfReferenceUID",
    (0x0020, 0x9161): "ConcatenationUID",
    (0x0040, 0xA124): "UID",
    (0x0040, 0xA171): "ObservationUID",
    (0x0062, 0x0021): "TrackingUID",
    (0x0064, 0x0003): "SourceFrameOfReferenceUID",
    (0x0088, 0x0140): "StorageMediaFileSetUID",
    (0x3006, 0x0024): "ReferencedFrameOfReferenceUID",
}

# Class, syntax and scheme UIDs: standard or implementation identifiers, never patient-related.
NON_INSTANCE_UID_TAGS = {
    (0x0002, 0x0002), (0x0002, 0x0010), (0x0002, 0x0012), (0x0004, 0x1510), (0x0004, 0x1512),
    (0x0008, 0x0016), (0x0008, 0x001A), (0x0008, 0x001B), (0x0008, 0x0062), (0x0008, 0x010C),
    (0x0008, 0x1150),
}

# Sequences, so implicit-VR files with defined-length sequences are walked and paths read well.
SQ_TAGS = {
    (0x0004, 0x1220): "DirectoryRecordSequence",
    (0x0008, 0x0082): "InstitutionCodeSequence",
    (0x0008, 0x0096): "ReferringPhysicianIdentificationSequence",
    (0x0008, 0x1032): "ProcedureCodeSequence",
    (0x0008, 0x1110): "ReferencedStudySequence",
    (0x0008, 0x1111): "ReferencedPerformedProcedureStepSequence",
    (0x0008, 0x1115): "ReferencedSeriesSequence",
    (0x0008, 0x1120): "ReferencedPatientSequence",
    (0x0008, 0x1140): "ReferencedImageSequence",
    (0x0008, 0x1199): "ReferencedSOPSequence",
    (0x0008, 0x1250): "RelatedSeriesSequence",
    (0x0008, 0x2112): "SourceImageSequence",
    (0x0008, 0x9215): "DerivationCodeSequence",
    (0x0010, 0x1002): "OtherPatientIDsSequence",
    (0x0012, 0x0064): "DeidentificationMethodCodeSequence",
    (0x0040, 0x0100): "ScheduledProcedureStepSequence",
    (0x0040, 0x0260): "PerformedProtocolCodeSequence",
    (0x0040, 0x0275): "RequestAttributesSequence",
    (0x0040, 0xA043): "ConceptNameCodeSequence",
    (0x0040, 0xA073): "VerifyingObserverSequence",
    (0x0040, 0xA730): "ContentSequence",
    (0x0054, 0x0016): "RadiopharmaceuticalInformationSequence",
    (0x5200, 0x9229): "SharedFunctionalGroupsSequence",
    (0x5200, 0x9230): "PerFrameFunctionalGroupsSequence",
}

STATUS_TAGS = {
    (0x0008, 0x0060): ("Modality", "CS"),
    (0x0012, 0x0062): ("PatientIdentityRemoved", "CS"),
    (0x0012, 0x0063): ("DeidentificationMethod", "LO"),
    (0x0018, 0x0015): ("BodyPartExamined", "CS"),
    (0x0010, 0x1010): ("PatientAge", "AS"),
    (0x0028, 0x0301): ("BurnedInAnnotation", "CS"),
    (0x0028, 0x0302): ("RecognizableVisualFeatures", "CS"),
    (0x0042, 0x0011): ("EncapsulatedDocument", "OB"),
}

# Modalities where text is often burned into the pixels (ultrasound, screen captures,
# angiography, fluoroscopy, endoscopy and photos, radiographs, slide label images).
BURNED_IN_RISK_MODALITIES = {"US", "SC", "OT", "XA", "RF", "ES", "XC", "GM", "CR", "DX", "MG", "IO", "PX", "SM", "DOC"}
VOLUME_MODALITIES = {"CT", "MR", "PT"}
HEAD_WORDS = ("HEAD", "BRAIN", "SKULL", "NECK", "FACE", "ORBIT", "SINUS")

CATEGORIES = ("identifier", "location", "staff", "site", "study-id", "free-text", "date", "age",
              "uid", "private", "pixel", "status")

MAX_VALUE_CAPTURE = 64 * 1024


class ParseError(Exception):
    pass


def keyword_for(tag):
    if tag in CHECKED:
        return CHECKED[tag][0]
    if tag in DATE_TAGS:
        return DATE_TAGS[tag][0]
    if tag in UID_TAGS:
        return UID_TAGS[tag]
    if tag in SQ_TAGS:
        return SQ_TAGS[tag]
    if tag in STATUS_TAGS:
        return STATUS_TAGS[tag][0]
    if 0x6000 <= tag[0] <= 0x601E and tag[0] % 2 == 0:
        if tag[1] == 0x3000:
            return "OverlayData"
        if tag[1] == 0x4000:
            return "OverlayComments"
    return None


def fmt_tag(tag):
    return "(%04X,%04X)" % tag


def is_private(group):
    return group % 2 == 1 and group not in ILLEGAL_PRIVATE_GROUPS


def wanted_value(tag, vr):
    if tag in CHECKED or tag in DATE_TAGS or tag in UID_TAGS or tag in STATUS_TAGS:
        return True
    if vr in ("DA", "DT", "UI"):
        return True
    if 0x6000 <= tag[0] <= 0x601E and tag[1] == 0x4000:
        return True
    return False


class Element(object):
    __slots__ = ("path", "tag", "vr", "value", "length", "items")

    def __init__(self, path, tag, vr, value, length, items=None):
        self.path = path
        self.tag = tag
        self.vr = vr
        self.value = value
        self.length = length
        self.items = items


class DicomWalker(object):
    """Walks a DICOM dataset held in a bytes-like buffer and records elements."""

    def __init__(self, buf, max_depth=32):
        self.buf = buf
        self.size = len(buf)
        self.max_depth = max_depth
        self.elements = []

    def _u16(self, pos, little):
        return struct.unpack_from("<H" if little else ">H", self.buf, pos)[0]

    def _u32(self, pos, little):
        return struct.unpack_from("<I" if little else ">I", self.buf, pos)[0]

    def _tag(self, pos, little):
        return (self._u16(pos, little), self._u16(pos + 2, little))

    def looks_explicit(self, pos):
        if pos + 6 > self.size:
            return False
        vr = bytes(self.buf[pos + 4:pos + 6])
        return len(vr) == 2 and 65 <= vr[0] <= 90 and 65 <= vr[1] <= 90

    def _starts_with_item(self, pos, end, little):
        return pos + 8 <= end and self._tag(pos, little) == ITEM

    def read_header(self, pos, end, little, explicit):
        if pos + 8 > end:
            raise ParseError("truncated element header at byte %d" % pos)
        tag = self._tag(pos, little)
        if tag[0] == 0xFFFE:
            return tag, None, self._u32(pos + 4, little), 8
        if explicit:
            raw = bytes(self.buf[pos + 4:pos + 6])
            if not (65 <= raw[0] <= 90 and 65 <= raw[1] <= 90):
                raise ParseError("invalid VR at byte %d for tag %s" % (pos + 4, fmt_tag(tag)))
            vr = raw.decode("ascii")
            if vr in LONG_VRS:
                if pos + 12 > end:
                    raise ParseError("truncated element header at byte %d" % pos)
                return tag, vr, self._u32(pos + 8, little), 12
            return tag, vr, self._u16(pos + 6, little), 8
        return tag, None, self._u32(pos + 4, little), 8

    def parse_dataset(self, pos, end, little, explicit, path, depth, until_item_delim=False):
        if depth > self.max_depth:
            raise ParseError("sequence nesting deeper than %d" % self.max_depth)
        while pos < end:
            tag, vr, length, hdr = self.read_header(pos, end, little, explicit)
            if tag == ITEM_DELIM:
                if until_item_delim:
                    return pos + 8
                raise ParseError("unexpected item delimiter at byte %d" % pos)
            if tag[0] == 0xFFFE:
                raise ParseError("unexpected item tag %s at byte %d" % (fmt_tag(tag), pos))
            vstart = pos + hdr
            name = keyword_for(tag) or fmt_tag(tag)
            if length == UNDEFINED:
                if vr == "SQ" or vr is None:
                    items, pos = self.parse_sequence(vstart, None, end, little, explicit, path + (name,), depth)
                    self.elements.append(Element(path, tag, "SQ" if vr else None, None, None, items))
                elif vr == "UN":
                    # PS3.5 6.2.2: UN with undefined length holds a sequence in implicit VR little endian
                    items, pos = self.parse_sequence(vstart, None, end, True, False, path + (name,), depth)
                    self.elements.append(Element(path, tag, "UN", None, None, items))
                else:
                    pos = self.skip_encapsulated(vstart, end, little)
                    self.elements.append(Element(path, tag, vr, None, None))
                continue
            vend = vstart + length
            if vend > end:
                raise ParseError("value of %s runs past the end of its container (truncated file?)" % fmt_tag(tag))
            if vr == "SQ":
                items, _ = self.parse_sequence(vstart, length, vend, little, explicit, path + (name,), depth)
                self.elements.append(Element(path, tag, vr, None, length, items))
            elif (vr is None or vr == "UN") and length >= 8 and (
                    (vr is None and tag in SQ_TAGS) or self._starts_with_item(vstart, vend, little if vr is None else True)):
                seq_little, seq_explicit = (little, explicit) if vr is None else (True, False)
                mark = len(self.elements)
                try:
                    items, _ = self.parse_sequence(vstart, length, vend, seq_little, seq_explicit, path + (name,), depth)
                    self.elements.append(Element(path, tag, vr, None, length, items))
                except ParseError:
                    if vr is None and tag in SQ_TAGS:
                        raise
                    del self.elements[mark:]
                    self._record_value(path, tag, vr, vstart, length)
            else:
                self._record_value(path, tag, vr, vstart, length)
            pos = vend
        if until_item_delim:
            raise ParseError("item without an item delimiter")
        return pos

    def _record_value(self, path, tag, vr, vstart, length):
        value = None
        if wanted_value(tag, vr) and length <= MAX_VALUE_CAPTURE:
            value = bytes(self.buf[vstart:vstart + length])
        self.elements.append(Element(path, tag, vr, value, length))

    def parse_sequence(self, pos, length, end, little, explicit, path, depth):
        seq_end = pos + length if length is not None else end
        items = 0
        while pos < seq_end:
            if pos + 8 > seq_end:
                raise ParseError("truncated sequence item header at byte %d" % pos)
            tag = self._tag(pos, little)
            ilen = self._u32(pos + 4, little)
            if tag == SEQ_DELIM:
                return items, pos + 8
            if tag != ITEM:
                raise ParseError("expected a sequence item at byte %d, found %s" % (pos, fmt_tag(tag)))
            istart = pos + 8
            item_path = path[:-1] + ("%s[%d]" % (path[-1], items),)
            if ilen == UNDEFINED:
                pos = self.parse_dataset(istart, seq_end, little, explicit, item_path, depth + 1, until_item_delim=True)
            else:
                if istart + ilen > seq_end:
                    raise ParseError("sequence item runs past the end of its sequence")
                self.parse_dataset(istart, istart + ilen, little, explicit, item_path, depth + 1)
                pos = istart + ilen
            items += 1
        if length is None:
            raise ParseError("sequence without a sequence delimiter")
        return items, seq_end

    def skip_encapsulated(self, pos, end, little):
        while pos + 8 <= end:
            tag = self._tag(pos, little)
            ilen = self._u32(pos + 4, little)
            if tag == SEQ_DELIM:
                return pos + 8
            if tag != ITEM or ilen == UNDEFINED:
                raise ParseError("malformed encapsulated pixel data at byte %d" % pos)
            pos += 8 + ilen
            if pos > end:
                raise ParseError("encapsulated fragment runs past the end of the file")
        raise ParseError("encapsulated pixel data without a sequence delimiter")


def decode_text(value):
    if value is None:
        return ""
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return value.decode("latin-1")


def is_empty(text, vr):
    junk = " \x00\\"
    if vr == "PN":
        junk += "^="
    return all(ch in junk for ch in text)


def read_file(path, force, max_inflate):
    """Return (elements, transfer_syntax) or raise ParseError; return None when not DICOM."""
    size = os.path.getsize(path)
    if size == 0:
        return None
    with open(path, "rb") as fh:
        try:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        except (ValueError, OSError):
            mm = fh.read()
        try:
            return walk_buffer(mm, force, max_inflate)
        finally:
            if isinstance(mm, mmap.mmap):
                mm.close()


def walk_buffer(buf, force, max_inflate):
    size = len(buf)
    walker = DicomWalker(buf)
    if size >= 132 and bytes(buf[128:132]) == b"DICM":
        pos = 132
    elif force:
        pos = 0
    else:
        return None
    ts = None
    # file meta group: always explicit VR little endian
    while pos + 8 <= size and struct.unpack_from("<H", buf, pos)[0] == 0x0002:
        tag, vr, length, hdr = walker.read_header(pos, size, True, True)
        if length == UNDEFINED or pos + hdr + length > size:
            raise ParseError("malformed file meta element %s" % fmt_tag(tag))
        value = bytes(buf[pos + hdr:pos + hdr + length])
        walker.elements.append(Element((), tag, vr, value if wanted_value(tag, vr) or tag == (2, 0x10) else None, length))
        if tag == (0x0002, 0x0010):
            ts = value.decode("ascii", "replace").strip("\x00 ")
        pos += hdr + length
    if ts is None:
        # no file meta or no TransferSyntaxUID: guess the VR encoding from the first element
        explicit = walker.looks_explicit(pos)
        walker.parse_dataset(pos, size, True, explicit, (), 0)
        return walker.elements, "(none: %s VR little endian assumed)" % ("explicit" if explicit else "implicit")
    if ts == TS_IMPLICIT_LE:
        walker.parse_dataset(pos, size, True, False, (), 0)
    elif ts == TS_EXPLICIT_BE:
        walker.parse_dataset(pos, size, False, True, (), 0)
    elif ts == TS_DEFLATED_LE:
        inflater = zlib.decompressobj(-15)
        try:
            data = inflater.decompress(bytes(buf[pos:]), max_inflate + 1)
        except zlib.error as exc:
            raise ParseError("deflated dataset could not be inflated: %s" % exc)
        if len(data) > max_inflate:
            raise ParseError("inflated dataset is larger than --max-inflate")
        inner = DicomWalker(data)
        inner.parse_dataset(0, len(data), True, True, (), 0)
        walker.elements.extend(inner.elements)
    else:
        # explicit VR little endian, also for every compressed transfer syntax
        walker.parse_dataset(pos, size, True, True, (), 0)
    return walker.elements, ts


class Finding(object):
    __slots__ = ("severity", "category", "tag", "keyword", "path", "message", "value", "allowed")

    def __init__(self, severity, category, tag, keyword, path, message, value=None):
        self.severity = severity
        self.category = category
        self.tag = tag
        self.keyword = keyword
        self.path = path
        self.message = message
        self.value = value
        self.allowed = False

    def as_dict(self, show_values):
        out = {
            "severity": self.severity,
            "category": self.category,
            "tag": self.tag,
            "keyword": self.keyword,
            "path": self.path,
            "message": self.message,
            "allowed": self.allowed,
        }
        if show_values and self.value is not None:
            out["value"] = self.value
        return out


def element_path(el, keyword):
    return ".".join(el.path + (keyword,))


def check_elements(elements, opts):
    findings = []
    top = {}
    private_groups = {}
    for el in elements:
        if not el.path:
            top[el.tag] = el
        group = el.tag[0]
        if is_private(group):
            if el.tag[1] != 0x0000:
                key = (re.sub(r"\[\d+\]", "[*]", ".".join(el.path)), group)
                private_groups[key] = private_groups.get(key, 0) + 1
            continue
        if el.tag[1] == 0x0000:
            continue  # group length
        kw = keyword_for(el.tag) or fmt_tag(el.tag)
        text = decode_text(el.value)
        vr = el.vr
        if el.tag in CHECKED:
            ckw, cvr, cat, sev = CHECKED[el.tag]
            vr = vr or cvr
            if cvr == "SQ" or vr == "SQ":
                present = bool(el.items)
            else:
                # a value too long to capture still counts as present
                present = bool(el.length) and (el.value is None or not is_empty(text, vr))
            if present:
                findings.append(Finding(sev, cat, fmt_tag(el.tag), ckw, element_path(el, ckw),
                                        "%s has a value" % ckw if cvr != "SQ" else "%s has items" % ckw,
                                        text if cvr != "SQ" else None))
            continue
        date_vr = vr if vr in ("DA", "DT") else (DATE_TAGS[el.tag][1] if vr is None and el.tag in DATE_TAGS else None)
        if date_vr and el.value is not None and not is_empty(text, date_vr):
            findings.append(Finding("WARN", "date", fmt_tag(el.tag), kw, element_path(el, kw),
                                    "date present; Safe Harbor removes all date parts except the year, "
                                    "a shifted date needs a documented method", text))
            continue
        is_uid = vr == "UI" or (vr is None and el.tag in UID_TAGS)
        if is_uid and opts.uid_root and el.tag not in NON_INSTANCE_UID_TAGS and el.value is not None:
            for uid in text.strip("\x00 ").split("\\"):
                uid = uid.strip("\x00 ")
                if not uid or uid.startswith(STANDARD_UID_PREFIX):
                    continue
                if uid != opts.uid_root and not uid.startswith(opts.uid_root + "."):
                    findings.append(Finding("WARN", "uid", fmt_tag(el.tag), kw, element_path(el, kw),
                                            "UID is not under --uid-root %s; original UIDs may survive" % opts.uid_root,
                                            uid))
                    break
            continue
        if el.tag == (0x0010, 0x1010) and el.value is not None:
            m = re.match(r"^\s*(\d{1,3})\s*([DWMY])\s*$", text.strip("\x00"))
            if m and m.group(2) == "Y" and int(m.group(1)) > 89:
                findings.append(Finding("HIGH", "age", fmt_tag(el.tag), "PatientAge", element_path(el, "PatientAge"),
                                        "age over 89; Safe Harbor requires ages 90 and over to be grouped as 90+",
                                        text))
            continue
        if el.tag == (0x0028, 0x0302) and text.strip("\x00 ").upper() == "YES":
            findings.append(Finding("HIGH", "pixel", fmt_tag(el.tag), "RecognizableVisualFeatures",
                                    element_path(el, "RecognizableVisualFeatures"),
                                    "header says the pixel data shows recognizable visual features (a face)", text))
            continue
        if el.tag == (0x0028, 0x0301) and el.path and text.strip("\x00 ").upper() == "YES":
            findings.append(Finding("HIGH", "pixel", fmt_tag(el.tag), "BurnedInAnnotation",
                                    element_path(el, "BurnedInAnnotation"),
                                    "header says identifying text is burned into the pixel data", text))
            continue
        if el.tag == (0x0042, 0x0011):
            findings.append(Finding("WARN", "pixel", fmt_tag(el.tag), "EncapsulatedDocument",
                                    element_path(el, "EncapsulatedDocument"),
                                    "embedded document (for example a PDF report) is not inspected by this check"))
            continue
        if 0x6000 <= group <= 0x601E and group % 2 == 0:
            if el.tag[1] == 0x3000:
                findings.append(Finding("WARN", "pixel", fmt_tag(el.tag), "OverlayData", element_path(el, "OverlayData"),
                                        "overlay plane present; overlays can carry burned-in text or marks"))
            elif el.tag[1] == 0x4000 and el.value is not None and not is_empty(text, "LT"):
                findings.append(Finding("WARN", "free-text", fmt_tag(el.tag), "OverlayComments",
                                        element_path(el, "OverlayComments"), "overlay comments have a value", text))
    for (prefix, group), count in sorted(private_groups.items()):
        path = (prefix + "." if prefix else "") + "(%04X,xxxx)" % group
        findings.append(Finding("WARN", "private", "(%04X,xxxx)" % group, "(private)", path,
                                "%d private element(s) in group %04X; remove them or keep only attributes "
                                "known to be safe" % (count, group)))
    findings.extend(check_dataset(top))
    return findings


def top_text(top, tag):
    el = top.get(tag)
    return decode_text(el.value).strip("\x00 ").upper() if el is not None and el.value is not None else ""


def check_dataset(top):
    findings = []
    modality = top_text(top, (0x0008, 0x0060))
    burned = top_text(top, (0x0028, 0x0301))
    if burned == "YES":
        findings.append(Finding("HIGH", "pixel", "(0028,0301)", "BurnedInAnnotation", "BurnedInAnnotation",
                                "header says identifying text is burned into the pixel data", burned))
    elif burned != "NO" and modality in BURNED_IN_RISK_MODALITIES:
        findings.append(Finding("WARN", "pixel", "(0028,0301)", "BurnedInAnnotation", "BurnedInAnnotation",
                                "BurnedInAnnotation is not NO for modality %s; inspect the pixels for text" % modality))
    body = top_text(top, (0x0018, 0x0015))
    if modality in VOLUME_MODALITIES and any(word in body for word in HEAD_WORDS):
        findings.append(Finding("WARN", "pixel", "(0018,0015)", "BodyPartExamined", "BodyPartExamined",
                                "%s of the head or neck: a 3D rendering can show the face; deface volumes "
                                "before sharing" % modality, body))
    removed = top_text(top, (0x0012, 0x0062))
    if removed != "YES":
        findings.append(Finding("WARN", "status", "(0012,0062)", "PatientIdentityRemoved", "PatientIdentityRemoved",
                                "PatientIdentityRemoved is not YES" if removed else "PatientIdentityRemoved is absent",
                                removed or None))
    if (0x0012, 0x0063) not in top and (0x0012, 0x0064) not in top:
        findings.append(Finding("INFO", "status", "(0012,0063)", "DeidentificationMethod", "DeidentificationMethod",
                                "no DeidentificationMethod or DeidentificationMethodCodeSequence recorded"))
    return findings


def apply_allowances(findings, opts):
    for f in findings:
        if f.severity == "INFO":
            continue
        if f.category in opts.allow_category or f.keyword in opts.allow:
            f.allowed = True
        elif f.keyword in opts.allow_pattern and f.value is not None:
            if opts.allow_pattern[f.keyword].fullmatch(f.value.strip("\x00 ")):
                f.allowed = True
                f.message += " (matches the allowed pattern)"
            else:
                f.message += " (does not match the allowed pattern)"
        if f.allowed:
            f.severity = "INFO"
    return findings


def iter_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs.sort()
                for name in sorted(files):
                    yield os.path.join(root, name)
        else:
            yield p


def summarize(per_file):
    agg = {}
    for path, findings in per_file:
        seen = set()
        for f in findings:
            norm = re.sub(r"\[\d+\]", "[*]", f.path)
            key = (SEVERITIES.index(f.severity), f.category, f.tag, f.keyword, norm, f.allowed)
            entry = agg.setdefault(key, {"severity": f.severity, "category": f.category, "tag": f.tag,
                                         "keyword": f.keyword, "path": norm, "allowed": f.allowed,
                                         "files": 0, "occurrences": 0, "message": f.message})
            entry["occurrences"] += 1
            if key not in seen:
                entry["files"] += 1
                seen.add(key)
    return [agg[k] for k in sorted(agg)]


def build_parser():
    p = argparse.ArgumentParser(
        prog="dicom_phi_check.py",
        description="Read-only check of DICOM headers for identifying data that survived de-identification. "
                    "Header only: pixel data, burned-in text, faces and embedded documents are not inspected.",
        epilog="Exit codes: 0 no HIGH findings (no WARN either with --strict); 1 findings; "
               "2 usage error, unparseable file or no DICOM files. Values are hidden unless --show-values.")
    p.add_argument("paths", nargs="*", help="DICOM files or directories (searched recursively)")
    p.add_argument("--format", choices=("text", "json"), default="text", help="output format (default: text)")
    p.add_argument("--json", action="store_true", help="same as --format json")
    p.add_argument("--per-file", action="store_true", help="list findings per file instead of a summary")
    p.add_argument("--strict", action="store_true", help="exit 1 on WARN findings too")
    p.add_argument("--force", action="store_true",
                   help="also read files without the DICM preamble (raw datasets); may misread other files")
    p.add_argument("--uid-root", metavar="ROOT",
                   help="expected root of replaced instance UIDs, for example 2.25; flags UIDs outside it")
    p.add_argument("--allow", action="append", default=[], metavar="KEYWORD",
                   help="accept this attribute (for example a pseudonymous PatientID); repeatable")
    p.add_argument("--allow-category", action="append", default=[], metavar="CATEGORY", choices=CATEGORIES,
                   help="accept a whole category, for example date when dates were shifted under a "
                        "documented method; repeatable; one of: %s" % ", ".join(CATEGORIES))
    p.add_argument("--allow-pattern", action="append", default=[], metavar="KEYWORD=REGEX",
                   help="accept an attribute only when its whole value matches REGEX, "
                        "for example PatientID=SUBJ-[0-9]{4}; repeatable")
    p.add_argument("--show-values", action="store_true",
                   help="print the offending values (they may be identifiers; keep them out of shared logs)")
    p.add_argument("--max-inflate", type=int, default=1024, metavar="MB",
                   help="largest inflated size for deflated datasets, in MB (default: 1024)")
    p.add_argument("--list-checks", action="store_true", help="print the checked attributes and exit")
    return p


def list_checks(out):
    out.write("Checked attributes (severity, category, tag, keyword):\n")
    for tag in sorted(CHECKED):
        kw, vr, cat, sev = CHECKED[tag]
        out.write("  %-4s  %-10s  %s  %s\n" % (sev, cat, fmt_tag(tag), kw))
    out.write("Also: every DA and DT value (date), PatientAge over 89Y (age), private groups (private),\n"
              "UIDs outside --uid-root (uid), BurnedInAnnotation, RecognizableVisualFeatures, overlays,\n"
              "encapsulated documents and head volumes (pixel), PatientIdentityRemoved and\n"
              "DeidentificationMethod (status).\n")


def main(argv=None):
    parser = build_parser()
    opts = parser.parse_args(argv)
    if opts.list_checks:
        list_checks(sys.stdout)
        return 0
    if not opts.paths:
        parser.print_usage(sys.stderr)
        sys.stderr.write("dicom_phi_check.py: error: give at least one file or directory\n")
        return 2
    if opts.json:
        opts.format = "json"
    patterns = {}
    for item in opts.allow_pattern:
        if "=" not in item:
            sys.stderr.write("dicom_phi_check.py: error: --allow-pattern needs KEYWORD=REGEX\n")
            return 2
        key, rx = item.split("=", 1)
        try:
            patterns[key.strip()] = re.compile(rx)
        except re.error as exc:
            sys.stderr.write("dicom_phi_check.py: error: bad regex for %s: %s\n" % (key, exc))
            return 2
    opts.allow_pattern = patterns
    opts.allow = set(opts.allow)
    opts.allow_category = set(opts.allow_category)
    if opts.uid_root:
        opts.uid_root = opts.uid_root.strip().rstrip(".")
        if not re.fullmatch(r"[0-9]+(\.[0-9]+)*", opts.uid_root):
            sys.stderr.write("dicom_phi_check.py: error: --uid-root must be dotted digits, for example 2.25\n")
            return 2
    max_inflate = max(1, opts.max_inflate) * 1024 * 1024

    per_file, skipped, errors = [], [], []
    for path in iter_files(opts.paths):
        if not os.path.isfile(path):
            errors.append({"file": path, "error": "not a file or not found"})
            continue
        try:
            result = read_file(path, opts.force, max_inflate)
        except ParseError as exc:
            errors.append({"file": path, "error": str(exc)})
            continue
        except (OSError, struct.error) as exc:
            errors.append({"file": path, "error": "read error: %s" % exc})
            continue
        if result is None:
            skipped.append(path)
            continue
        elements, _ts = result
        findings = apply_allowances(check_elements(elements, opts), opts)
        per_file.append((path, findings))

    summary = summarize(per_file)
    counts = {s: 0 for s in SEVERITIES}
    for _, findings in per_file:
        for f in findings:
            counts[f.severity] += 1
    if errors or not per_file:
        code = 2
    elif counts["HIGH"] or (opts.strict and counts["WARN"]):
        code = 1
    else:
        code = 0
    status = {0: "PASS", 1: "FAIL", 2: "ERROR"}[code]
    note = ("Header check only: pixel data, burned-in text, faces in volumes, slide label images and "
            "embedded documents were not inspected.")

    if opts.format == "json":
        doc = {
            "tool": "dicom_phi_check", "version": VERSION, "result": status,
            "files_scanned": len(per_file), "files_skipped": skipped, "errors": errors,
            "counts": counts, "note": note, "summary": summary,
            "files": [{"file": path, "findings": [f.as_dict(opts.show_values) for f in findings]}
                      for path, findings in per_file],
        }
        sys.stdout.write(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        return code

    out = sys.stdout
    out.write("dicom_phi_check %s: %d file(s) scanned, %d skipped (not DICOM Part 10), %d error(s)\n"
              % (VERSION, len(per_file), len(skipped), len(errors)))
    out.write("NOTE: %s\n" % note)
    for err in errors:
        out.write("ERROR  %s: %s\n" % (err["file"], err["error"]))
    if not per_file and not errors:
        out.write("ERROR  no DICOM Part 10 files found (use --force for raw datasets)\n")
    if opts.per_file:
        for path, findings in per_file:
            out.write("\n%s\n" % path)
            if not findings:
                out.write("  (no findings)\n")
            for f in sorted(findings, key=lambda x: (SEVERITIES.index(x.severity), x.tag, x.path)):
                line = "  %-4s  %-10s %-12s %-40s %s" % (f.severity, f.category, f.tag, f.path, f.message)
                if opts.show_values and f.value is not None:
                    line += "  value=%r" % f.value[:64]
                out.write(line.rstrip() + "\n")
    else:
        if summary:
            out.write("\n%-4s  %-10s %-12s %-48s %6s  %s\n" % ("SEV", "CATEGORY", "TAG", "PATH", "FILES", "WHAT"))
        for row in summary:
            what = row["message"] + (" [allowed]" if row["allowed"] else "")
            out.write(("%-4s  %-10s %-12s %-48s %6d  %s" % (row["severity"], row["category"], row["tag"],
                                                             row["path"], row["files"], what)).rstrip() + "\n")
    out.write("\nResult: %s (%d HIGH, %d WARN, %d INFO)\n" % (status, counts["HIGH"], counts["WARN"], counts["INFO"]))
    return code


if __name__ == "__main__":
    sys.exit(main())
