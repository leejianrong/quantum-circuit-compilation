# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Own64-row arbitrary-S0 fusion lifecycle; measured emission precedes proof."""
from pathlib import Path
from types import SimpleNamespace
import hashlib,json,sys
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'fusion'))
from native_loader64 import emit as emit_loader,decode as decode_loader,Debts,plan as decode_plan
from loader64 import cb,FULL
from cleanup6 import cleanup as cleanup_loader
from metadata64 import truth
from root11_coefficient import inverse_low_window
CTX=None;TRACE=[];TABLE=HERE/'numeric/lattice_d13_half38sel.json'
FIRST=HERE/'q44/first.json';SECOND=HERE/'q43/second_cap19.json'
PLANS={}

def plan(values,target,rows):
    fs=[truth(v)for v in values];wanted=truth(target);book=cb.Codebook(fs,rows);p=book.represent(wanted,trials=128,seed=42);assert p is not None
    return book.improve_preserving_kernel(p,rounds=32,subspace_bits=7,seed=42)
def bit(v,i):return(np.asarray(v,dtype=np.int64)>>i)&1

def apply(ctx):
    global CTX
    CTX=ctx;table=json.loads(TABLE.read_text());A=np.asarray(table['A']);S=np.asarray(table['S']);a=np.arange(64)
    PLANS['S5initial']=plan([bit(A,i)for i in range(7,13)]+[bit(S,i)for i in range(5)],bit(S,5),64)
    PLANS['A11']=plan([bit(A,10),bit(S,5),bit(S,6)],bit(A,11),64)
    metadata=json.loads((HERE/'metadata_A10_swap.json').read_text())
    assert hashlib.sha256(TABLE.read_bytes()).hexdigest()==metadata['table_sha256']
    PLANS['A10first']=decode_plan(metadata['first']['plan']);PLANS['A10second']=decode_plan(metadata['second']['plan'])
    for key,values in [('A10first',[bit(A,i)for i in(8,9,11)]+[bit(S,i)for i in range(7)]),('A10second',[bit(A,i)for i in(8,9)]+[bit(S,i)for i in range(7)]+[bit(A,7)])]:
        assert PLANS[key].and_count==2 and PLANS[key].evaluate_functions([truth(x)for x in values],FULL)==truth(bit(A,10))
    v=np.arange(4096);D=np.asarray(table['D']);SS=S[v>>6]
    PLANS['S5current']=plan([bit(D,i)for i in(9,10,11,12)]+[bit(SS,i)for i in range(5)],bit(SS,5),4096)
    assert PLANS['S5initial'].and_count==1 and PLANS['A11'].and_count==1 and PLANS['A10first'].and_count==2 and PLANS['A10second'].and_count==2 and PLANS['S5current'].and_count==2
    import half_product64
    half_product64.ROUNDING_MASK=0;half_product64.LAST_ZERO=True;half_product64.ABSENT_ZERO=True;half_product64.apply(ctx)

def mark(b,label,trace=None,owners=None):
    row=dict(label=label,live_owners=b.num_allocated_qubits);TRACE.append(row)
    if trace is not None:trace.append(row)
    hook=CTX.components['lifecycle'].CUT_HOOK
    if hook:hook(label,b,{}if owners is None else{key:list(x)for key,x in owners.items()})

def erase(b,q,truthv,debts):debts.erase(b,q,truthv)
def prep(b,variables,p):
    q=b.alloc_qubits(1)[0];cb.emit_xor(b,variables,q,p);return q

def restore_a5(b,v,D):
    # Two-product network from the full4096-root metadata contract.
    g=b.alloc_qubits(1)[0];q=b.alloc_qubits(1)[0]
    p=cb.factor_polynomial(4,False,0,{(0,3),(1,3),(2,3)})
    cb.emit_xor(b,[D[9],D[10],D[11],D[12]],g,p)
    p=cb.factor_polynomial(6,False,(1<<1)|(1<<2)|(1<<3),{(0,3),(0,4),(2,3),(2,4),(3,4),(3,5),(4,5)})
    # (D9^D11^v9^g)*(D12^v9) contributes a linear v9 term.
    p=cb.factor_polynomial(6,False,(1<<1)|(1<<2)|(1<<3)|(1<<4),{(0,3),(0,4),(2,3),(2,4),(3,4),(3,5),(4,5)})
    cb.emit_xor(b,[D[9],D[10],D[11],D[12],v[9],g],q,p)
    m=b.alloc_bits(1)[0];b.hmr(g,m);b.free(g)
    cb.emit_phase(b,[D[9],D[10],D[11],D[12]],m,cb.factor_polynomial(4,False,0,{(0,3),(1,3),(2,3)}));b.free(m)
    assert p.and_count==1;v[10]=q

def restore_a6(b,v,D):
    p=cb.factor_polynomial(4,False,0b1111,{(0,1),(0,3),(1,3)})
    v[11]=prep(b,[D[10],D[11],D[12],v[10]],p)

def disposable(b,source,target,carry,erase_carry):
    ar=CTX.baseline.ar;aa,bb,preserve=ar._inputs(source,target,carry,False);debts={};incoming=carry
    for i,(x,y)in enumerate(zip(aa[:-2],bb[:-2])):
        frame=ar._compute_carry(b,x,y,incoming,preserve=preserve);ar._sum_keep_carry(b,frame)
        if i==0:erase_carry(incoming)
        else:
            m=b.alloc_bits(1)[0];b.hmr(incoming,m);b.free(incoming);debts[i]=m
        incoming=frame.outgoing
    ar._finish_top(b,aa,bb,incoming,preserve);m=b.alloc_bits(1)[0];b.hmr(incoming,m);b.free(incoming);debts[len(bb)-2]=m
    return ar.CarryDebt(debts,len(bb))

def overflow_forward(b,v,D,token):
    base=CTX.baseline;sign=v[5];top=D[7];saved=token.saved_bit
    b.cx(sign,saved);b.cx(sign,top);b.x(top);wrap=b.alloc_qubits(1)[0];b.ccx(saved,top,wrap)
    for q in D[8:]:b.cx(sign,q)
    def clear(q):b.del_and(saved,top,q);b.free(q)
    token.overflow_debt=disposable(b,[],D[8:],wrap,clear)
    for q in D[8:]:b.cx(sign,q)
    b.x(top);b.cx(sign,top);b.cx(sign,saved)

def coef_forward(b,v,D,S,debts,truths,second=False):
    base=CTX.baseline;S.append(prep(b,[D[i]for i in range(7,13)]+S,PLANS['S5initial']))
    high=D[12];b.cx(S[5],high);b.ccx(D[11],S[5],high);D[12]=None;S.append(high)
    retired={}
    if not second:
        erase(b,v[10],truths['root'][4],debts);v[10]=None
    for i in ((10,11)if second else(10,)):
        m=b.alloc_bits(1)[0];b.hmr(D[i],m);b.free(D[i]);D[i]=None;retired[i]=m
    mark(b,'coefficient_rows_entry2'if second else'coefficient_rows_entry1')
    saved=b.alloc_qubits(1)[0];b.cx(D[7],saved);token=base.ar.DeferredBoundedToken(SimpleNamespace(last=6,signed_source=False),saved,8,[])
    for i in range(6):
        shift=5-i;carry=base._coefficient_carry(b,S,v[i],shift)
        for q in D[:8]:b.cx(v[i],q)
        debt=disposable(b,S[shift+1:],D[:8],carry,lambda q,i=i,shift=shift:base._clear_coefficient_carry(b,S,v[i],shift,q));token.row_debts.append(debt)
        for q in D[:8]:b.cx(v[i],q)
    if second:
        D[10]=prep(b,[D[8],D[9]]+S+[saved],PLANS['A10second'])
        D[11]=prep(b,[D[10],S[5],S[6]],PLANS['A11'])
    else:
        D[10]=prep(b,[D[8],D[9],D[11]]+S,PLANS['A10first'])
    for i,m in retired.items():base.ar.repay_saved_bit(b,D[i],m)
    b.cx(S[5],high);b.ccx(D[11],S[5],high);D[12]=high;S[6]=None
    erase(b,S[5],truths['S'][5],debts);S[5]=None
    if second:
        m=b.alloc_bits(1)[0];b.hmr(S[4],m);b.free(S[4]);S[4]=None;token.s4_outcome=m
    else:
        for i in range(5):erase(b,S[i],truths['S'][i],debts);S[i]=None
    mark(b,'coefficient_overflow_entry2'if second else'coefficient_overflow_entry1')
    overflow_forward(b,v,D,token);return token

def coef_inverse(b,v,D,S,token,debts,truths):
    base=CTX.baseline;ar=base.ar
    S.append(prep(b,[D[i]for i in(9,10,11,12)]+S,PLANS['S5current']))
    mark(b,'coefficient_inverse_overflow')
    ar._deferred_overflow(b,v[:6],[],D,token,inverse=True)
    high=D[12];b.cx(S[5],high);b.ccx(D[11],S[5],high);D[12]=None;S.append(high)
    m=b.alloc_bits(1)[0];b.hmr(D[7],m);b.cx(token.saved_bit,D[7]);b.cx(D[7],token.saved_bit);b.free(token.saved_bit);token.saved_bit=None
    for i in reversed(range(6)):
        shift=5-i;carry=base._coefficient_carry(b,S,v[i],shift)
        for q in D[:7]:b.cx(v[i],q)
        inverse_low_window(b,S[shift+1:],D[:7],token.row_debts[i],carry_in=carry,top_outcome=m,ar=ar)
        for q in D[:7]:b.cx(v[i],q)
        base._clear_coefficient_carry(b,S,v[i],shift,carry)
        if shift in (1,2):
            retired=shift-1;erase(b,S[retired],truths['S'][retired],debts);S[retired]=None
    ar.repay_saved_bit(b,D[7],m)
    b.cx(S[5],high);b.ccx(D[11],S[5],high);D[12]=high;S.pop()
    erase(b,S[5],truths['S'][5],debts);S.pop()

def emit_body(b,v12,h10,flags4,table_module,divider_module,decode_root_callback,*,trace=None):
    base=CTX.baseline;L=CTX.components['lifecycle'];body=sys.modules['variant_patch_patch_w47_body'];h2=sys.modules['variant_patch_patch_h2ret'];v=list(v12);h=list(h10);flags=list(flags4)
    table=json.loads(TABLE.read_text());cert1=json.loads(FIRST.read_text());cert2=json.loads(SECOND.read_text());debts=Debts()
    truths=dict(root=cb.word_functions(range(64),6),S=cb.word_functions(table['S'],7));assert h[0]is None
    out=emit_loader(b,v[6:],cert1,debts);D=list(out[:13]);S=list(out[13:]);v[11]=None
    mark(b,'first_table64',trace,dict(v=v,h=h,D=D,S=S,flags=flags))
    first=coef_forward(b,v,D,S,debts,truths);first_snapshot=base.ar.release_saved_bit(b,first.saved_bit);first.saved_bit=None
    seed,seed_token=base.seed_forward(b,v,D);h=body.unpack_h0_after_seed(b,v,h,flags,seed)
    word,product_token=base.product_forward(b,D,seed,h)
    restore_a5(b,v,D);restore_a6(b,v,D)
    b.x(word[15]);b.cx(word[14],word[15]);b.free(word[15]);P=word[:15]
    first_D=[]
    for q in D:
        m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q);first_D.append(m)
    mark(b,'coefficient_retired_for_divider',trace,dict(v=v,P=P,flags=flags))
    P=list(divider_module.compute_phase_cleanup(b,v,P,flags))
    out=emit_loader(b,v[6:],cert2,debts);D=list(out[:13]);S=list(out[13:])
    for i in range(6,12):v[i]=None
    base.ar.repay_saved_bit(b,D[7],first_snapshot)
    second=coef_forward(b,v,D,S,debts,truths,True)
    for q,m in zip(D,first_D):base.ar.repay_saved_bit(b,q,m)
    for a,c in zip(first.row_debts,second.row_debts):base._merge_debts(b,a,c)
    base._merge_debts(b,first.overflow_debt,second.overflow_debt)
    assert v[10]is None
    S=S[:5];high=b.alloc_qubits(1)[0];b.cx(P[14],high);b.x(high);word=P+[high]
    second.s3_outcome=b.alloc_bits(1)[0];b.hmr(S[3],second.s3_outcome);b.free(S[3]);S[3]=None
    mark(b,'inverse_product_data64',trace,dict(v=v,word=word,D=D,S=S,flags=flags,snapshot=[second.saved_bit]))
    dirty=[q for q in v if q is not None]+flags+[q for q in S if q is not None]+[second.saved_bit]
    seed,h=L.product_inverse(b,v,D,word,product_token,dirty);base.seed_cleanup(b,v,D,seed,seed_token)
    S[3]=rebuild_s3(b,D,S);base.ar.repay_saved_bit(b,S[3],second.s3_outcome)
    S[4]=h2.rebuild_h2(b,D,S[2],S[3]);base.ar.repay_saved_bit(b,S[4],second.s4_outcome)
    coef_inverse(b,v,D,S,second,debts,truths)
    outputs=D+[q for q in S if q is not None]
    data=dict(cert2,reusable_input_bits=list(range(6)),fixed_address_bits=[],output_truths=[t for i,t in enumerate(cert2['output_truths'])if i not in(13,14)])
    address=[None]*6;decode_plan_data=json.loads((HERE/'decoder_dp_early01.json').read_text())
    for item in decode_plan_data['steps']:
        variables=outputs+[address[i]for i in range(6)if item['before_mask']>>i&1]
        address[item['bit']]=prep(b,variables,decode_plan(item['plan']))
    v[6:]=address
    mark(b,'raw_root64_restored',trace,dict(v=v,h=h,A=D,S=S,flags=flags))
    cleanup_loader(b,address,outputs,data,debts)
    assert not debts.pending and b.num_allocated_qubits==26 and all(q is not None for q in v)
    mark(b,'body_return',trace,dict(v=v,h=h,flags=flags));return v,h


def rebuild_s3(b,D,S):
    data=json.loads((HERE/'retire_s3_shared_cofactor.json').read_text())
    variables=[D[i]for i in range(8,13)]+S[:3]
    shared=prep(b,variables,decode_plan(data['shared_plan']))
    target=prep(b,variables,decode_plan(data['base_without_shared']));b.cx(shared,target)
    diff=prep(b,variables,decode_plan(data['difference_without_shared']));b.cx(shared,diff)
    indices=list(cb.bits(data['split_mask']));pivot=indices[0]
    for i in indices[1:]:b.cx(variables[i],variables[pivot])
    if data['split_invert']:b.x(variables[pivot])
    b.ccx(variables[pivot],diff,target)
    if data['split_invert']:b.x(variables[pivot])
    for i in reversed(indices[1:]):b.cx(variables[i],variables[pivot])
    for q,key in ((diff,'difference_plan'),(shared,'shared_plan')):
        m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q);cb.emit_phase(b,variables,m,decode_plan(data[key]));b.free(m)
    return target
