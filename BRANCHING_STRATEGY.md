# Branching Strategy

## Overview

The repository uses a stable/experimental branching model to ensure reliable releases while developing new features.

## Branches

### `main` (Stable)
**Tagged as: `v1.0-stable`**

The stable, production-ready version of the converter.

**Features:**
- ✅ Drum Rack workflow with 16 pads
- ✅ **Pads Mode sequences** (trigger multiple pads from one sequence)
- ✅ Sequence length detection from MIDI clip length
- ✅ Automatic step length adjustment (default 1/16, non-triplet values only)
- ✅ Beat count calculation for clip mode samples
- ✅ Choke group mapping
- ✅ Chain order-based pad mapping
- ✅ Sample envelope extraction
- ✅ Output bus routing

**Use this branch for:**
- Production conversions
- Stable, tested functionality
- Projects that need reliable output

**Installation:**
```bash
git checkout main
# or
git checkout v1.0-stable
```

---

### `experimental/keys-midi-mode` (Experimental)
**Status: Testing**

Experimental branch with new sequence modes: Keys and MIDI.

**New Features:**
- 🆕 **Keys Mode sequences** (melodic sequences on specific pads)
- 🆕 **MIDI Mode sequences** (send MIDI to external devices)
- 🆕 Automatic sequence mode detection based on routing
- 🆕 `detect_sequence_mode()` function

**All stable features** from `main` are included.

**Use this branch for:**
- Testing Keys mode (MIDI track → specific drum rack pad)
- Testing MIDI mode (MIDI track → external MIDI device)
- Providing feedback on new features
- Experimental conversions

**Installation:**
```bash
git checkout experimental/keys-midi-mode
```

**Testing Status:**
- [x] Keys mode detection implemented
- [x] MIDI mode detection implemented
- [x] Sequence parameter handling
- [ ] Real-world testing with Keys mode projects
- [ ] Real-world testing with MIDI mode projects
- [ ] Edge case testing

---

## Workflow

### For Users

1. **Stable conversions**: Use `main` branch or `v1.0-stable` tag
2. **Testing new features**: Use `experimental/keys-midi-mode` branch
3. **Report issues**: Open GitHub issues with branch name specified

### For Development

1. **Bug fixes for stable**: Create branches from `main`
2. **New features**: Create branches from appropriate experimental branch
3. **Merging**: Experimental branches merge to `main` after thorough testing

---

## Version History

### v1.0-stable (Current Stable)
**Date**: 2025-11-04  
**Branch**: `main`  
**Commit**: `84ee622`

**What's Included:**
- Complete Pads mode implementation
- Step length fixes (non-triplet values)
- Documentation and technical reference
- Roadmap for future features

**Changelog:**
- Fix pads mode: use chan parameter (256+pad_number)
- Fix step length: only non-triplet values
- Default to 1/16 step length, scale up when needed
- Cleanup: move dev docs to docs/development/
- Add Blackbox technical reference
- Add comprehensive roadmap

---

### experimental/keys-midi-mode (Experimental)
**Date**: 2025-11-04  
**Status**: Testing  
**Based on**: `v1.0-stable`

**What's New:**
- Keys mode sequence detection and generation
- MIDI mode sequence detection and generation
- Routing pattern analysis
- Mode-specific parameter handling

**Known Limitations:**
- Requires testing with real projects
- May need routing pattern refinements
- MIDI channel extraction may need adjustment

---

## Feature Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for detailed feature plans.

### Next Experimental Branches (Planned)

1. **`experimental/unquantised`** - Unquantised sequence detection
2. **`experimental/triplets`** - Intelligent step length (triplets, 1/32 notes)
3. **`experimental/song-mode`** - Arrangement view extraction

---

## Switching Between Branches

### To use stable version:
```bash
git checkout main
python3 code/xml_read_v2.py -i project.als -o output/
```

### To test Keys/MIDI mode:
```bash
git checkout experimental/keys-midi-mode
python3 code/xml_read_v2.py -i project.als -o output/
```

### To go back to stable:
```bash
git checkout main
```

---

## Testing Guidelines

### For Experimental Branches

1. **Compare output**: Always compare experimental output with stable output
2. **Test incrementally**: Start with simple projects, then complex ones
3. **Report issues**: Include branch name, project details, and expected vs actual behavior
4. **Backup originals**: Keep original Ableton projects safe

### Example Test Workflow

```bash
# Test with stable version first
git checkout main
python3 code/xml_read_v2.py -i test.als -o stable_output/

# Test with experimental version
git checkout experimental/keys-midi-mode
python3 code/xml_read_v2.py -i test.als -o experimental_output/

# Compare outputs
diff -r stable_output/ experimental_output/
```

---

## Contributing

### Reporting Issues
- Include branch name in issue title: `[experimental/keys-midi-mode] Issue description`
- Specify Ableton Live version
- Include relevant routing configuration
- Attach sample project if possible

### Submitting Improvements
1. Fork the repository
2. Create feature branch from appropriate base branch
3. Make changes and test thoroughly
4. Submit pull request with clear description

---

## Support

- **Stable branch issues**: High priority, will be fixed quickly
- **Experimental branch issues**: Expected, help us improve!
- **Feature requests**: Add to roadmap discussion

---

*Last Updated: 2025-11-04*  
*Current Stable: v1.0-stable*  
*Current Experimental: experimental/keys-midi-mode*

