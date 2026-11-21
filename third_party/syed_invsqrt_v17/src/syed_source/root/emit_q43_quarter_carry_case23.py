# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Emit the sealed quarter-cost carry correction on the composed width native."""
from pathlib import Path
from fractions import Fraction
import argparse,json,shlex
from map_incumbent_width import BASE,NOTICE,Program,sha
from emit_q43_composed_first_product_and_bank import semantic,operation_lines
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();assert not args.out.exists()
 contract_path=BASE/'agents/conditional_phase/Q43_QUARTER_CARRY_CASE23_CONTRACT.json'
 contract=json.loads(contract_path.read_text());assert sha(contract_path)=='2fa0a0ec726da539db940746da4e09e9e85f21ef2418b6cc433fcf6953d18d90'
 parent_path=BASE/'root/q43_first_bank_and_carry_half_v1/candidate_text.kmx';assert sha(parent_path)=='4650e2341bd19826e2c495b5a64db040b6f30f31a8d682e38bf50cd66bd5c8e5'
 source_path=BASE/'agents/temporal_merges/q43_integrated_width_base_v1/candidate_text.kmx';assert sha(source_path)==contract['integrated_native_sha256']
 source=Program(source_path.read_text());text=parent_path.read_text();parent=Program(text)
 original=[semantic(o) for o in source.operations];current=[semantic(o) for o in parent.operations]
 def anchor(cut):
  pattern=original[cut-3:cut+4]
  hits=[i+3 for i in range(len(current)-len(pattern)+1) if current[i:i+len(pattern)]==pattern]
  assert len(hits)==1,(cut,hits);return hits[0]
 paid=anchor(contract['paid_insert_cut']);free=anchor(contract['free_insert_cut'])
 assert source.operations[11616].kind=='PUSH_CONDITION' and source.operations[11616].condition=='b280'
 assert semantic(source.operations[11622])==('CCX',('q16','q1','q36'),None,None)
 plans_path=BASE/'root/q43_first_bank_and_carry_half_v1/REPORT.json';plans=json.loads(plans_path.read_text());p=next(p for p in plans['plans'] if p['case_id']==23)
 lo,hi=p['output_interval'];hits=[i for i in range(lo,hi) if semantic(parent.operations[i])==('CCZ',('q1','q2','q16'),'b1',None)]
 assert len(hits)==1;remove=hits[0];assert remove<paid<free
 # The two guards retain distinct physical, unconditional measurement births.
 depth=0;depths=[]
 for o in source.operations:
  depths.append(depth);depth+=(o.kind=='PUSH_CONDITION')-(o.kind=='POP_CONDITION')
 for record in [contract['debt_outcome'],contract['later_outcome']]:
  birth=record['birth'];op=source.operations[birth]
  assert op.kind=='HMR' and op.condition is None and depths[birth]==0 and op.arguments[1]==record['owner'] and op.event==record['event']
 fresh='b'+str(max(int(q[1:]) for q in parent.wires if q.startswith('b'))+1)
 paid_lines=[f'BIT_STORE1 {fresh}',f'BIT_INVERT {fresh} if b280','PUSH_CONDITION if b911',f'PUSH_CONDITION if {fresh}',*contract['paid_quantum_gates'],'POP_CONDITION','POP_CONDITION',f'BIT_STORE0 {fresh}']
 additions={paid:paid_lines,free:contract['free_gates']};lines=text.splitlines();oplines=operation_lines(lines);assert len(oplines)==len(parent.operations)
 by_line={line:i for i,line in enumerate(oplines)};changed=['# '+NOTICE];mapping={};count=0
 for line_no,line in enumerate(lines):
  if line_no in by_line:
   i=by_line[line_no];mapping[i]=count
   if i in additions:changed.extend(additions[i]);count+=len(additions[i])
   if i==remove:continue
   count+=1
  changed.append(line)
 changed='\n'.join(changed)+'\n';result=Program(changed);assert len(result.operations)==count and result.measurements==parent.measurements and result.registers==parent.registers
 args.out.mkdir(parents=True);dest=args.out/'candidate_text.kmx';dest.write_text(changed)
 report=dict(notice=NOTICE,status='ROOT_ANCHORED_QUARTER_CARRY_REPAIR_EMITTED_FULL_PROOF_PENDING',parent_native_sha256=sha(parent_path),candidate_native_sha256=sha(dest),parent_cost='5843/4',modelled_expected_Toffolis='2921/2',old_paid_gate_firing='1/2',new_paid_gate_firing='1/4',free_native_helper_sector='b280=1',paid_complement_sector='b911=1,b280=0',distinct_unconditional_physical_HMR_guards=True,removed_parent_operation=remove,paid_parent_cut=paid,free_parent_cut=free,paid_candidate_cut=mapping[paid],free_candidate_cut=mapping[free],fresh_classical_complement=fresh,complement_explicitly_reset=True,quantum_controls_prepared_and_unprepared=True,Q=44,T_model='1',rotation_model=34,full_native_phase_and_Q43_qualification_pending=True,bindings={str(p.relative_to(BASE)):sha(p) for p in [Path(__file__),contract_path,parent_path,source_path,plans_path]})
 (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
