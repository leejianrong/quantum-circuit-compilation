# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Compose the full-proof first-product patch with the disjoint bank patch."""
from pathlib import Path
import argparse,json,shlex
from map_incumbent_width import BASE,NOTICE,Program,sha
def semantic(o):return o.kind,o.arguments,o.condition,o.half_turns
def operation_lines(lines):
 out=[]
 for i,line in enumerate(lines):
  words=shlex.split(line,comments=True)
  if words and words[0] not in ('REGISTER','APPEND_TO_REGISTER','INFO_TAG','DEBUG_PRINT'):out.append(i)
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();assert not args.out.exists()
 paths=[BASE/'root/q43_phase_and_late_width_v1/candidate_text.kmx',BASE/'agents/temporal_merges/q43_first_product_v9_native_v1/candidate_text.kmx',BASE/'agents/paid_helper/fourth_bank_deferred_phase_v1/candidate_text.kmx']
 expected=['501f1d90c3a82c45c6a60d6ec478bd89c91ebc3f72e847cc56f8d4182a014e43','c8ef0a00dd40536c64719f4588724421a9bb5fce96dcd41daa9d90c907a42fab','95f170ce3dade12c482df8be846f0fade6f99bcb869b0094f821ec98a0a66740']
 assert [sha(p) for p in paths]==expected
 texts=[p.read_text() for p in paths];base,patch,target=[Program(t) for t in texts]
 a,b,c=3796,4933,4994
 assert [semantic(o) for o in base.operations[:a]]==[semantic(o) for o in patch.operations[:a]]
 assert [semantic(o) for o in base.operations[b:]]==[semantic(o) for o in patch.operations[c:]]
 assert [semantic(o) for o in base.operations[:8530]]==[semantic(o) for o in target.operations[:8530]]
 assert base.registers==patch.registers==target.registers
 fresh=patch.wires-base.wires;assert not fresh.intersection(target.wires)
 src=texts[1].splitlines();dst=texts[2].splitlines()
 sp,dp=operation_lines(src),operation_lines(dst)
 assert len(sp)==len(patch.operations) and len(dp)==len(target.operations)
 insert=src[sp[a]:sp[c]]
 changed='\n'.join(['# '+NOTICE]+dst[:dp[a]]+insert+dst[dp[b]:])+'\n'
 result=Program(changed);assert len(result.operations)==len(target.operations)+61
 assert result.measurements==target.measurements+(patch.measurements-base.measurements)
 assert result.registers==target.registers
 args.out.mkdir(parents=True);out=args.out/'candidate_text.kmx';out.write_text(changed)
 report=dict(notice=NOTICE,status='ROOT_DISJOINT_FULL_PROOF_COMPONENTS_COMPOSED_NATIVE_PROOF_PENDING',source_parent_sha256=expected[0],first_product_component_sha256=expected[1],bank_component_sha256=expected[2],candidate_native_sha256=sha(out),source_interval=[a,b],new_interval=[a,c],operations=len(result.operations),HMR=result.measurements,fresh_classical_owners=sorted(fresh),whole_Q=44,modelled_expected_Toffolis='5805/4',full_domain_proof_pending=True,global_Q43_not_yet_claimed=True,bindings={str(p.relative_to(BASE)):sha(p) for p in paths+[Path(__file__)]})
 (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
