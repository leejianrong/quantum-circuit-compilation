# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Bounded Q44 arithmetic repairs; first loader and tail remain separate."""
import sys
from root11_coefficient import inverse_low_window


def apply(ctx):
    coefficient=sys.modules['variant_patch_patch_coef2_q46']
    original=ctx.baseline.coefficient_forward
    def forward(b,*args,**kwargs):
        # Apply the same one-owner D12/H4 conversion on both passes.
        assert coefficient.STATE['converted'] is None
        coefficient.STATE['calls']=1
        return original(b,*args,**kwargs)
    ctx.baseline.coefficient_forward=forward
    module=ctx.components['coefficient'];previous=module.inverse_low6
    def inverse(b,source,target,debt,*,carry_in,top_outcome,ar,omit_wrap=False):
        if b.max_qubits-b.num_allocated_qubits>=4:
            return previous(b,source,target,debt,carry_in=carry_in,top_outcome=top_outcome,ar=ar,omit_wrap=omit_wrap)
        assert b.max_qubits-b.num_allocated_qubits>=3
        return inverse_low_window(b,source,target,debt,carry_in=carry_in,
                                  top_outcome=None if omit_wrap else top_outcome,ar=ar)
    module.inverse_low6=inverse
