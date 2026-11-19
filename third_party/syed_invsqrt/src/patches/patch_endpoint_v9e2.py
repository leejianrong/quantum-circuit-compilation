# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""COMPOSER PIN e2 (frozen copy of the width2 endpoint exactly as built in runs/cmp_q46h = deliver/q46t8: patch sha 4fce573e...,
core agents/composer/p/w2core_e2.py = width2 core sha d7809457..., form agents/composer/p/v9_form_e2.json sha c9b1ab28...;
width2 edits its files in place, so delivered builds load these frozen copies; env W2_* must be unset).
width2: Q46 walk8 endpoint with root bit v9 ALSO retired across the endpoint (one more spare lane), so the
Q47 hold sets fit at real allocation <= 46. v9 is rebuilt at exit from (v8, s12..s16) by the exact straight-line
AND program in W2_V9_FORM (tools/minand_sat.py JSON; inputs named by wire in the measuring build, mapped to roles
below). Hold sets from env W2_E_HOLD / W2_F_HOLD / W2_R2 (defaults = walk8q47's). Core = agents/width2/p/w2_walk8_core.py.
v10 is then rebuilt with ONE AND from gate g1 of the v9 program: v10 = v9 ^ g1 ^ (s13^g1)(v9^s14) (exact on the full
domain; env W2_V10_G1=0 keeps the phase agent's 2-AND v10 rebuild).
W2_V9_PLACEHOLDER=1: ANALYSIS ONLY (wrong circuit): rebuild v9 as 0, to measure the gross value.
Replaces only divider.phase_endpoint."""
import importlib.util, json, os
from pathlib import Path
_CORE = Path('@FG_ROOT@/agents/composer/p/w2core_e2.py')
_spec = importlib.util.spec_from_file_location('width2_walk8_core_v9', _CORE)
_core = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_core)
_core.QMAX = 46
ROLE = {'q18': 'v8', 'q17': 'v7', 'q9': 's12', 'q34': 's13', 'q36': 's14', 'q0': 's15', 'q30': 's16', 'q32': 's17'}
if os.environ.get('W2_V9_PLACEHOLDER') == '1':
    FORM = dict(inputs=[], gates=[], output=dict(constant=0, terms=[]))
else:
    _f = json.loads(Path(os.environ.get('W2_V9_FORM', '@FG_ROOT@/agents/composer/p/v9_form_e2.json')).read_text())
    assert _f['status'] == 'SAT'
    FORM = dict(inputs=[ROLE[x] for x in _f['inputs']], gates=_f['gates'], output=_f['output'])
_core.RETIRE_V9 = FORM
# v10 from gate g1 of THIS v9 program (1 AND instead of 2): only for the pinned form (sha-checked)
import hashlib
_FORM_PATH = Path(os.environ.get('W2_V9_FORM', '@FG_ROOT@/agents/composer/p/v9_form_e2.json'))
_core.V10_FROM_G1 = (os.environ.get('W2_V10_G1', '1') == '1' and os.environ.get('W2_V9_PLACEHOLDER') != '1'
                     and hashlib.sha256(_FORM_PATH.read_bytes()).hexdigest().startswith('221ee58f0074ac4b'))
E_HOLD = set(int(x) for x in os.environ.get('W2_E_HOLD', ','.join(map(str, range(1, 13)))).split(',') if x)
F_HOLD = set(int(x) for x in os.environ.get('W2_F_HOLD', ','.join(map(str, range(13)))).split(',') if x)
R2 = {(a, b): (c, d) for a, b, c, d in json.loads(os.environ.get('W2_R2', '[[11,13,0,2],[10,14,0,3],[7,17,3,6],[6,18,4,7]]'))}


def apply(ctx):
    divider = ctx.phase.BINDING.divider
    assert divider is ctx.old.divider
    divider.phase_endpoint = _core.make_endpoint(ctx.phase, E_HOLD, F_HOLD, R2)
