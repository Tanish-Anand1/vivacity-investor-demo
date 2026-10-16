"""Bounded capture metadata and geometry evidence; no inferred physical constants."""
import struct
from pathlib import PurePosixPath
import numpy as np

MAX_CAPTURE = 16 * 1024 * 1024


def capture_metadata(filename, data):
    if not data or len(data) > MAX_CAPTURE or not isinstance(filename, str) or not 1 <= len(filename) <= 64:
        raise ValueError('capture must be 1..16 MiB and have a basename of at most 64 characters')
    if '/' in filename or '\\' in filename or any(ord(c) < 32 for c in filename):
        raise ValueError('capture filename must be a safe basename')
    extension = PurePosixPath(filename).suffix.lower().lstrip('.')
    width = height = None
    if extension == 'png' and data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) >= 33 and data[12:16] == b'IHDR':
        width, height = struct.unpack('>II', data[16:24])
    elif extension in ('jpg', 'jpeg') and data.startswith(b'\xff\xd8'):
        offset = 2
        while offset + 4 <= len(data):
            if data[offset] != 255: break
            marker = data[offset+1]; offset += 2
            if marker == 255: offset -= 1; continue
            if marker in (0xd8, 0xd9): continue
            length = int.from_bytes(data[offset:offset+2], 'big')
            if length < 2 or offset + length > len(data): break
            if marker in (0xc0, 0xc1, 0xc2) and length >= 8:
                height, width = struct.unpack('>HH', data[offset+3:offset+7]); break
            offset += length
    elif extension == 'webp' and len(data) >= 30 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        if data[12:16] == b'VP8X':
            width = 1 + int.from_bytes(data[24:27], 'little'); height = 1 + int.from_bytes(data[27:30], 'little')
        elif data[12:16] == b'VP8L' and data[20] == 0x2f:
            bits = int.from_bytes(data[21:25], 'little'); width = 1 + (bits & 0x3fff); height = 1 + ((bits >> 14) & 0x3fff)
        elif data[12:16] == b'VP8 ' and data[23:26] == b'\x9d\x01\x2a':
            width, height = struct.unpack('<HH', data[26:30]); width &= 0x3fff; height &= 0x3fff
    elif extension in ('mp4', 'mov') and len(data) >= 16 and data[4:8] == b'ftyp' and 16 <= int.from_bytes(data[:4], 'big') <= len(data):
        return {'kind':'video','extension':extension,'dimensions_px':None,'validation':'container signature only; duration/codec and decoding are validated by the provider'}
    elif extension == 'mkv' and data.startswith(b'\x1a\x45\xdf\xa3') and len(data) >= 16:
        return {'kind':'video','extension':extension,'dimensions_px':None,'validation':'EBML signature only; duration/codec and decoding are validated by the provider'}
    if width is None or not 1 <= width <= 16384 or not 1 <= height <= 16384 or width * height > 40_000_000:
        raise ValueError('unsupported capture or invalid image header; use PNG/JPEG/WebP or MP4/MOV/MKV')
    return {'kind':'image','extension':extension,'dimensions_px':[width,height],
            'validation':'bounded image dimensions and signature; full decoding is validated by the provider'}


def geometry_evidence(preview, *, sampled=False):
    """Exact edge topology of the bounded preview, not a proof about subsampled source."""
    points = np.asarray(preview['positions'], dtype=float)
    faces = np.asarray(preview['indices'], dtype=np.int64).reshape(-1,3)
    if not len(points) or not len(faces) or not np.isfinite(points).all() or faces.min()<0 or faces.max()>=len(points):
        raise ValueError('invalid finite indexed triangle geometry')
    _, remap = np.unique(points, axis=0, return_inverse=True)
    welded = remap[faces]
    edges = np.concatenate([welded[:,[0,1]],welded[:,[1,2]],welded[:,[2,0]]])
    canonical = np.sort(edges,axis=1)
    _, inverse, counts = np.unique(canonical,axis=0,return_inverse=True,return_counts=True)
    signs = np.where(edges[:,0]<edges[:,1],1,-1)
    balance = np.bincount(inverse,weights=signs,minlength=len(counts))
    area2 = np.linalg.norm(np.cross(points[faces[:,1]]-points[faces[:,0]],points[faces[:,2]]-points[faces[:,0]]),axis=1)
    degenerates = int(np.count_nonzero(area2 <= 1e-12))
    boundary = int(np.count_nonzero(counts==1)); nonmanifold = int(np.count_nonzero(counts>2))
    inconsistent = int(np.count_nonzero((counts==2)&(balance!=0)))
    return {'schema_version':'vivacity.geometry-evidence/1.0','scope':'deterministically subsampled preview' if sampled else 'decoded static triangles',
            'source_mesh_fully_checked':not sampled,'vertices':len(points),'triangles':len(faces),
            'bounds_source_coordinates':[points.min(axis=0).tolist(),points.max(axis=0).tolist()],
            'coordinate_system':preview.get('coordinate_system'),'finite_vertices':True,'valid_indices':True,
            'degenerate_triangles':degenerates,'boundary_edges':boundary,'nonmanifold_edges':nonmanifold,
            'inconsistent_winding_edges':inconsistent,'watertight_preview':not (boundary or nonmanifold or degenerates),
            'normals':'computed finite face normals; imported normal attributes are not validated',
            'self_intersections':'not checked','object_separation':'not inferred; connected surfaces are not semantic objects',
            'metric_scale':'user supplied or provider reported; not independently measured',
            'physical_properties':{'mass':'unknown','friction':'unknown','restitution':'unknown'},
            'physics_readiness':'requires explicit collision mapping and independent validation'}
