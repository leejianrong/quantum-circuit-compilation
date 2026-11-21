# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Emit a declared Q45 study with explicit Q46 exception windows; not a Q45 claim."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import traceback

OWN=Path(__file__).resolve().parent
HERE=OWN.parent/"fusion"
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(OWN))
FG=HERE/'runtime'
sys.path.insert(0,str(FG/'tools'))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--windows',default='loader1,coef1,prodfwd,divfwd,endpoint,divider,loader2,coef2,coefinv,tail')
    ap.add_argument('--pack',action='store_true')
    ap.add_argument('--endpoint45',action='store_true')
    ap.add_argument('--loader45',action='store_true')
    ap.add_argument('--product45',action='store_true')
    ap.add_argument('--divforward45',action='store_true')
    ap.add_argument('--coefinverse45',action='store_true')
    ap.add_argument('--coefsecond45',action='store_true')
    ap.add_argument('--inverse-policy',action='store_true')
    ap.add_argument('--native-tail',action='store_true')
    ap.add_argument('--precision-k',type=int,default=None)
    ap.add_argument('--precision-up-rows',default='')
    ap.add_argument('--precision-start',type=int,default=25)
    ap.add_argument('--precision-overrides',default='')
    ap.add_argument('--angles',type=Path)
    ap.add_argument('--product-k-rows',default='')
    ap.add_argument('--product-rounding',choices=('nearest','floor'),default='nearest')
    ap.add_argument('--coefficient-precision',type=int)
    ap.add_argument('--coefficient-top-transfer',action='store_true')
    ap.add_argument('--half-numerator',action='store_true')
    ap.add_argument('--half-zero-feed',action='store_true')
    ap.add_argument('--half-absent-zero',action='store_true')
    ap.add_argument('--half-phase38',action='store_true')
    ap.add_argument('--q44-components',action='store_true')
    ap.add_argument('--mixed-tail45',action='store_true')
    ap.add_argument('--half-rounding-mask',type=int,default=0)
    ap.add_argument('--half-last-zero',action='store_true')
    ap.add_argument('--strict',action='store_true')
    ap.add_argument('--base',type=int,default=45)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    os.environ['CMP_CAP_BASE']=str(args.base);os.environ['CMP_CAPWIN_BLOCKS']=args.windows
    import build_variant as bv
    patches=[]
    for line in (FG/'patches/PATCH_ORDER.txt').read_text().splitlines():
        terms=line.split()
        if terms and terms[0]=='patch':
            path=HERE/'width_patches'/terms[1] if terms[1] in ('patch_w47_body.py','patch_hret_sat_s15a.py') else FG/'patches'/terms[1]
            if args.coefsecond45 and terms[1]=='patch_coef2_q46.py':path=HERE/'patch_coef_second45.py'
            if args.precision_k is not None and terms[1]=='patch_hret_sat_s15a.py':path=HERE/'precision_hret.py'
            module=bv.load_patch(path)
            if args.half_absent_zero and terms[1]=='patch_second46_c19_69.py':
                module.LOADERS=HERE/'second_loader_absent_zero.py'
            if args.pack and terms[1]=='patch_w47_body.py':module.PACK=True
            if args.product45 and terms[1]=='patch_w47_body.py':module.A5_AROUND_PRODUCT=True
            if args.endpoint45 and terms[1]=='patch_endpoint_v9e2.py':
                spec=importlib.util.spec_from_file_location('own_endpoint45_core',HERE/'endpoint45_core.py')
                core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
                core.QMAX=45;core.RETIRE_V9=module._core.RETIRE_V9;core.V10_FROM_G1=True
                module._core=core
                module.E_HOLD=set(range(1,13))-{9,11}
                module.F_HOLD=set(range(13))-{12}
                module.R2={(11,13):(0,2),(6,18):(4,7)}
            if args.loader45 and terms[1]=='patch_second46_c19_69.py':
                module.CERT=str(FG/'agents/loader2/certs/second_cap18_75_q45.json')
                module.CERT_SHA256=hashlib.sha256(Path(module.CERT).read_bytes()).hexdigest()
            patches.append(module)
    if args.divforward45:patches.append(bv.load_patch(HERE/'patch_divider_forward45.py'))
    if args.precision_k is not None:
        precision=bv.load_patch(HERE/'patch_divider_precision.py');precision.EXTRA=args.precision_k;precision.EXTRA_START=args.precision_start;precision.K_OVERRIDES={int(k):int(v) for k,v in (p.split(':') for p in args.precision_overrides.split(',') if p)};precision.UP_ROWS={int(x) for x in args.precision_up_rows.split(',') if x};patches.append(precision)
    if args.coefinverse45:patches.append(bv.load_patch(HERE/'patch_coef_inverse45.py'))
    if args.q44_components:patches.append(bv.load_patch(HERE/'patch_q44_components.py'))
    if args.inverse_policy:patches.append(bv.load_patch(HERE/'patch_inverse_policy.py'))
    if args.native_tail:patches.append(bv.load_patch(HERE/'patch_tail_native.py'))
    if args.angles and not args.half_phase38:
        phase=bv.load_patch(HERE/'patch_phase_angles.py');phase.ANGLE_FILE=args.angles.resolve();patches.append(phase)
    if args.product_k_rows:
        product=bv.load_patch(HERE/'patch_product_precision.py');product.K_ROWS={int(k):int(v) for k,v in (s.split(':') for s in args.product_k_rows.split(','))};product.ROUNDING=args.product_rounding;patches.append(product)
    if args.coefficient_precision is not None:
        coefficient=bv.load_patch(HERE/'patch_coefficient_precision.py');coefficient.K=args.coefficient_precision;coefficient.TOP_TRANSFER=args.coefficient_top_transfer;patches.append(coefficient)
    if args.half_numerator:
        product=bv.load_patch(HERE/'patch_half_numerator.py');product.ROUNDING_MASK=args.half_rounding_mask
        product.LAST_ZERO=args.half_last_zero;product.ABSENT_ZERO=args.half_absent_zero;patches.append(product)
    if args.half_zero_feed:
        assert args.half_numerator and args.precision_k is not None
        zero=bv.load_patch(HERE/'patch_half_zero_feed_history24_v3.py');zero.ABSENT_OUTSIDE=args.half_absent_zero
        zero.EARLY_HISTORY12=args.q44_components;patches.append(zero)
    assert not args.half_absent_zero or args.half_zero_feed
    if args.half_phase38:
        assert args.half_numerator and args.half_last_zero and args.angles and args.precision_k is not None
        endpoint=bv.load_patch(OWN/'patch_half_endpoint_residue_spare.py');endpoint.ANGLE_FILE=args.angles.resolve()
        endpoint.LAST_CUT=precision.row_k(36);patches.append(endpoint)
    patches.append(bv.load_patch(HERE/'patch_h15_shared_sum.py'))
    patches.append(bv.load_patch(OWN/'native64_q44_A10_swap.py'))
    patches.append(bv.load_patch(OWN/'patch_cleanup_conditional_phase.py'))
    patches.append(bv.load_patch(OWN/'patch_decoder_seven_products.py'))
    patches.append(bv.load_patch(OWN/'patch_garbage_two_owner_cleanup.py'))
    patches.append(bv.load_patch(OWN/'patch_joint_s3_s4_s5_lifetime.py'))
    patches.append(bv.load_patch(OWN/'patch_coefficient_a11_lifetime.py'))
    patches.append(bv.load_patch(OWN/'patch_omitted_row_capture.py'))
    cap=bv.load_patch(HERE/'patch_mixed_cap44.py' if args.mixed_tail45 else FG/'agents/composer/p/patch_capwin45.py');patches.append(cap)
    status={'notice':__import__('loader64').NOTICE,'status':'A10_SWAP_NATIVE_EMISSION_AWAITING_PROOF' ,'requested_base':args.base,'Q46_windows':args.windows.split(','),'pack':args.pack,'endpoint45':args.endpoint45,'loader45':args.loader45,'product45':args.product45}
    try:
        ctx,circuit,text,cuts,trace,layout=bv.build(bv.PatchSet(patches),args.base if args.strict else args.base+1)
        from fourier_resource_expectation import exact_expectation
        counts=exact_expectation(text)
        circuit.to_file(str(args.out/'study.kmb'),format='kmb')
        (args.out/'study.kmx').write_text(text)
        status.update(emitted=True,Q=circuit.num_qubits,expectation=counts,cuts=cuts,trace=trace,kmb_sha256=hashlib.sha256((args.out/'study.kmb').read_bytes()).hexdigest(),explicit_cap_window_log=cap.LOG)
    except Exception as error:
        status.update(emitted=False,error=str(error),failure_trace=traceback.format_exc(),window_log=cap.LOG)
    (args.out/'study.json').write_text(json.dumps(status,indent=2)+'\n')
    print(json.dumps({k:v for k,v in status.items() if k not in ('cuts','trace','expectation','failure_trace')},indent=1),flush=True)

if __name__=='__main__':main()
