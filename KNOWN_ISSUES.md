# Known Issues and Limitations

## Date: November 3, 2025

---

## 1. Pad Mapping - Chain Order vs MIDI Note Mapping

### Issue
The converter currently uses **chain order** to determine Blackbox pad positions, NOT the MIDI "Receive Play" notes shown in the Ableton UI.

### Background
- Ableton's Drum Rack has two separate concepts:
  - **Chain Order**: The order chains appear in the chain list (right side)
  - **Pad Grid Position**: The visual 4x4 pad layout (bottom of Drum Rack)
- In the Ableton UI, the "Receive Play" column shows MIDI notes (C1=36, C#1=37, etc.)
- These MIDI notes should determine pad position (C1→Pad 12, C#1→Pad 13, etc.)

### What We Found
- In the XML file, `ReceivingNote` values are stored, but they don't match the UI
  - UI shows: C1, C#1, D1, D#1 (MIDI 36-39)
  - XML shows: MIDI 86-92 (completely different range)
- We also found `PadScrollPosition` but couldn't determine the correct formula
- The actual pad position doesn't seem to be directly stored in the XML

### Current Behavior
**The converter maps: Chain 0 → Pad 0, Chain 1 → Pad 1, Chain 2 → Pad 2, etc.**

This means if your chains are in a different order than your pad layout, the samples will be on the wrong pads in the Blackbox.

### Workaround for Users
**Before converting your Ableton project:**
1. Open your Drum Rack
2. Arrange the **chains** (in the chain list on the right) to match your desired pad order:
   - Chain 0 = Pad 0 (top-left)
   - Chain 1 = Pad 1
   - Chain 2 = Pad 2
   - Chain 3 = Pad 3
   - Chain 4 = Pad 4 (second row, left)
   - ... and so on
3. Save your project
4. Run the converter

### Blackbox Pad Layout (0-indexed)
```
Row 0 (top):     0   1   2   3
Row 1:           4   5   6   7
Row 2:           8   9  10  11
Row 3 (bottom): 12  13  14  15
```

### Future Work Needed
- Investigate if there's a different XML structure in newer/older Ableton versions
- Try to find the actual formula that maps ReceivingNote + PadScrollPosition → Pad Position
- Consider adding a manual pad mapping configuration option

---

## 2. MIDI Sequence Notes (RESOLVED)

### Issue
~~All MIDI sequence notes were being set to 0 (C) instead of preserving the actual MIDI notes from Ableton.~~

### Status: **FIXED**
The converter now correctly extracts and preserves the actual MIDI note values from Ableton sequences.

---

## 3. Sample Rate and Beat Count Calculation

### Status: **WORKING**
- Beat counts are calculated from sample duration and project tempo
- This matches what Ableton displays in the Simpler UI ("bars" parameter)
- WAV file headers are read to get accurate sample lengths

### Note
Beat count calculation is accurate when samples are NOT time-stretched or warped. For warped samples, the calculation uses the original sample duration, not the warped duration.

---

## 4. Choke Groups

### Status: **WORKING PERFECTLY**
- Choke groups are correctly extracted from `BranchInfo/ChokeGroup`
- Mapping: Ableton 0 → Blackbox 0 (none), Ableton 1-4 → Blackbox 1-4 (A-D)

---

## 5. Other Working Features
- ✅ Sample file copying and path resolution
- ✅ Loop start/end extraction
- ✅ Clip mode vs sampler mode detection
- ✅ MIDI sequence extraction with multiple sub-layers
- ✅ Tempo extraction
- ✅ Envelope parameter extraction
- ✅ Output bus routing (set to main output/0)
- ✅ Sample length from WAV file headers

---

## Summary for Users

### What Works Well
- Sample extraction
- Beat counts and loop settings
- Choke groups
- MIDI sequences
- Most Simpler parameters

### What Requires Manual Work
- **Pad order**: Arrange your chains in the correct order BEFORE converting
- Time-stretched samples: Beat counts may not account for warping

### Recommended Workflow
1. Set up your Drum Rack with chains in the desired pad order
2. Ensure samples have proper loop settings if needed
3. Save your Ableton project
4. Run the converter
5. Test the resulting preset on Blackbox
6. Make minor tweaks as needed

