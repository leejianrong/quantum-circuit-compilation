# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
"""Repay one cubic across its native majority operation on the same data target."""
from itertools import product

def cut(text):
    start=text.index('BIT_STORE0 b8003\nBIT_INVERT b8003 if b170\nBIT_INVERT b8003 if b360')
    end=text.index('POP_CONDITION\nBIT_STORE0 b203',start)
    s=text[start:end]
    assert s.count('CCZ q21 q30 q7\n')==1 and s.count('CCX q21 q30 q7\n')==1
    s=s.replace('CCZ q21 q30 q7\n','')
    a,b,t='q21','q30','q7'
    repay=['PUSH_CONDITION if b8003',f'Z_POW {a} 1.75',f'Z_POW {b} 1.75',f'CX {a} {b}',f'Z_POW {b} 0.25',f'CX {a} {b}',f'Z_POW {t} 1.5','POP_CONDITION',f'CCX {a} {b} {t}',f'Z_POW {t} 0.5 if b8003']
    s=s.replace('CCX q21 q30 q7\n','\n'.join(repay)+'\n')
    for a,b,t in product(range(2),repeat=3):
        assert ((7*a+7*b+(a^b)+6*t+2*(t^(a*b)))%8)==4*a*b*t
    return text[:start]+s+text[end:]
