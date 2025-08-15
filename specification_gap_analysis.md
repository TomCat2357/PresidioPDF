# Specification Gap Analysis Report

## Executive Summary

This analysis identifies specific gaps between the current implementation in `src/cli/read_main.py`, `src/cli/detect_main.py`, and `src/cli/duplicate_main.py` and the new specification requirements defined in `#仕様.txt`.

## 1. JSON Format Analysis

### Current Implementation vs Required Format

#### Read Module (`read_main.py`)

**Current Output Format:**
```json
{
  "metadata": {"pdf": {...}, "generated_at": "..."},
  "text": {
    "structured": {"pages": [...]},  // Complex nested structure
    "plain": ["block1", "block2", ...]  // Array of block texts
  },
  "detect": {"structured": [...]}
}
```

**Required Output Format (per #仕様.txt):**
```json
{
  "metadata": {...},
  "text": [["xxxx","yyyyyyyy"], ["zzzz","aaa",...], ....],  // 2D array format
  "detect": [
    {
      "start": {"page_num": 0, "block_num": 0, "offset": 0},
      "end": {"page_num": 0, "block_num": 0, "offset": 3},
      "entity": "PERSON",
      "word": "田中守男"
    }
  ],
  "offset2coordsMap": {...},
  "coords2offsetMap": {...}
}
```

**Gaps:**
1. **Text format**: Current uses `{"plain": [...], "structured": {...}}` but required is flat 2D array `[[...], [...]]`
2. **Detect format**: Current has structured format, required has flat array with start/end objects
3. **Missing coordinate maps**: No `offset2coordsMap` and `coords2offsetMap` in current output
4. **Structured text**: Current still outputs structured text, but spec says to remove it (廃止する)

#### Detect Module (`detect_main.py`)

**Current Output Format:**
```json
{
  "metadata": {...},
  "detect": {
    "plain": [...],
    "structured": [...]
  }
}
```

**Required Output Format:**
```json
{
  "metadata": {...},
  "detect": [...],  // Flat array with start/end position objects
  "offset2coordsMap": {...},
  "coords2offsetMap": {...}
}
```

**Gaps:**
1. **Detect structure**: Current uses `{"plain": [...], "structured": [...]}` but required is flat array
2. **Missing coordinate maps**: No coordinate mapping data
3. **Position format**: Current detection format lacks start/end position objects

## 2. CLI Options Analysis

### Current Options vs Required Options

#### Read Module Options

**Current Options:**
```bash
--with-highlights/--no-highlights (default=True)
--with-plain/--no-plain (default=True)
--with-structured/--no-structured (default=True)
```

**Required Options (per #仕様.txt):**
```bash
--with-map/--no-map (default=--with-map)
--with-highlights/--no-highlights
```

**Gaps:**
1. **Missing --with-map/--no-map**: No coordinate map handling options
2. **Unnecessary structured options**: --with-structured should be removed per spec
3. **Plain text handling**: --with-plain may need adjustment for 2D array format

#### Detect Module Options

**Current Options:**
```bash
--highlights-merge (append/replace)
```

**Required Options (per #仕様.txt):**
```bash
--with-predetect/--no-predetect (formerly --add-highlights)
```

**Gaps:**
1. **Option name change**: `--highlights-merge` should be `--with-predetect/--no-predetect`
2. **Logic change**: Current "append/replace" logic differs from spec's add/don't add logic

## 3. Coordinate Mapping Format Analysis

### Current Implementation

The codebase has coordinate mapping infrastructure in:
- `src/pdf/pdf_coordinate_mapper.py` - Complex embedding system
- `src/pdf/pdf_locator.py` - Character-level coordinate tracking
- `src/pdf/pdf_block_mapper.py` - Block-based coordinate mapping

**Current coordinate structures:**
- Complex nested objects with detailed metadata
- Character-level precision with bbox information
- Multiple mapping strategies (page-based, block-based, global)

### Required Format (per #仕様.txt)

**offset2coordsMap:**
```json
{
  "page_num": {
    "block_num": [
      [x0, y0, x1, y1],
      [x0, y0, x1, y1],
      ...
    ]
  }
}
```

**coords2offsetMap:**
```json
{
  "(x0,y0,x1,y1)": "(page_num,block_num,offset)",
  ...
}
```

**Gaps:**
1. **Format mismatch**: Current uses complex objects, required uses simple numeric arrays
2. **Key format**: Current uses integer keys, required uses string tuple keys for coords2offset
3. **Coordinate precision**: Need to match exact format specified
4. **Integration**: Maps not integrated into JSON output

## 4. PDF Embedding Analysis

### Current Implementation

`src/pdf/pdf_coordinate_mapper.py` has sophisticated embedding system:
- Embeds JSON data as attached files in PDF
- Complex metadata management
- Full coordinate mapping structure

### Required Implementation (per #仕様.txt)

- Embed `offset2coordsMap` and `coords2offsetMap` in PDF
- Simple format matching specification
- Integration with read/detect workflow

**Gaps:**
1. **Data format**: Current embeds complex structures, need simple maps
2. **Integration**: Not integrated with CLI workflow
3. **Map generation**: Need to generate maps in required format

## 5. Text Management Analysis

### Current Implementation

**read_main.py line 109-116:**
```python
if with_structured:
    structured = _structured_from_pdf(pdf)
    text_obj["structured"] = structured
    if with_plain:
        text_obj["plain"] = _blocks_plain_text(structured)
```

**_blocks_plain_text function (line 64-74):**
- Returns `List[str]` (1D array of block texts)
- Extracts from structured text

### Required Implementation

**Per #仕様.txt:**
- Remove structured_text reading (廃止する)
- Output 2D array format: `[["xxxx","yyyyyyyy"], ["zzzz","aaa",...], ....]`
- Plain text based management

**Gaps:**
1. **Remove structured**: Line 109-116 should remove structured text handling
2. **Change text format**: Modify `_blocks_plain_text` to return 2D array
3. **Coordinate integration**: Need to build coordinate maps alongside text extraction

## 6. Specific Code Locations Requiring Modification

### read_main.py
1. **Lines 88-96**: Modify click options to add --with-map/--no-map, remove --with-structured
2. **Lines 105-125**: Complete rewrite of output generation logic
3. **Lines 64-74**: Modify `_blocks_plain_text` to return 2D array format
4. **Lines 39-61**: Remove `_structured_from_pdf` or make conditional
5. **Add new functions**: Coordinate map generation and PDF embedding

### detect_main.py
1. **Line 58**: Change `--highlights-merge` to `--with-predetect/--no-predetect`
2. **Lines 312-319**: Modify output format from nested to flat detect array
3. **Lines 195-270**: Modify detection result building to include position objects
4. **Add coordinate map inheritance**: Pass through coordinate maps from read JSON

### duplicate_main.py
1. **Lines 118-122**: Modify output format to include coordinate maps
2. **Add entity-agnostic mode**: New option for cross-entity duplicate detection

### Common Changes Needed
1. **All modules**: Add coordinate map handling throughout
2. **Position format**: Standardize on start/end objects with page_num/block_num/offset
3. **JSON schema**: Update validation functions for new formats

## 7. Implementation Priority

### High Priority (Core Functionality)
1. Modify read_main.py text output to 2D array format
2. Add coordinate map generation to read_main.py
3. Change detect output format to flat array with position objects
4. Update CLI options per specification

### Medium Priority (Feature Enhancement)
1. Integrate PDF coordinate map embedding
2. Add --with-predetect logic to detect_main.py
3. Add cross-entity duplicate detection mode

### Low Priority (Optimization)
1. Remove unused structured text code
2. Update validation schemas
3. Performance optimization for coordinate map generation

## 8. Testing Requirements

1. **Format validation**: Ensure outputs match exact specification formats
2. **Coordinate accuracy**: Verify coordinate maps produce correct PDF positioning
3. **CLI option compatibility**: Test all new/modified options
4. **Backward compatibility**: Ensure existing functionality still works where applicable
5. **Integration testing**: Test full read → detect → duplicate → mask pipeline

## Conclusion

The analysis reveals significant structural changes needed across all three main CLI modules. The primary gaps are:

1. **JSON format mismatches** requiring complete output restructuring
2. **Missing coordinate mapping integration** throughout the pipeline
3. **CLI option discrepancies** requiring interface changes
4. **Text management approach** needing fundamental changes from structured to plain-text based

The implementation will require careful coordination across modules to maintain data flow while implementing the new specification requirements.