# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Lazy final-table helper preparation and joint two-output HMR phase cases.

Keep the incumbent Clifford erasure prefix. The first four nonlinear helpers
are computed once, on demand, and kept until their guarded HMR cleanup.
The final two output HMR outcomes choose one of three exact one-product
phase representations, so no final helper is prepared in the zero case.
"""
from pathlib import Path
import sys,json,hashlib,os
from native_loader64 import cb,plan,FULL
HERE=Path(__file__).resolve().parent
CERT=HERE/'cleanup_bank6_interleave.json'
PHASE=HERE/'cleanup_phase_conditional_helpers.json'

def make_product(width,left,right):
 linear=left&right;edges=set()
 for i in cb.bits(left):
  for j in cb.bits(right):
   if i!=j:
    edge=tuple(sorted((i,j)))
    if edge in edges:edges.remove(edge)
    else:edges.add(edge)
 p=cb.factor_polynomial(width,False,linear,edges);assert p.and_count==1
 return p

def cleanup(b,address,outputs,data,debts):
 cert=json.loads(CERT.read_text());case=json.loads(PHASE.read_text())
 assert cert['Toffolis']==6 and cert['loader_table_sha256']==data['table_sha256']
 assert case['status']=='THREE_CONDITIONAL_SINGLE_HELPER_PHASE_CORRECTIONS'
 assert case['certificate_sha256']==hashlib.sha256(CERT.read_bytes()).hexdigest()
 raw=cb.word_functions(range(64),6);functions=raw+[int(t,16)for t in data['output_truths']]
 assert len(outputs)==16
 debts.flush(b,list(address)+list(outputs),functions)
 live=dict(enumerate(outputs));helpers=[];plans=[];active=[];helper_truths=[];rows=[]
 def ensure_prefix(count,condition):
  for i in range(count):
   b.x(active[i]);b.push_condition(active[i]);b.push_condition(condition)
   cb.emit_xor(b,list(address)+helpers[:i],helpers[i],plans[i])
   b.pop_condition();b.pop_condition();b.x(active[i])
   b.bit_store(active[i],True,control=condition)
 for step in cert['steps']:
  if step['kind']=='make_helper':
   i=step['helper_index']
   if i==4:break
   assert i==len(helpers) and sorted(live)==step['live_outputs']
   p=plan(step['plan']);assert p.and_count==1
   helpers.append(b.alloc_qubits(1)[0]);plans.append(p)
   a=b.alloc_bits(1)[0];b.bit_store(a,False);active.append(a)
   helper_truths.append(p.evaluate_functions(raw+helper_truths,FULL))
  else:
   i=step['output_index'];p=plan(step['plan']);q=live.pop(i)
   assert sorted(live)==step['remaining_outputs'] and len(helpers)==step['helper_count']
   m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q)
   ensure_prefix(len(helpers),m)
   cb.emit_phase(b,list(address)+helpers+[live[j]for j in sorted(live)],m,p);b.free(m)
   if helpers:rows.append(dict(output=i,conditional_helper_prefix=len(helpers)))
 assert sorted(live)==[11,13] and len(helpers)==4
 outcomes=[]
 for i in (13,11):
  q=live.pop(i);m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q);outcomes.append(m)
 request=b.alloc_bits(1)[0];b.bit_store(request,False)
 for m in outcomes:b.bit_store(request,True,control=m)
 ensure_prefix(4,request);b.free(request)
 variables=list(address)+helpers;values=raw+helper_truths
 output_truths=[int(t,16)for t in data['output_truths']]
 def enter(mask):
  for i,m in enumerate(outcomes):
   if not(mask>>i&1):b.x(m)
   b.push_condition(m)
 def leave(mask):
  for i in reversed(range(2)):
   b.pop_condition()
   if not(mask>>i&1):b.x(outcomes[i])
 witnesses=[]
 for item in case['witnesses']:
  mask=item['target_mask'];p=plan(item['plan']);gp=make_product(10,item['left'],item['right'])
  gt=gp.evaluate_functions(values,FULL);assert gt==int(item['helper_truth'],16)
  wanted=(output_truths[13]if mask&1 else 0)^(output_truths[11]if mask&2 else 0)
  assert p.evaluate_functions(values+[gt],FULL)==wanted
  q=b.alloc_qubits(1)[0];enter(mask);cb.emit_xor(b,variables,q,gp)
  if p.constant:b.z(True)
  for bit in cb.bits(p.linear):b.z((variables+[q])[bit])
  for i,j in p.edges:b.cz((variables+[q])[i],(variables+[q])[j])
  leave(mask)
  m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q)
  enter(mask);cb.emit_phase(b,variables,m,gp);leave(mask);b.free(m)
  witnesses.append(dict(mask=mask,helper_owner=str(q),helper_truth=hex(gt),phase_truth=hex(wanted),left=item['left'],right=item['right']))
 for m in outcomes:b.free(m)
 for i in reversed(range(4)):
  q=helpers.pop();m=b.alloc_bits(1)[0];b.hmr(q,m);b.free(q)
  b.push_condition(active[i]);cb.emit_phase(b,list(address)+helpers,m,plans[i]);b.pop_condition()
  b.free(m);b.free(active[i])
 assert not debts.pending and not live
 audit=os.environ.get('CLEANUP_CONDITIONAL_AUDIT')
 if audit:
  Path(audit).write_text(json.dumps(dict(notice=__import__('loader64').NOTICE,status='ACTUAL_CONDITIONAL_FINAL_CLEANUP_OWNER_AND_FUNCTION_AUDIT',
   raw_address_owners=list(map(str,address)),guarded_prefix_uses=rows,joint_outcome_output_indices=[13,11],witnesses=witnesses,
   four_prefix_expected_ANDs=['31/32','15/16','15/16','7/8'],three_case_expected_ANDs=['1/4','1/4','1/4'],expected_total='143/32',
   old_total=6,expected_saving='49/32',cap=b.max_qubits,exit_owners=b.num_allocated_qubits,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),certificate_sha256=hashlib.sha256(CERT.read_bytes()).hexdigest(),phase_case_sha256=hashlib.sha256(PHASE.read_bytes()).hexdigest()),indent=2)+'\n')

def apply(ctx):
 sys.modules['variant_patch_native64_q44_A10_swap'].cleanup_loader=cleanup
