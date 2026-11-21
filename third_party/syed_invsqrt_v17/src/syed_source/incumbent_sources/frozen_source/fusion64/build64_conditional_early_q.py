# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Frozen CLI for the outcome-selected quadratic row12 bank."""
from pathlib import Path
import os,sys
OWN=Path(__file__).resolve().parent
HERE=OWN.parent/'fusion'
for path in(HERE,OWN,HERE/'runtime/tools'):sys.path.insert(0,str(path))
os.environ['JOINT_DIRTY_PHASE_HELPER']=str(OWN/'third_top_phase.py')
os.environ['ROW14_COUPLED_PHASE_HELPER']=str(OWN/'row13_early_bank_retire_phase_v1.py')
os.environ['ROW14_COUPLED_PHASE_SHA256']='e39ecad78d744a1799003bedcb38aa1a6d6f1ea89ca1583072f1b3cbf30c8043'
os.environ['ROW12_EARLY_PHASE_HELPER']=str(OWN/'row12_quadratic_bank_phase_v1.py')
os.environ['ROW12_EARLY_PHASE_SHA256']='51b9a33888dda3024925dfb6b5139178be4652698e70c6128134d4d2cbddaee2'
import build_variant as bv
import row13_dirty_c10_native_v2
import conditional_early_q_native_v1
old_apply=bv.PatchSet.apply
def patched(self,ctx):
    old_apply(self,ctx)
    row13_dirty_c10_native_v2.apply(ctx)
    conditional_early_q_native_v1.apply(ctx)
bv.PatchSet.apply=patched
from build64_decoder_seven_products import main
if __name__=='__main__':main()
