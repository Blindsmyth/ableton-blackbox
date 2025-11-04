# Known Issues - Experimental Branch

## Current Testing: An mir Vorbei test unquantised

### Summary of All Fixes
- ✅ **Issue #1 FIXED**: Keys mode now correctly maps via Branch Id
- ✅ **Issue #2 FIXED**: Pad 8 now in sampler mode (not clip mode)
- ✅ **Issue #3 FIXED**: Timing now correct for all sequence modes
- ✅ **Issue #4 FIXED**: Tick rate based on sequence mode (Pads vs Keys/MIDI)

---

### Issue 1: Keys Mode Destination Detection ⚠️
**Status**: Partially Fixed  
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

**Attempted Fix (Partial)**:
- Added `extract_first_midi_note_from_track()` function
- Improved sequence generation to map MIDI notes to pads
- Commit: dab9bf3

**Current Issue**:
- MIDI notes not being populated in `pad_list` during drum rack extraction
- Warning: "No MIDI notes found in pad_list, using standard mapping (36-51 → 0-15)"
- Need to debug why `ReceivingNote` values aren't being stored in pad_info

**Next Steps**:
1. Debug drum_rack_extract to ensure midi_note is properly extracted
2. Verify ReceivingNote values are being read from XML
3. Test with updated pad_list that includes MIDI notes

---

### Issue 2: Pad 8 Clip Mode Incorrectly Enabled ✅
**Status**: FIXED  
**Severity**: Medium (was)

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

**Fix Applied**:
- Modified `make_drum_rack_pads()` to only enable clip mode for explicitly warped samples
- Checks `warp_info['is_warped']` before enabling clip mode
- Unwarped samples now stay in sampler mode regardless of length
- Commit: 72bd680

---

### Issue 3: Unquantised Sequence Timing 4x Too Slow ✅
**Status**: FIXED  
**Severity**: High (was)

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

**Fix Applied**:
- Modified tick calculation for unquantised mode
- Changed from 3840 ticks/beat to 960 ticks/beat when `--unquantised` flag is set
- Verified: Event at 0.632 beats now has strtks=606 (was 2427)
- Ratio: 4.0x reduction (exactly as needed)
- Commit: 9f69431

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

## Completed Fixes

1. ✅ **Issue #3**: Unquantised timing (Commit: 9f69431)
2. ✅ **Issue #2**: Pad 8 clip mode (Commit: 72bd680)

## Remaining Work

1. ⚠️ **Issue #1**: Keys mode destination detection (Partial fix: dab9bf3)

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

