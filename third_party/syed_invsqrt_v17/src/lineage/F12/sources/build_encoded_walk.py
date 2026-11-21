# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Emit an integer-weight reflection circuit with a reversible change of exponent coordinates."""
from build_walk_joint import JointWalk,main

class EncodedWalk(JointWalk):
    def make(self):
        path=self.plan.get('code_path',[])
        for code in path:self.shear(code)
        prefix=self.lines
        self.lines=[]
        self.plan['price']-=2*len(path)
        super().make_helpers()
        self.plan['price']+=2*len(path)
        assert self.lines.pop()=='CZ q23 q25'
        self.lines=prefix+self.lines
        for code in reversed(path):self.shear(code)
        self.emit('CZ q23 q25')
        assert sum(v.split()[0]in ('CCX','CCZ','CSWAP')for v in self.lines)==self.plan['price']
        return self.lines

if __name__=='__main__':main(EncodedWalk)
