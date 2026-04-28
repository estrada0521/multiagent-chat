from __future__ import annotations

import ctypes
import ctypes.util
from ctypes import CFUNCTYPE, POINTER, c_char_p, c_double, c_int32, c_uint32, c_uint64, c_void_p

FSEVENT_CREATE_FLAGS = 0x00000001 | 0x00000002 | 0x00000010
KFSEVENTSTREAM_EVENT_ID_SINCE_NOW = 0xFFFFFFFFFFFFFFFF


def load_cf_cs():
    core_foundation = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
    core_services = ctypes.CDLL(ctypes.util.find_library("CoreServices"))
    return core_foundation, core_services


def cf_path_array(cf, paths: list[str]) -> c_void_p:
    CFStringCreateWithCString = cf.CFStringCreateWithCString
    CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint32]
    CFStringCreateWithCString.restype = c_void_p

    CFArrayCreateMutable = cf.CFArrayCreateMutable
    CFArrayCreateMutable.argtypes = [c_void_p, c_int32, c_void_p]
    CFArrayCreateMutable.restype = c_void_p

    CFArrayAppendValue = cf.CFArrayAppendValue
    CFArrayAppendValue.argtypes = [c_void_p, c_void_p]
    CFArrayAppendValue.restype = None

    CFRelease = cf.CFRelease
    CFRelease.argtypes = [c_void_p]
    CFRelease.restype = None

    cf_array = CFArrayCreateMutable(None, 0, None)
    if not cf_array:
        return c_void_p()
    created: list[c_void_p] = []
    try:
        for path in paths:
            cf_string = CFStringCreateWithCString(None, path.encode("utf-8"), 0x08000100)
            if not cf_string:
                continue
            created.append(cf_string)
            CFArrayAppendValue(cf_array, cf_string)
    finally:
        for item in created:
            CFRelease(item)
    return cf_array


FSEventCallback = CFUNCTYPE(
    None,
    c_void_p,
    c_void_p,
    c_uint64,
    POINTER(c_char_p),
    POINTER(c_uint32),
    POINTER(c_uint64),
)
