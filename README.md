# DICOM Lossless Compression Engine

## What it does

Lossless compression for 2D DICOM medical images (single-frame or multi-frame).  
Pipeline: **Wavelet Transform → Huffman Encoding → DEFLATE** on metadata.

## Algorithm Summary

1. **Read DICOM** → split metadata and pixel data  
2. **Metadata** → JSON → DEFLATE compress  
3. **Pixel data** → Haar Wavelet Transform (3 levels) → Huffman encode  
4. **Pack** everything into `.dcmz` binary format  
5. **Decompress**: exact reverse of all steps above  
6. **Verify**: `numpy.array_equal()` confirms bit-perfect recovery  

## Installation

```bash
pip install -r requirements.txt
```

## Run Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

Run from the project root (`dicom_compressor/`).

## API Endpoints

| Method | Endpoint        | Description                                      |
|--------|-----------------|--------------------------------------------------|
| POST   | `/compress`     | Upload `.dcm` → returns compression stats       |
| POST   | `/decompress`   | Upload `.dcmz` → returns recovered `.dcm` file  |
| GET    | `/health`       | Health check                                     |

## Run Tests

```bash
pytest tests/ -v
```

Run from the project root (`dicom_compressor/`).

## Limitations

- **2D images only** (single-frame or multi-frame stacks; no 3D volumes)  
- **Lossless mode only** in this version  
- New `.dcmz` files use format `DCMZ_V2` (multi-frame); legacy `DCMZ_V1` files (single-frame only) can still be decompressed  
