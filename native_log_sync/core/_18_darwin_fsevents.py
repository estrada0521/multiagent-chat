"""Shared macOS FSEvents / CoreFoundation helpers for native log watchers."""

from __future__ import annotations

import ctypes
from ctypes import CFUNCTYPE, POINTER, byref, c_char_p, c_long, c_size_t, c_uint32, c_uint64, c_void_p

FSEVENTSTREAM_FILE_EVENTS = 0x00000010
FSEVENTSTREAM_WATCH_ROOT = 0x00000004
FSEVENT_CREATE_FLAGS = FSEVENTSTREAM_FILE_EVENTS | FSEVENTSTREAM_WATCH_ROOT
KFSEVENTSTREAM_EVENT_ID_SINCE_NOW = 0xFFFFFFFFFFFFFFFF
KCF_STRING_ENCODING_UTF8 = 0x08000100


class CFArrayCallbacks(ctypes.Structure):
    _fields_ = [
        ("version", c_long),
        ("retain", c_void_p),
        ("release", c_void_p),
        ("copyDescription", c_void_p),
        ("equal", c_void_p),
    ]


def load_cf_cs() -> tuple[ctypes.CDLL, ctypes.CDLL]:
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    cs = ctypes.CDLL("/System/Library/Frameworks/CoreServices.framework/CoreServices")
    return cf, cs


def cf_string(cf: ctypes.CDLL, value: bytes) -> c_void_p:
    fn = cf.CFStringCreateWithCString
    fn.argtypes = [c_void_p, c_char_p, c_uint32]
    fn.restype = c_void_p
    return fn(None, value, KCF_STRING_ENCODING_UTF8)


def cf_path_array(cf: ctypes.CDLL, paths: list[str]) -> c_void_p:
    k_cf_type_array_callbacks = CFArrayCallbacks.in_dll(cf, "kCFTypeArrayCallBacks")
    fn = cf.CFArrayCreate
    fn.argtypes = [c_void_p, POINTER(c_void_p), c_long, POINTER(CFArrayCallbacks)]
    fn.restype = c_void_p
    cf_strings = [cf_string(cf, p.encode("utf-8")) for p in paths]
    n = len(cf_strings)
    holder = (c_void_p * n)(*cf_strings)
    return fn(None, holder, n, byref(k_cf_type_array_callbacks))


FSEventCallback = CFUNCTYPE(
    None, c_void_p, c_void_p, c_size_t, POINTER(c_char_p), POINTER(c_uint32), POINTER(c_uint64)
)
