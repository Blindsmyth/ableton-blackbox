# Credits & Attribution

## Original Creator

**Maximilian Karlander** (pro424 on 1010music forum)

The original codebase (`xml_read.py` v0.2) was created in March 2023 and provided the foundation for this project, specifically:

- Reverse-engineering of the 1010music Blackbox XML preset format
- Understanding of pad, sequence, and parameter mappings
- Initial sample extraction and conversion logic
- Blackbox XML generation utilities

Original forum thread: https://forum.1010music.com/forum/products/blackbox/support-blackbox/43727-python-script-converting-an-ableton-live-project-to-blackbox-xml

---

## Current Maintainer & Enhancements

**Simon Schmidt** (2025)

Extended and refactored the original codebase to:

- Add Ableton Live 12+ compatibility (tag-based XML navigation)
- Implement Drum Rack workflow (16 Simplers → 16 Blackbox pads)
- Support multi-layer sequences (A/B/C/D sub-layers)
- Add unquantised MIDI timing support
- Detect warped stems and set loop modes
- Extract choke groups from drum racks
- Improve error handling and logging
- Clean up codebase architecture

---

## License

This project maintains the original author's intent while adding significant new functionality. Please respect both contributors' work when using or modifying this code.

