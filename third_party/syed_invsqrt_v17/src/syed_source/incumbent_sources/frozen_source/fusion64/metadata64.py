# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Exact quadratic recoverability screen for64-row coefficient metadata."""
import argparse,json,sys,hashlib
from pathlib import Path
import numpy as np
from loader64 import cb,serialize,NOTICE

def truth(values):return sum(int(x)<<i for i,x in enumerate(values))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--table',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();table=json.loads(a.table.read_text());bits=table['coefficient_storage_bits'];v=np.arange(4096,dtype=np.int64);address=v>>6;S=np.asarray(table['S'],np.int64)[address];A=np.asarray(table['A'],np.int64)[address];D=np.asarray(table['stored_coefficient'],np.int64);rows=[]
 for source,name in [(A,'initial'),(D,'current')]:
  labels=[f'C{i}'for i in range(bits-6,bits)]+[f'S{i}'for i in range(bits-8)]+['v10','v11']
  values=[(source>>i)&1 for i in range(bits-6,bits)]+[(S>>i)&1 for i in range(bits-8)]+[(v>>i)&1 for i in (10,11)];funcs=[truth(x)for x in values]
  for target in range(bits-8,bits-6):
   wanted=truth((S>>target)&1);book=cb.Codebook(funcs,4096);p=book.represent(wanted,trials=128,seed=target+11)
   if p:p=book.improve_preserving_kernel(p,rounds=32,subspace_bits=7,seed=target+11)
   row=dict(stage=name,target=f'S{target}',labels=list(labels),representable=p is not None,Toffolis=p.and_count if p else None,plan=serialize(p)if p else None);rows.append(row)
   if p:labels.append(f'S{target}');funcs.append(wanted)
  for target in (9,10,11):
   labels2=[f'C{i}'for i in range(bits-6,bits)]+[f'v{i}'for i in (9,10,11)if i!=target]
   fs=[truth((source>>i)&1)for i in range(bits-6,bits)]+[truth((v>>i)&1)for i in (9,10,11)if i!=target]
   wanted=truth((v>>target)&1);book=cb.Codebook(fs,4096);p=book.represent(wanted,trials=128,seed=target+11)
   if p:p=book.improve_preserving_kernel(p,rounds=32,subspace_bits=7,seed=target+11)
   rows.append(dict(stage=name,target=f'v{target}',labels=labels2,representable=p is not None,Toffolis=p.and_count if p else None,plan=serialize(p)if p else None))
 report=dict(notice=NOTICE,status='EXACT4096_ROOT_METADATA_QUADRATIC_SCREEN_NOT_NATIVE',table=str(a.table),table_sha256=hashlib.sha256(a.table.read_bytes()).hexdigest(),rows=rows);a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps([{k:v for k,v in r.items()if k not in ('labels','plan')}for r in rows],indent=2))
if __name__=='__main__':main()
