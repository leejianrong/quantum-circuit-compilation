# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Interleaved six-product64-row phase cleanup, with all physical owners explicit."""
from pathlib import Path
import json
from native_loader64 import cb,plan,FULL
HERE=Path(__file__).resolve().parent

def cleanup(b,address,outputs,data,debts):
 cert=json.loads((HERE/'cleanup_bank6_interleave.json').read_text());assert cert['Toffolis']==6 and cert['loader_table_sha256']==data['table_sha256'];assert len(outputs)==len(data['output_truths'])==16
 raw=cb.word_functions(range(64),6);functions=raw+[int(t,16)for t in data['output_truths']];debts.flush(b,list(address)+list(outputs),functions)
 live=dict(enumerate(outputs));helpers=[];stack=[];peak=len(live)
 for step in cert['steps']:
  p=plan(step['plan'])
  if step['kind']=='make_helper':
   assert step['helper_index']==len(helpers);assert sorted(live)==step['live_outputs'];q=b.alloc_qubits(1)[0];cb.emit_xor(b,list(address)+helpers,q,p);helpers.append(q);stack.append((q,p))
  else:
   i=step['output_index'];q=live.pop(i);assert sorted(live)==step['remaining_outputs'] and len(helpers)==step['helper_count'];variables=list(address)+helpers+[live[j]for j in sorted(live)];cb.emit_erase(b,variables,[q],[p]);b.free(q)
  peak=max(peak,len(live)+len(helpers));assert len(live)+len(helpers)<=cert['output_helper_owner_cap']
 assert not live
 for q,p in reversed(stack):
  assert helpers.pop()==q;cb.emit_erase(b,list(address)+helpers,[q],[p]);b.free(q)
 assert not debts.pending and peak<=18
