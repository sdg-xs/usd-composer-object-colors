# Implementation review

The review compared the implementation with the empty-repository baseline `a382c2f`. Two independent reviewers covered standards and specification compliance. The follow-up reviews confirmed the listed fixes.

## Standards

No documented-standard violations or material maintainability smells were found. One correctness issue was identified: an open palette could submit its old group key to a new criterion or stage. Palette callbacks now validate the captured criterion and stage generation, and panel rebuilds hide the palette.

Initial findings: one correctness issue. Remaining findings: zero.

## Spec

Three findings were identified:

- A stale palette could change the wrong scheme. The callback now rejects stale input.
- Removing the HOOPS namespace from display labels could make properties indistinguishable. Labels now retain `[HOOPS]` source context.
- A broad reserved-name filter could skip legitimate geometry. Discovery now includes those user prims.

Focused regressions cover all three cases. The reviewer found no additional scope creep. The documented unsupported materials and mixed-opacity instances comply with the requirement to report unsupported structures.

Initial findings: three. Remaining findings: zero.
