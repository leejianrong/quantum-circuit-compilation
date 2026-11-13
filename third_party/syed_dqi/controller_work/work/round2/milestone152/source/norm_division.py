# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""Stable-target division sessions with 18 scratch qubits and explicit phases."""
from tower_inverse import (quadratic_basis,apply_inplace_linear,init_norm,erase_norm,
                           xor_product,phase_product,kernel)
from projective_carry import power_rows
from sized_field130 import difference_cache
from scalar_inverse_phase import phase_inverse_six

class DivisionSession:
    def __init__(self,builder,beta):
        assert len(beta)==12
        self.builder=builder;self.beta=beta;self.targets=[];self.closed=False
        self.info=quadratic_basis(12)
        norm=self.make_norm()
        self.inverse=difference_cache(builder,norm)
        builder.cx(norm,self.inverse)
        self.erase_norm(norm)

    def make_norm(self):
        b=self.builder;beta=self.beta;info=self.info
        apply_inplace_linear(b,beta,info['to_tower'])
        norm=init_norm(b,beta[:6],beta[6:],info['delta'])
        apply_inplace_linear(b,beta,info['from_tower'])
        return norm

    def erase_norm(self,norm):
        b=self.builder;beta=self.beta;info=self.info
        apply_inplace_linear(b,beta,info['to_tower'])
        erase_norm(b,beta[:6],beta[6:],norm,info['delta']);b.free(norm)
        apply_inplace_linear(b,beta,info['from_tower'])

    def quotient(self,word):
        assert not self.closed and len(word)==12
        assert not any(set(word)&set(old) for old,_ in self.targets)
        assert not set(word)&set(self.beta)
        b=self.builder;temporary=b.alloc_qubits(12)
        apply_inplace_linear(b,self.beta,power_rows(64))
        xor_product(b,word,self.beta,temporary)
        apply_inplace_linear(b,self.beta,power_rows(64))
        b.swap(word,temporary)
        old=b.alloc_bits(12);b.hmr(temporary,old);b.free(temporary)
        apply_inplace_linear(b,word,self.info['to_tower'])
        small=b.alloc_qubits(6);masks=[]
        for half in (word[:6],word[6:]):
            xor_product(b,half,self.inverse,small);b.swap(half,small)
            mask=b.alloc_bits(6);b.hmr(small,mask);masks.append(mask)
        b.free(small)
        apply_inplace_linear(b,word,self.info['from_tower'])
        phase_product(b,word,self.beta,old,kernel(12));b.free(old)
        self.targets.append((word,masks))

    def close(self):
        assert not self.closed
        b=self.builder;info6=quadratic_basis(6)
        apply_inplace_linear(b,self.inverse,info6['to_tower'])
        inverse_mask=b.alloc_bits(6);b.hmr(self.inverse,inverse_mask);b.free(self.inverse)
        norm=self.make_norm()
        for word,masks in self.targets:
            apply_inplace_linear(b,word,self.info['to_tower'])
            for half,mask in zip((word[:6],word[6:]),masks):
                phase_product(b,half,norm,mask,kernel(6));b.free(mask)
            apply_inplace_linear(b,word,self.info['from_tower'])
        phase_inverse_six(b,norm,inverse_mask);b.free(inverse_mask)
        self.erase_norm(norm);self.closed=True

def divide(builder,words,beta):
    session=DivisionSession(builder,beta)
    for word in words:session.quotient(word)
    session.close()

def dependent(builder,alpha,high,beta,neighbor):
    assert all(len(w)==12 for w in (alpha,high,beta,neighbor))
    assert len(set(q for w in (alpha,high,beta,neighbor) for q in w))==48
    session=DivisionSession(builder,beta)
    session.quotient(alpha)
    xor_product(builder,neighbor,alpha,high)
    session.quotient(high)
    session.close()

def model(k):
    assert k>=1
    return dict(T=54+72*k,expected_T=54+72*k-4/64,scratch=18)
