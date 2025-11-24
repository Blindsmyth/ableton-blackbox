#!/bin/bash
# Example usage scripts for Ableton to Blackbox converter

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Ableton to Blackbox Converter - Example Usage ===${NC}\n"

# Set base directory (adjust this to your setup)
BASE_DIR="/Users/simon/Dropbox/Blackbox Stuff"
SCRIPT_DIR="$BASE_DIR/ableton_blackbox/code"
PROJECTS_DIR="$BASE_DIR/Ableton Files"

# Example 1: Convert "An mir Vorbei" project
echo -e "${YELLOW}Example 1: Converting 'An mir Vorbei' (Ableton 12 project)${NC}"
echo "Command:"
echo "python3 xml_read.py \\"
echo "  -i \"$PROJECTS_DIR/An mir Vorbei Project/An mir Vorbei.als\" \\"
echo "  -o \"$BASE_DIR/ableton_blackbox/data/An_mir_Vorbei_BB\" \\"
echo "  -m"
echo ""

# Uncomment to actually run:
# cd "$SCRIPT_DIR"
# python3 xml_read.py -i "$PROJECTS_DIR/An mir Vorbei Project/An mir Vorbei.als" -o "$BASE_DIR/ableton_blackbox/data/An_mir_Vorbei_BB" -m

# Example 2: Convert "Hack Into Your Soul" project
echo -e "${YELLOW}Example 2: Converting 'Hack Into Your Soul' (Ableton 11 project)${NC}"
echo "Command:"
echo "python3 xml_read.py \\"
echo "  -i \"$PROJECTS_DIR/Hack Into Your Soul/Hack into Your Soul Blackbox Export Project/Hack into Your Soul Blackbox Export.als\" \\"
echo "  -o \"$BASE_DIR/ableton_blackbox/data/Hack_Into_Your_Soul_BB\" \\"
echo "  -m"
echo ""

# Uncomment to actually run:
# cd "$SCRIPT_DIR"
# python3 xml_read.py -i "$PROJECTS_DIR/Hack Into Your Soul/Hack into Your Soul Blackbox Export Project/Hack into Your Soul Blackbox Export.als" -o "$BASE_DIR/ableton_blackbox/data/Hack_Into_Your_Soul_BB" -m

# Example 3: Convert with verbose output for debugging
echo -e "${YELLOW}Example 3: Verbose mode for debugging${NC}"
echo "Command:"
echo "python3 xml_read.py \\"
echo "  -i \"$PROJECTS_DIR/An mir Vorbei Project/An mir Vorbei.als\" \\"
echo "  -o \"$BASE_DIR/ableton_blackbox/data/An_mir_Vorbei_BB_verbose\" \\"
echo "  -m -v 2>&1 | tee conversion_log.txt"
echo ""
echo "This saves the output to conversion_log.txt for review"
echo ""

# Example 4: Batch convert multiple projects
echo -e "${YELLOW}Example 4: Batch convert multiple projects${NC}"
echo "#!/bin/bash"
echo "for project in \"$PROJECTS_DIR\"/*.als; do"
echo "    name=\$(basename \"\$project\" .als)"
echo "    echo \"Converting: \$name\""
echo "    python3 xml_read.py -i \"\$project\" -o \"$BASE_DIR/ableton_blackbox/data/BB_\$name\" -m"
echo "done"
echo ""

# Example 5: Compare original vs new script
echo -e "${YELLOW}Example 5: Compare v0.2 (original) vs v0.3 (enhanced)${NC}"
echo "# Try original script (will likely fail on Live 12):"
echo "python3 xml_read.py -i \"project.als\" -o \"output_v2\" -m"
echo ""
echo "# Try enhanced script (should work):"
echo "python3 xml_read.py -i \"project.als\" -o \"output_v3\" -m"
echo ""

# Example 6: Test with one of the Blackbox presets that were converted
echo -e "${YELLOW}Example 6: Analyze an existing Blackbox preset${NC}"
echo "Command:"
echo "python3 -c \"
import xml.etree.ElementTree as ET
tree = ET.parse('$BASE_DIR/Blackbox Backup/Presets/LONGING/preset.als')
root = tree.getroot()
print('Preset structure:', root.tag)
for child in list(root)[:5]:
    print(' -', child.tag, child.attrib)
\""
echo ""

echo -e "${GREEN}=== End of Examples ===${NC}"
echo ""
echo "To run any example:"
echo "1. Uncomment the command in this script, or"
echo "2. Copy the command and run it in your terminal"
echo ""
echo "Happy converting! 🎵"


