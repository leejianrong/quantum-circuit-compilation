# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Retire original A11 across the six inverse low coefficient rows.

After the exact S6 exchange, A11 is a quadratic function of unchanged
A10,S5,S6. Its HMR phase is repaid immediately. One ordinary AND restores
the value before the reverse S6 exchange. Each inverse adder still pays
all of its original forward measurement debts.
"""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import os
import sys

RECORDS=[]
ENDPOINT={}


def snapshot(b):
    from branch_prover import generated_text,Program
    from fourier_resource_expectation import exact_expectation
    text=generated_text(b.finish_circuit())
    return dict(owners=b.num_allocated_qubits,cap=b.max_qubits,
                operations=len(Program(text).operations),
                mean=exact_expectation(text)['mean'])


def measure(label,b,fn):
    before=snapshot(b);result=fn();after=snapshot(b)
    RECORDS.append(dict(label=label,before=before,after=after,
        delta={key:str(Fraction(after['mean'][key])-Fraction(value))
               for key,value in before['mean'].items()}))
    return result


def apply(ctx):
    native=sys.modules['variant_patch_native64_q44_A10_swap']
    original=native.coef_inverse
    enabled=os.environ.get('A11_RETIREMENT_ENABLED','1')=='1'
    old_window=native.inverse_low_window
    def window(b,*args,**kwargs):
        return measure('inverse_low_window',b,lambda:old_window(b,*args,**kwargs))
    native.inverse_low_window=window

    def inverse(b,v,D,S,token,debts,truths):
        base=native.CTX.baseline;ar=base.ar
        S.append(native.prep(b,[D[i]for i in(9,10,11,12)]+S,native.PLANS['S5current']))
        native.mark(b,'coefficient_inverse_overflow')
        ar._deferred_overflow(b,v[:6],[],D,token,inverse=True)
        high=D[12];b.cx(S[5],high);b.ccx(D[11],S[5],high);D[12]=None;S.append(high)
        def release():
            phase=b.alloc_bits(1)[0];b.hmr(D[11],phase);b.free(D[11]);D[11]=None
            native.cb.emit_phase(b,[D[10],S[5],S[6]],phase,native.PLANS['A11']);b.free(phase)
        measure('retire_A11_after_S6_exchange',b,release)
        m=b.alloc_bits(1)[0];b.hmr(D[7],m);b.cx(token.saved_bit,D[7]);b.cx(D[7],token.saved_bit);b.free(token.saved_bit);token.saved_bit=None
        for i in reversed(range(1,6)):
            shift=5-i;carry=base._coefficient_carry(b,S,v[i],shift)
            for q in D[:7]:b.cx(v[i],q)
            native.inverse_low_window(b,S[shift+1:],D[:7],token.row_debts[i],carry_in=carry,top_outcome=m,ar=ar)
            for q in D[:7]:b.cx(v[i],q)
            base._clear_coefficient_carry(b,S,v[i],shift,carry)
            if shift == 1:
                retired=shift-1;native.erase(b,S[retired],truths['S'][retired],debts);S[retired]=None
        native.omitted_settle_endpoint(b,v,D,S,token,debts,truths,m)
        assert D[11] is None and D[12] is None and S[1] is not None
        ENDPOINT.update(metadata_names=[f'A{i}'for i in range(11)]+[f'S{i}'for i in(2,3,4,5,6,1)],
            metadata_owners=[str(q)for q in D[:11]]+[str(S[i])for i in(2,3,4,5,6,1)],
            retained_S1_owner=str(S[1]),owners=b.num_allocated_qubits,
            omitted_endpoint_products=2,raw_expected_inverse_coefficient_products='42')

    def measured_inverse(*args,**kwargs):
        return measure('whole_inverse_coefficient',args[0],lambda:(inverse if enabled else original)(*args,**kwargs))
    native.coef_inverse=measured_inverse


def emit_body(*args,**kwargs):
    result=sys.modules['variant_patch_native64_q44_A10_swap'].emit_body(*args,**kwargs)
    Path(os.environ['A11_LIFETIME_LEDGER']).write_text(json.dumps(dict(
        notice=__import__('loader64').NOTICE,status='MEASURED_RETAINED_S1_CHANGED_ENDPOINT_LIFETIME_COMPONENT',
        enabled=os.environ.get('A11_RETIREMENT_ENABLED','1')=='1',records=RECORDS,endpoint=ENDPOINT,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        finishing_and_full_proof_not_implied=True,no_submission=True,official_salt_panels_run=0),indent=2)+'\n')
    return result
