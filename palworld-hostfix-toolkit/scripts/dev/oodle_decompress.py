import ctypes
import os

DLL_PATH = os.path.join(os.path.dirname(__file__), "extracted", "libooz.dll")
SAFE_SPACE = 64

_lib = ctypes.CDLL(DLL_PATH)
_lib.Ooz_Decompress.argtypes = [
    ctypes.c_char_p,   # src_buf
    ctypes.c_int,      # src_len
    ctypes.c_char_p,   # dst
    ctypes.c_size_t,   # dst_size
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_int,
]
_lib.Ooz_Decompress.restype = ctypes.c_int


def ooz_decompress(compressed: bytes, uncompressed_len: int) -> bytes:
    out_buf = ctypes.create_string_buffer(uncompressed_len + SAFE_SPACE)
    result = _lib.Ooz_Decompress(
        compressed, len(compressed),
        out_buf, uncompressed_len,
        0, 0, 0, None, 0, None, None, None, 0, 0,
    )
    if result != uncompressed_len:
        raise Exception(f"Ooz_Decompress returned {result}, expected {uncompressed_len}")
    return out_buf.raw[:uncompressed_len]


if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    with open(path, "rb") as f:
        data = f.read()

    uncompressed_len = int.from_bytes(data[0:4], "little")
    compressed_len = int.from_bytes(data[4:8], "little")
    magic = data[8:11]
    save_type = data[11]
    offset = 12
    if magic == b"CNK":
        uncompressed_len = int.from_bytes(data[12:16], "little")
        compressed_len = int.from_bytes(data[16:20], "little")
        magic = data[20:23]
        save_type = data[23]
        offset = 24

    print(f"magic={magic!r} save_type={hex(save_type)} uncompressed_len={uncompressed_len} compressed_len={compressed_len} file_size={len(data)}")

    compressed_data = data[offset:]
    gvas = ooz_decompress(compressed_data, uncompressed_len)
    print(f"decompressed {len(gvas)} bytes, header: {gvas[:4]!r}")
    assert gvas[:4] == b"GVAS", "does not start with GVAS magic!"
    print("SUCCESS: valid GVAS header found")
