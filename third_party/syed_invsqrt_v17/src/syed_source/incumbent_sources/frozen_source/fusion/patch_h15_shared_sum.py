# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Exact six-product H15 recovery with three reversible AND helpers.

All terminal products accumulate in H15. The three nonterminal helpers are
erased in reverse order with the existing exact HMR/conditional-CZ emitter.
"""
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import os
import sys

NOTICE = "Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research."


def apply(ctx):
    hret = sys.modules['variant_patch_precision_hret']
    plan_path = Path(__file__).with_name('h15_six_plan.json')
    plan = json.loads(plan_path.read_text())
    assert hashlib.sha256(plan_path.read_bytes()).hexdigest() == 'b4143c355c54b01d866e687866eefca917a091783bc9db88b731b5fd6b166499'
    assert plan['k'] == 6 and len(plan['inputs']) == 7
    hret._SAT[15] = plan
    hret._ROLES['u16_13'] = 'next'
    previous = hret._emit_sat

    def emit(b, form, wires, target):
        if form is not plan:
            return previous(b, form, wires, target)
        from branch_prover import generated_text
        from fourier_resource_expectation import exact_expectation
        def snapshot():
            return dict(owners=b.num_allocated_qubits,
                        mean=exact_expectation(generated_text(b.finish_circuit()))['mean'])
        before = snapshot()
        events = []

        class Track:
            def __getattr__(self, name):
                return getattr(b, name)
            def alloc_qubits(self, count):
                values = b.alloc_qubits(count)
                events.append(dict(event='allocate_product_helpers', owners=b.num_allocated_qubits,
                                   allocated=list(map(str, values))))
                return values
            def free(self, owner):
                b.free(owner)
                events.append(dict(event='free', owner=str(owner), owners=b.num_allocated_qubits))

        hret._emit_sat_original(Track(), form, wires, target)
        after = snapshot()
        delta = {k: str(Fraction(after['mean'][k]) - Fraction(v)) for k, v in before['mean'].items()}
        assert delta == dict(toffoli_like='6', T='0', generic_rotations='0'), delta
        assert before['owners'] == after['owners'] == 39
        peak = max([before['owners']] + [r['owners'] for r in events])
        assert peak == 42
        n = len(wires)
        used_later = [any(n+i in g['left']+g['right'] for g in form['gates'][i+1:])
                      for i in range(len(form['gates']))]
        assert used_later == [True, True, True, False, False, False]
        record = dict(notice=NOTICE, status='EXACT_NATIVE_COMPONENT_RESOURCE_LEDGER_AWAITING_WHOLE_PROOF',
                      plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                      patch_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      inputs=dict(zip(form['inputs'], map(str, wires))), target=str(target),
                      entry_with_target=before, exit_with_target=after,
                      raw_entry_owners=before['owners']-1, component_peak=peak,
                      resources=delta, used_later=used_later, events=events,
                      helper_cleanup='Reverse HMR with conditional CZ on the still-live defining affine factors.',
                      helper_cleanup_Toffolis=0, previous_H15_credit_Toffolis=7,
                      component_Toffoli_saving=1,
                      full_domain_all_HMR_claim=False)
        Path(os.environ['H15_SIX_LEDGER']).write_text(json.dumps(record, indent=2)+'\n')

    hret._emit_sat = emit
