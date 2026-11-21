# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Four-low-bit root11 coefficient interpolation: model and native ledger.

The original128 address rows remain applicable, but numerical table choices
and every metadata erasure require a new full proof before integration.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse
import hashlib
import json
import numpy as np
import precision_sensitivity as ps


def coefficient_lookup11(A,S):
    v=np.arange(2048,dtype=np.int64);A=np.asarray(A,dtype=np.int64)[v>>4];S=np.asarray(S,dtype=np.int64)[v>>4]
    C=A.copy()
    for i in range(4):
        shift=3-i;sign=(v>>i)&1;source=S>>(shift+1)
        carry=(((S>>shift)&1)*(1-sign)+((S>>(shift-1))&1)*sign) if shift else (S&1)*(1-sign)
        C+=(1-2*sign)*(source+carry)
    return C


def inverse_low_window(b,source,target,debt,*,carry_in,top_outcome,ar):
    """Undo the shortened low window and pay the measured old top.

    The final single-bit segment has a literal-zero source, so its overflow
    sign is a Clifford CZ. Earlier boundary carries are measured only after
    all dependent segments have been repaid. Their exact borrow phases use
    the same immutable arithmetic implementation as the incumbent.
    """
    word=list(target);a=list(source)+[False]*(len(word)-len(source))
    n=len(word);entry=b.num_allocated_qubits;clean=b.max_qubits-entry
    assert a[-1] is False and debt.width==n+1 and not debt.consumed
    assert set(debt.measurements)==set(range(1,n))
    options=[]
    def partition(remaining,held,sizes):
        if not remaining:
            options.append(tuple(sizes));return
        for length in range(1,min(remaining,clean-held)+1):
            partition(remaining-length,held+1,sizes+[length])
    partition(n-1,0,[])
    if not options:raise ValueError(f'{n}-bit shortened inverse needs more than {clean} clean carries')
    sizes=min(options,key=lambda row:(sum(x-1 for x in row),row))+(1,)
    debt.consumed=True;b.x(ar.km.array(word));boundaries=[];start=0;carry=carry_in
    for index,length in enumerate(sizes):
        last=index==len(sizes)-1;aa=a[start:start+length];bb=word[start:start+length]
        outgoing=ar._segment_repay(b,aa,bb,carry,retain_outgoing=not last,
            preserve=None,start=start,debt=debt,overflow_phase=top_outcome if last else None)
        if not last:boundaries.append((aa,bb,carry,outgoing))
        carry=outgoing;start+=length
    for aa,bb,incoming,outgoing in reversed(boundaries):
        outcome=b.alloc_bits(1)[0];b.hmr(outgoing,outcome);b.free(outgoing)
        b.push_condition(outcome);ar._phase_borrow(b,aa,bb,incoming,preserve=None);b.pop_condition();b.free(outcome)
    b.x(ar.km.array(word))
    assert not debt.measurements and b.num_allocated_qubits==entry


def native_build(extra_coefficient_bits=0,owners=42,inverse_owners=40,cap=46,even_slope=False):
    variant,_,_=ps.ra.load_everything();modules=variant.install();base=modules['lifecycle'].baseline;ar=base.ar;km=base.km
    from branch_prover import generated_text
    from fourier_resource_expectation import exact_expectation
    b=km.CircuitBuilder();b.set_max_qubits(cap)
    assert extra_coefficient_bits in (0,1)
    cwidth=13+extra_coefficient_bits;swidth=6+extra_coefficient_bits;window=7+extra_coefficient_bits
    stored_s=swidth-int(even_slope)
    data=list(b.alloc_qubits(owners));C=data[:cwidth];S=([False] if even_slope else [])+data[cwidth:cwidth+stored_s]
    r=data[cwidth+stored_s:cwidth+stored_s+4];dummy=data[cwidth+stored_s+4:]
    saved=b.alloc_qubits(1)[0];b.cx(C[window-1],saved)
    token=ar.DeferredBoundedToken(SimpleNamespace(last=4,signed_source=False),saved,window,[])
    def disposable(source,target,carry,erase):
        aa,bb,preserve=ar._inputs(source,target,carry,False);incoming=carry;debts={}
        for pos,(x,y) in enumerate(zip(aa[:-2],bb[:-2])):
            frame=ar._compute_carry(b,x,y,incoming,preserve=preserve);ar._sum_keep_carry(b,frame)
            if pos==0:erase(incoming)
            else:
                m=b.alloc_bits(1)[0];b.hmr(incoming,m);b.free(incoming);debts[pos]=m
            incoming=frame.outgoing
        ar._finish_top(b,aa,bb,incoming,preserve)
        m=b.alloc_bits(1)[0];b.hmr(incoming,m);b.free(incoming);debts[len(bb)-2]=m
        return ar.CarryDebt(debts,len(bb))
    def row_carry(i):
        shift=3-i
        if even_slope and shift==0:return False
        if even_slope and shift==1:
            value=b.alloc_qubits(1)[0];b.x(r[i]);b.ccx(S[1],r[i],value);b.x(r[i]);return value
        return base._coefficient_carry(b,S,r[i],shift)
    def clear_row(i,value):
        if value is False:return
        if even_slope and i==2:
            b.x(r[i]);b.del_and(S[1],r[i],value);b.x(r[i]);b.free(value)
        else:base._clear_coefficient_carry(b,S,r[i],3-i,value)
    for i in range(4):
        shift=3-i;carry=row_carry(i)
        for q in C[:window]:b.cx(r[i],q)
        if carry is False:debt=ar.forward_add(b,S[shift+1:],C[:window],carry_in=False)
        else:debt=disposable(S[shift+1:],C[:window],carry,lambda value,i=i:clear_row(i,value))
        token.row_debts.append(debt)
        for q in C[:window]:b.cx(r[i],q)
    sign=r[3];top=C[window-1];b.cx(sign,saved);b.cx(sign,top);b.x(top)
    wrap=b.alloc_qubits(1)[0];b.ccx(saved,top,wrap)
    for q in C[window:]:b.cx(sign,q)
    def erase(value):b.del_and(saved,top,value);b.free(value)
    token.overflow_debt=disposable([],C[window:],wrap,erase)
    for q in C[window:]:b.cx(sign,q)
    b.x(top);b.cx(sign,top);b.cx(sign,saved)
    f=b.finish_circuit();ft=generated_text(f)
    # These zero dummy owners model the smaller inverse-entry live set only.
    dropped=owners+1-inverse_owners;assert 0<=dropped<=len(dummy)
    if dropped:
        for q in dummy[-dropped:]:b.free(q)
    ar._deferred_overflow(b,r,S,C,token,inverse=True)
    phase=b.alloc_bits(1)[0];b.hmr(top,phase);b.cx(saved,top);b.cx(top,saved);b.free(saved);token.saved_bit=None
    transfer=modules['coefficient']
    for i in reversed(range(4)):
        shift=3-i;carry=row_carry(i)
        for q in C[:window-1]:b.cx(r[i],q)
        if extra_coefficient_bits:
            inverse_low_window(b,S[shift+1:],C[:window-1],token.row_debts[i],carry_in=carry,top_outcome=phase,ar=ar)
        else:
            transfer.inverse_low6(b,S[shift+1:],C[:6],token.row_debts[i],carry_in=carry,top_outcome=phase,ar=ar)
        for q in C[:window-1]:b.cx(r[i],q)
        clear_row(i,carry)
    ar.repay_saved_bit(b,top,phase)
    p=b.finish_circuit();pt=generated_text(p)
    return f,p,ft,pt,exact_expectation(ft),exact_expectation(pt)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--extra-coefficient-bits',type=int,choices=(0,1),default=0)
    ap.add_argument('--owners',type=int,default=42);ap.add_argument('--inverse-owners',type=int,default=40)
    ap.add_argument('--cap',type=int,default=46)
    ap.add_argument('--even-slope',action='store_true')
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    f,p,ft,pt,fc,pc=native_build(a.extra_coefficient_bits,a.owners,a.inverse_owners,a.cap,a.even_slope)
    forward=fc['mean_numeric']['toffoli_like'];inverse=pc['mean_numeric']['toffoli_like']-forward
    f.to_file(str(a.out/'forward.kmb'),format='kmb');p.to_file(str(a.out/'roundtrip.kmb'),format='kmb')
    (a.out/'forward.kmx').write_text(ft);(a.out/'roundtrip.kmx').write_text(pt)
    report=dict(status='NATIVE_FOUR_ROW_COEFFICIENT_LEDGER_NOT_FULL_CANDIDATE',Q=p.num_qubits,
        forward=forward,inverse=inverse,two_forward_plus_inverse=2*forward+inverse,
        baseline_two_forward_plus_inverse=118,gross_saving=118-(2*forward+inverse),
        forward_entry_data_owners=a.owners,inverse_entry_owners_including_snapshot=a.inverse_owners,
        coefficient_extra_bits=a.extra_coefficient_bits,
        even_slope=a.even_slope,
        owner_retirement_costs_not_included=True,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),official_salt_panels_run=0,
        no_table_metadata_seed_or_whole_phase_qualification=True)
    (a.out/'ledger.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
