# Conversion Comparison: Generated vs Corrected

## Issues Found

### 1. ✅ Output Bus
**Problem**: Samples routed to wrong output
- **Generated**: `outputbus="1"` (Output 2)
- **Corrected**: `outputbus="0"` (Main Output)
- **Fix**: Change default output bus to 0

### 2. ❌ Choke Groups
**Problem**: Choke groups not extracted/applied
- **Generated**: All pads have `chokegrp="0"`
- **Corrected**: Some pads have `chokegrp="4"` (E Melos samples on row 1)
- **Fix**: Need to extract choke group info from Ableton drum rack

### 3. ❌ Sample Length (samlen)
**Problem**: Sample length not set
- **Generated**: `samlen="0"` for all pads
- **Corrected**: Actual sample lengths in samples:
  - Kick: `samlen="22315"` (463ms)
  - E Melos-2 [210306]: `samlen="699769"` (14.5s)
  - E Melos-2 [210309]: `samlen="3498844"` (72.8s)
  - E Melos-2 [210312]: `samlen="10496530"` (218.2s)
  - Percussion [193414]: `samlen="761653"` (15.8s)
  - 27-Audio: `samlen="108288"` (2.25s)
- **Fix**: Calculate actual sample length from WAV file

### 4. ❌ Beat Count (Clip Length)
**Problem**: Beat count calculations are way off
- **Pad 1 (Percussion loop)**:
  - Generated: `beatcount="128"` ✅ CORRECT
  - Corrected: `beatcount="128"` 
- **Pad 2 (27-Audio)**:
  - Generated: `beatcount="12"` ✅ CORRECT
  - Corrected: `beatcount="12"`, BUT `cellmode="0"` (not clip mode!)
- **Pad 4 (E Melos [210306])**:
  - Generated: `beatcount="116"` ❌ WRONG
  - Corrected: `beatcount="32"` 
- **Pad 5 (E Melos [210309])**:
  - Generated: `beatcount="588"` ❌ WRONG
  - Corrected: `beatcount="160"` 
- **Pad 6 (E Melos [210312])**:
  - Generated: `beatcount="1764"` ❌ WRONG
  - Corrected: `beatcount="480"` 
- **Fix**: Extract loop length from Ableton Simpler's loop settings, not from file duration

### 5. ✅ Sequence Mode (Keys vs Pads)
**Status**: Need to verify
- **Generated**: `seqpadmapdest="0"`
- **Corrected**: `seqpadmapdest="0"` 
- **Note**: Both use same value - user reported sequences in "keys mode", need to check what value enables "pads mode"

### 6. ❌ Pad 2 Sample Confusion
**Problem**: Hat sample not in clip mode
- **Pad 2 (27-Audio 0001)**:
  - Generated: `cellmode="1"` (clip mode)
  - Corrected: `cellmode="0"` (sampler mode with loop enabled)
- **Fix**: Don't force clip mode on all long samples - check if sample has loop points or warp markers

## Pad Layout Comparison

### Generated Layout (Row-major, 7 pads):
```
[Pad 0] [Pad 1] [Pad 2] [Pad 3]
[Pad 4] [Pad 5] [Pad 6] [Empty]
```

### Corrected Layout (Actually 7 pads):
```
[Pad 0] [Pad 1] [Pad 2] [Pad 3]
[Pad 4] [Pad 5] [Pad 6] [Empty]
```

Both are the same! Files are correct.

## Key Parameters to Extract from Ableton

1. **Choke Group** (`Send` chains in Drum Rack)
2. **Loop Length** (Simpler's loop end point, not file duration)
3. **Sample Length** (Read from WAV file header)
4. **Loop Enabled** vs **Clip Mode** (Check for warp markers vs static loops)

## Next Steps

1. Fix output bus (easy - change 1 → 0)
2. Add WAV file reader to get actual sample length
3. Extract loop end point from Simpler parameters
4. Extract choke group from Drum Rack chain structure
5. Improve clip mode detection heuristic

