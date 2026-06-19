//! Optional Rust acceleration for SoMaJo's emoji/grapheme segmentation.
//!
//! `emoji_boundaries` replicates the boundary computation in
//! `Tokenizer._split_emojis`: it segments the text into UAX#29 grapheme
//! clusters and returns the (start, end) CODEPOINT offsets of every grapheme
//! that should become its own emoji token. The Python predicate is:
//!   - multi-codepoint grapheme: contains Extended_Pictographic OR
//!     Emoji_Presentation OR U+FE0F
//!   - single-codepoint grapheme: is Extended_Pictographic OR Emoji_Presentation
//!
//! Offsets are codepoint indices (matching Python string indexing), not bytes.
//! Whether this is byte-identical to the Python (`regex`-module) version
//! depends on the Unicode versions of icu_properties and the regex module
//! matching — validated by the differential harness, not assumed.

use icu_properties::sets;
use pyo3::prelude::*;
use unicode_segmentation::UnicodeSegmentation;

#[pyfunction]
fn emoji_boundaries(text: &str) -> Vec<(usize, usize)> {
    let ep = sets::extended_pictographic();
    let ep_pres = sets::emoji_presentation();
    let is_trigger = |c: char| c == '\u{FE0F}' || ep.contains(c) || ep_pres.contains(c);
    let is_single = |c: char| ep.contains(c) || ep_pres.contains(c);

    let mut out = Vec::new();
    let mut char_idx = 0usize;
    for g in text.graphemes(true) {
        let n = g.chars().count();
        let start = char_idx;
        char_idx += n;
        let matched = if n > 1 {
            g.chars().any(is_trigger)
        } else {
            g.chars().next().map_or(false, is_single)
        };
        if matched {
            out.push((start, char_idx));
        }
    }
    out
}

#[pymodule]
fn somajo_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(emoji_boundaries, m)?)?;
    Ok(())
}
