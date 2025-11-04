# Known Issues - Experimental Branch

## Current Testing: An mir Vorbei test unquantised

### Issue 1: Keys Mode Destination Detection ❌
**Status**: Needs Fix  
**Severity**: High

**Problem**:
- Keys mode sequence is assigned to wrong pad
- Detection extracts chain index from routing (e.g., `DeviceIn.0`)
- But this doesn't account for custom MIDI note mappings in the drum rack

**Details**:
- User expects sequence to target Pad 8
- Current code detects `DeviceIn.0` → assigns to Pad 0
- Drum rack has custom MIDI mappings (notes 77-92 instead of standard 36-51)
- Sequence plays MIDI note 48, which doesn't match any drum rack pad

**Possible Solutions**:
1. **Option A**: Analyze MIDI notes in sequence to determine target pad
   - Check which notes are most common in the sequence
   - Map those notes to drum rack pads based on ReceivingNote
   
2. **Option B**: Use first MIDI note in sequence to determine pad
   - Take first note (e.g., 48) and find which pad responds to it
   - If no pad found, default to chain index
   
3. **Option C**: Manual override flag
   - Add `--keys-pad-mapping` option
   - Let user specify which sequences target which pads

**Recommended**: Option B (use first MIDI note to find target pad)

---

### Issue 2: Pad 8 Clip Mode Incorrectly Enabled ❌
**Status**: Needs Investigation  
**Severity**: Medium

**Problem**:
- Pad 8 has unwarped sample but is set to clip mode
- Current settings: `cellmode=1, loopmode=1, beatcount=32`
- Should be: `cellmode=0` (one-shot/sample mode)

**Details**:
- File: `An Mir Vorbei C Bass [2025-11-02 204842].wav`
- Warp detection may be incorrectly identifying it as warped
- Need to check `detect_warped_stem()` function logic

**Investigation Needed**:
- Check if sample has warp markers in Ableton XML
- Verify `WarpOn` parameter extraction
- Check beat count calculation triggering clip mode

**Workaround**:
- Manually edit `cellmode="0"` in preset.xml for pad 8

---

### Issue 3: Unquantised Sequence Timing 4x Too Slow ❌
**Status**: Critical Bug  
**Severity**: High

**Problem**:
- Unquantised sequences play at 1/4 speed
- Only first quarter of sequence plays before loop
- Timing calculations appear correct but Blackbox interprets differently

**Details**:
- Step length: `notesteplen=10` (1/16) ✓ Correct
- Step count: `notestepcount=64` ✓ Correct
- Example timing:
  - Ableton: Time=0.632 beats
  - Calculated: strtks=2427 (0.632 × 3840)
  - Expected: This should be correct for firmware 2.3+
  - Actual: Plays 4x slower than expected

**Possible Causes**:
1. **Tick rate mismatch**: Blackbox expecting different ticks-per-beat
   - Current: 3840 ticks/beat
   - Maybe needs: 960 ticks/beat for 1/16 step length?
   
2. **Step length interpretation**: notesteplen=10 might need different tick calculation
   - Maybe ticks should be relative to step length, not absolute
   
3. **Unquantised mode flag**: Maybe unquantised mode needs special handling
   - Current code doesn't change tick calculation based on unquantised flag
   
4. **Tempo scaling**: Maybe ticks need to be scaled by tempo (121 BPM)

**Debug Information**:
```
Ableton MIDI clip note times:
  Note 0: Time=0 beats → step=0, strtks=0
  Note 1: Time=0.632 beats → step=2, strtks=2427
  Note 2: Time=4 beats → step=16, strtks=15360

Current calculation:
  step = int(time_val * 4)  # 4 steps per beat (1/16 resolution)
  strtks = int(time_val * 3840)  # 3840 ticks per beat

If 4x too slow, maybe should be:
  strtks = int(time_val * 3840 / 4)  # Divide by 4?
  OR
  strtks = int(time_val * 960)  # Use 960 ticks per 1/16?
```

**Testing Needed**:
1. Try dividing strtks by 4: `strtks = int(time_val * 960)`
2. Check if step calculation also needs adjustment
3. Test with different step lengths
4. Compare with working Pads mode sequences

---

## Testing Plan

### Test 1: Fix Keys Mode Destination
```python
# In detect_sequence_mode or make_drum_rack_sequences
# After detecting Keys mode, analyze MIDI notes to find actual target pad

if seq_mode == 'Keys':
    # Extract first MIDI note from clip
    first_note = extract_first_midi_note(midi_clip)
    # Find which pad responds to this note
    for pad_idx, pad in enumerate(pad_list):
        if pad['midi_note'] == first_note:
            target_pad = pad_idx
            break
```

### Test 2: Fix Unquantised Timing
```python
# Try dividing ticks by 4 for unquantised mode
if unquantised:
    strtks = int(time_val * 960)  # Instead of 3840
else:
    strtks = int(time_val * 3840)
```

### Test 3: Fix Pad 8 Clip Mode
```python
# In detect_warped_stem, add more thorough warp checking
# Only set clip mode if explicitly warped AND has valid beat count
```

---

## Priority

1. **Critical**: Fix unquantised timing (Issue #3)
2. **High**: Fix Keys mode destination (Issue #1)
3. **Medium**: Fix pad 8 clip mode (Issue #2)

---

## Next Steps

1. Implement timing fix and test
2. Implement Keys mode pad detection improvement
3. Review warp detection logic
4. Test with updated code
5. Get user feedback on fixes

---

*Last Updated: 2025-11-04*  
*Testing Project: An mir Vorbei test unquantised*  
*Branch: experimental/keys-midi-mode*

