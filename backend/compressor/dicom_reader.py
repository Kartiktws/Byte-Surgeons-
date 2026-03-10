"""
DICOM Reader - Read and split 2D or multi-frame DICOM files.
Handles metadata extraction and DICOM reconstruction.
"""

import ast
import pydicom
from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement
from pydicom.datadict import dictionary_VR
from pydicom.sequence import Sequence as PydicomSequence
import numpy as np
from pathlib import Path


class DicomReader:
    """Read 2D or multi-frame DICOM files and reconstruct from metadata + pixels."""

    #  Pixel Data tag (7FE0,0010) contains the raw image bytes
    PIXEL_DATA_TAG = (0x7FE0, 0x0010)

    @staticmethod
    def tag_to_key(tag: tuple) -> str:
        """Convert (group, element) to 'GGGG,EEEE' string.
        This function converts a Python DICOM tag
        tuple (group, element) into the standard hex string "GGGG,EEEE" so it can be safely stored 
        in metadata dictionaries or JSON."""
        return f"{tag[0]:04X},{tag[1]:04X}"

    @staticmethod
    def key_to_tag(key: str) -> tuple:
        """Convert 'GGGG,EEEE' string to (group, element)."""
        parts = key.split(",")
        return (int(parts[0], 16), int(parts[1], 16))

    @staticmethod
    def elem_value_to_str(elem) -> str:
        """
        This function converts any DICOM element value into a safe string format 
        (using backslash for multi-values) so metadata can be stored in JSON and later reconstructed correctly.
        """
        """
        Serialize a DICOM element value to a string for JSON storage.
        Multi-value (list/tuple) elements are stored as backslash-separated
        so they round-trip correctly for VR CS and other multi-value string types.
        """
        val = elem.value
        if isinstance(val, (list, tuple)):
            return "\\".join(str(x) for x in val)
        try:
            return str(val)
        except Exception:
            return str(repr(val))

    def read(self, filepath: str) -> dict:
        """

        Open DICOM file and extract metadata + pixel array.
        Supports both single-frame (2D) and multi-frame (3D) images.

        The read() function loads a DICOM file and separates its metadata and pixel 
        data into a normalized Python structure, making the metadata JSON-serializable and the 
        pixel data available as a NumPy array for further processing or reconstruction.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"DICOM file not found: {filepath}")

        # Load the DICOM dataset 
        dataset = pydicom.dcmread(str(path))

        # Number of frames: from tag (0028,0008) or default 1
        num_frames = 1
        if (0x0028, 0x0008) in dataset:
            try:
                num_frames = int(dataset[0x0028, 0x0008].value)
            except (TypeError, ValueError, AttributeError):
                pass
        if num_frames == 1:
            nf_attr = getattr(dataset, "NumberOfFrames", None)
            if nf_attr is not None:
                try:
                    num_frames = int(nf_attr)
                except (TypeError, ValueError):
                    pass

        metadata_tags = {}
        for elem in dataset:
            tag = (elem.tag.group, elem.tag.element)
            if tag == self.PIXEL_DATA_TAG:
                continue
            vr = getattr(elem, "VR", None) or "UN"
            # Skip Sequence (SQ): value is list of Dataset instances, not serializable to JSON
            if vr == "SQ" or isinstance(getattr(elem, "value", None), PydicomSequence):
                continue
            key = self.tag_to_key(tag)
            # Store as {"v": value, "vr": vr} so reconstruct can skip by VR and handle multi-value
            metadata_tags[key] = {"v": self.elem_value_to_str(elem), "vr": vr}

        pixel_array = np.array(dataset.pixel_array, copy=True)
        # Ensure 3D for multi-frame: (num_frames, rows, cols)
        if pixel_array.ndim == 2:
            pixel_array = pixel_array[np.newaxis, ...]
        rows = int(dataset.Rows)
        cols = int(dataset.Columns)
        bits = int(dataset.BitsAllocated)
        bits_stored = int(getattr(dataset, "BitsStored", bits))
        modality = str(getattr(dataset, "Modality", "") or "").strip().upper()
        photometric = str(getattr(dataset, "PhotometricInterpretation", ""))

        pixel_spacing = None
        if hasattr(dataset, "PixelSpacing") and dataset.PixelSpacing is not None:
            try:
                pixel_spacing = [float(x) for x in dataset.PixelSpacing]
            except (TypeError, ValueError):
                pixel_spacing = list(dataset.PixelSpacing)

        return {
            "metadata_tags": metadata_tags,
            "pixel_array": pixel_array,
            "num_frames": num_frames,
            "rows": rows,
            "cols": cols,
            "bits": bits,
            "bits_stored": bits_stored,
            "modality": modality or "OT",
            "photometric": photometric,
            "pixel_spacing": pixel_spacing,
        }

    # VRs that support multi-value and are stored as backslash-separated in metadata
    MULTIVALUE_STRING_VR = ("CS", "SH", "LO", "AE", "UI")

    def value_for_vr(self, value_str: str, vr: str):
        """Convert string value to the type expected by DICOM VR."""
        """
        This function restores metadata values from stored string form back into the correct Python data type based on the DICOM Value 
        Representation (VR), ensuring that reconstructed DICOM elements have valid data types.
        """
        # Multi-value string VRs: restore list from backslash-separated form (CS max 16 chars per value)
        if vr in self.MULTIVALUE_STRING_VR:
            if "\\" in value_str:
                return [part.strip() for part in value_str.split("\\") if part.strip()]
            # Backward compatibility: legacy .dcmz may have Python list repr e.g. "['ORIGINAL', 'PRIMARY', 'M', 'NONE']"
            s = value_str.strip()
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = ast.literal_eval(value_str)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed]
                except (ValueError, SyntaxError):
                    pass
        try:
            if vr in ("US", "SS", "UL", "SL", "IS", "OL", "OV"):
                return int(value_str)
            if vr in ("FL", "FD", "DS"):
                return float(value_str)
            if vr in ("OB", "OD", "OF", "OL", "OV", "OW", "UN"):
                return value_str  # bytes or keep as-is
        except (TypeError, ValueError):
            pass
        return value_str

    def reconstruct(
        self,
        metadata_tags: dict,
        pixel_array: np.ndarray,
        output_filepath: str,
    ) -> str:
        """
        Create a new DICOM file from metadata and pixel array.
        Returns the saved filepath.
        """
        """
        The reconstruct() function rebuilds a valid DICOM file by converting stored metadata back into DICOM elements, 
        attaching pixel data, ensuring required image tags exist, and saving the result as a new DICOM dataset.
        """
        dataset = Dataset()
        pixel_data_tag = self.PIXEL_DATA_TAG

        for key, payload in metadata_tags.items():
            tag = self.key_to_tag(key)
            if tag == pixel_data_tag:
                continue
            # Support both formats: legacy key -> str, or key -> {"v": str, "vr": str}
            if isinstance(payload, dict):
                value_str = payload.get("v", "")
                try:
                    vr = payload.get("vr") or dictionary_VR(tag) or "UN"
                except Exception:
                    vr = payload.get("vr") or "UN"
            else:
                value_str = payload
                try:
                    vr = dictionary_VR(tag) or "UN"
                except Exception:
                    vr = "UN"
            # Skip Sequence (SQ): we only have a string, pydicom needs list of Dataset instances
            if vr == "SQ":
                continue
            try:
                converted = self.value_for_vr(value_str, vr)
            except Exception:
                converted = value_str
            elem = DataElement(tag, vr, converted)
            dataset.add(elem)

        # Ensure critical pixel-related tags exist (2D: rows/cols; 3D: num_frames, rows, cols)
        if pixel_array.ndim == 3:
            num_frames, rows, cols = pixel_array.shape
            if (0x0028, 0x0008) not in dataset:
                dataset.add(DataElement((0x0028, 0x0008), "IS", str(num_frames)))
            if (0x0028, 0x0010) not in dataset:
                dataset.add(DataElement((0x0028, 0x0010), "US", rows))
            if (0x0028, 0x0011) not in dataset:
                dataset.add(DataElement((0x0028, 0x0011), "US", cols))
        else:
            rows, cols = pixel_array.shape[0], pixel_array.shape[1]
            if (0x0028, 0x0010) not in dataset:
                dataset.add(DataElement((0x0028, 0x0010), "US", rows))
            if (0x0028, 0x0011) not in dataset:
                dataset.add(DataElement((0x0028, 0x0011), "US", cols))
        if (0x0028, 0x0100) not in dataset:
            bits = 16 if pixel_array.dtype == np.uint16 else 8
            dataset.add(DataElement((0x0028, 0x0100), "US", bits))
        if (0x0028, 0x0101) not in dataset:
            dataset.add(DataElement((0x0028, 0x0101), "US", dataset.BitsAllocated))
        if (0x0028, 0x0102) not in dataset:
            dataset.add(DataElement((0x0028, 0x0102), "US", dataset.BitsStored - 1))
        if (0x0028, 0x0103) not in dataset:
            dataset.add(DataElement((0x0028, 0x0103), "SS", 0))
        if (0x0028, 0x0002) not in dataset:
            dataset.add(DataElement((0x0028, 0x0002), "US", 1))
        if (0x0028, 0x0004) not in dataset:
            dataset.add(DataElement((0x0028, 0x0004), "CS", "MONOCHROME2"))

        dataset.PixelData = pixel_array.tobytes()

        # Required for save_as(write_like_original=False): file_meta and encoding
        dataset.file_meta = Dataset()
        dataset.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
        dataset.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
        dataset.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5.6.7.8.9.10"
        dataset.is_little_endian = True
        dataset.is_implicit_VR = False

        out_path = Path(output_filepath)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        dataset.save_as(str(out_path), write_like_original=False)
        return str(out_path)
