# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Native binding of the frozen, independently proved pair-normalization map."""
from common import *
import importlib.util

PATH=NARROW/'research/quantized_producer/pair_normalization.py'
SHA='6af7fc14bc3c904efe480e2e23aee2fcbd97ad23f0a7ba324d8c05e1c8ec17fe'
assert hashlib.sha256(PATH.read_bytes()).hexdigest()==SHA
spec=importlib.util.spec_from_file_location('native_pair_normalization_source',PATH)
source=importlib.util.module_from_spec(spec);sys.modules[spec.name]=source
spec.loader.exec_module(source)
forward=source.forward
inverse=source.inverse
MAX_X=source.MAX_X
